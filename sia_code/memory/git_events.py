"""Git integration for extracting timeline events and changelogs."""

import logging
import re
from pathlib import Path
from typing import Any

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError


def _coerce_text(value: str | bytes | Any) -> str:
    """Normalize git message-like values into text."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class GitEventExtractor:
    """Extract timeline events and changelogs from git repository."""

    def __init__(self, repo_path: str | Path):
        """Initialize extractor.

        Args:
            repo_path: Path to git repository

        Raises:
            InvalidGitRepositoryError: If path is not a git repository
        """
        self.repo_path = Path(repo_path)
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(f"{self.repo_path} is not a valid git repository")

    def scan_git_tags(self) -> list[dict[str, Any]]:
        """Extract changelogs from git tags.

        Returns:
            List of changelog dictionaries
        """
        changelogs = []

        tags = sorted(self.repo.tags, key=lambda t: t.commit.committed_datetime, reverse=True)

        for tag in tags:
            try:
                # Get tag message if annotated
                tag_message = ""
                try:
                    tag_message = tag.tag.message if tag.tag else ""
                except AttributeError:
                    # Lightweight tag, no message
                    pass

                # Extract version from tag name (e.g., v1.2.0 -> 1.2.0)
                version = None
                match = re.match(r"^v?(\d+\.\d+\.\d+)", tag.name)
                if match:
                    version = match.group(1)

                changelog = {
                    "tag": tag.name,
                    "version": version,
                    "date": tag.commit.committed_datetime,
                    "summary": tag_message or f"Release {tag.name}",
                    "breaking_changes": self._extract_breaking_changes(tag_message),
                    "features": self._extract_features(tag_message),
                    "fixes": self._extract_fixes(tag_message),
                    "commit_hash": tag.commit.hexsha,
                    "commit_time": tag.commit.committed_datetime,
                }

                changelogs.append(changelog)

            except Exception as e:
                # Skip problematic tags
                print(f"Warning: Could not process tag {tag.name}: {e}")
                continue

        return changelogs

    def scan_merge_events(
        self, since: str | None = None, limit: int | None = 50
    ) -> list[dict[str, Any]]:
        """Extract merge commits as timeline events.

        Args:
            since: Git ref to start from (e.g., 'HEAD~100' or 'v1.0.0')
            limit: Maximum number of merge events to return (None for all)

        Returns:
            List of timeline event dictionaries
        """
        events = []

        # Get merge commits
        if since:
            commit_range = f"{since}..HEAD"
        else:
            commit_range = "HEAD"

        try:
            max_count = limit * 2 if limit is not None and limit > 0 else None
            commits = list(self.repo.iter_commits(commit_range, max_count=max_count))
        except GitCommandError:
            # If range is invalid, just get HEAD commits
            max_count = limit * 2 if limit is not None and limit > 0 else None
            commits = list(self.repo.iter_commits("HEAD", max_count=max_count))

        for commit in commits:
            # Check if it's a merge commit (has multiple parents)
            if len(commit.parents) > 1:
                # Get branch names from commit message
                from_branch, to_branch = self._extract_merge_branches(_coerce_text(commit.message))

                # Get files changed
                files_changed = []
                try:
                    files_changed = [str(path) for path in commit.stats.files.keys()]
                except Exception:
                    pass

                # Get diff stats
                diff_stats = {
                    "insertions": commit.stats.total.get("insertions", 0),
                    "deletions": commit.stats.total.get("deletions", 0),
                    "files": commit.stats.total.get("files", 0),
                }

                event = {
                    "event_type": "merge",
                    "from_ref": from_branch or commit.parents[1].hexsha[:7],
                    "to_ref": to_branch or commit.parents[0].hexsha[:7],
                    "summary": _coerce_text(commit.summary),
                    "files_changed": files_changed[:20],  # Limit to avoid huge lists
                    "diff_stats": diff_stats,
                    "importance": self._determine_importance(diff_stats),
                    "created_at": commit.committed_datetime,
                    "commit_hash": commit.hexsha,
                    "commit_time": commit.committed_datetime,
                    "merge_commit": commit,  # Include for summarization
                }

                events.append(event)

                if limit is not None and limit > 0 and len(events) >= limit:
                    break

        return events

    def compare_refs(self, from_ref: str, to_ref: str) -> dict[str, Any]:
        """Generate timeline event from comparing two git refs.

        Args:
            from_ref: Starting ref (e.g., 'v1.0.0', 'main~10')
            to_ref: Ending ref (e.g., 'v1.1.0', 'HEAD')

        Returns:
            Timeline event dictionary
        """
        try:
            from_commit = self.repo.commit(from_ref)
            to_commit = self.repo.commit(to_ref)
        except GitCommandError as e:
            raise ValueError(f"Invalid git ref: {e}")

        # Get diff
        diff = from_commit.diff(to_commit)

        # Files changed
        files_changed = []
        for change in diff:
            if change.a_path:
                files_changed.append(change.a_path)
            elif change.b_path:
                files_changed.append(change.b_path)

        # Get commits between refs
        commits = list(self.repo.iter_commits(f"{from_ref}..{to_ref}"))

        # Generate summary from commit messages
        summary_parts = []
        for commit in commits[:5]:  # First 5 commits
            summary_parts.append(f"- {commit.summary}")

        summary = "\n".join(summary_parts)
        if len(commits) > 5:
            summary += f"\n\n... and {len(commits) - 5} more commits"

        # Diff stats
        diff_stats = {
            "insertions": sum(c.stats.total.get("insertions", 0) for c in commits),
            "deletions": sum(c.stats.total.get("deletions", 0) for c in commits),
            "files": len(set(files_changed)),
            "commits": len(commits),
        }

        return {
            "event_type": "tag" if "v" in from_ref or "v" in to_ref else "comparison",
            "from_ref": from_ref,
            "to_ref": to_ref,
            "summary": summary or f"Changes from {from_ref} to {to_ref}",
            "files_changed": files_changed[:50],  # Limit
            "diff_stats": diff_stats,
            "importance": self._determine_importance(diff_stats),
            "created_at": to_commit.committed_datetime,
        }

    def _extract_breaking_changes(self, message: str) -> list[str]:
        """Extract breaking changes from commit/tag message.

        Args:
            message: Commit or tag message

        Returns:
            List of breaking changes
        """
        breaking = []
        if not message:
            return breaking

        # Look for "BREAKING CHANGE:", "Breaking:", etc.
        for line in message.split("\n"):
            if re.search(r"breaking|^!:", line, re.IGNORECASE):
                breaking.append(line.strip())

        return breaking

    def _extract_features(self, message: str) -> list[str]:
        """Extract features from commit/tag message."""
        features = []
        if not message:
            return features

        for line in message.split("\n"):
            if re.search(r"^(feat|feature|add):", line, re.IGNORECASE):
                features.append(line.strip())

        return features

    def _extract_fixes(self, message: str) -> list[str]:
        """Extract fixes from commit/tag message."""
        fixes = []
        if not message:
            return fixes

        for line in message.split("\n"):
            if re.search(r"^(fix|bug):", line, re.IGNORECASE):
                fixes.append(line.strip())

        return fixes

    def _extract_merge_branches(self, message: str) -> tuple[str | None, str | None]:
        """Extract branch names from merge commit message.

        Args:
            message: Merge commit message

        Returns:
            Tuple of (from_branch, to_branch)
        """
        # Common patterns:
        # "Merge branch 'feature' into 'main'"
        # "Merge pull request #123 from user/branch"

        match = re.search(r"Merge\s+branch\s+'([^']+)'(?:\s+into\s+'([^']+)')?", message)
        if match:
            return (match.group(1), match.group(2))

        match = re.search(r"Merge\s+pull\s+request.*from\s+(\S+)", message)
        if match:
            return (match.group(1), None)

        return (None, None)

    def is_merge_branch_message(self, message: str) -> bool:
        """Return True when commit message follows 'Merge branch ...' pattern."""
        return bool(re.search(r"^Merge\s+branch\s+'[^']+'", (message or "").strip()))

    def _determine_importance(self, diff_stats: dict[str, Any]) -> str:
        """Determine importance based on diff statistics.

        Args:
            diff_stats: Dictionary with insertions, deletions, files

        Returns:
            'high', 'medium', or 'low'
        """
        files = diff_stats.get("files", 0)
        lines = diff_stats.get("insertions", 0) + diff_stats.get("deletions", 0)

        if files > 50 or lines > 1000:
            return "high"
        elif files > 10 or lines > 200:
            return "medium"
        else:
            return "low"

    def get_commits_between_tags(self, from_tag: str, to_tag: str) -> list[str]:
        """Get commit messages between two tags.

        Args:
            from_tag: Starting tag (exclusive)
            to_tag: Ending tag (inclusive)

        Returns:
            List of commit messages (first line only)
        """
        try:
            commits = list(self.repo.iter_commits(f"{from_tag}..{to_tag}"))
            # Return first line of each commit message
            return [_coerce_text(c.message).strip().split("\n")[0] for c in commits]
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not get commits between {from_tag} and {to_tag}: {e}")
            return []

    def get_commits_in_merge(self, merge_commit) -> list[str]:
        """Get commit messages from a merged branch.

        Args:
            merge_commit: The merge commit object

        Returns:
            List of commit messages from the merged branch (first line only)
        """
        if len(merge_commit.parents) < 2:
            return []

        try:
            # Get commits from second parent (merged branch) to merge-base
            base = self.repo.merge_base(merge_commit.parents[0], merge_commit.parents[1])
            if base:
                commits = list(
                    self.repo.iter_commits(f"{base[0].hexsha}..{merge_commit.parents[1].hexsha}")
                )
                return [_coerce_text(c.message).strip().split("\n")[0] for c in commits]
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not get commits for merge {merge_commit.hexsha[:7]}: {e}")
            return []

        return []


# Convenience functions


def scan_git_tags(repo_path: str | Path) -> list[dict[str, Any]]:
    """Extract changelog from git tags.

    Args:
        repo_path: Path to git repository

    Returns:
        List of changelog dictionaries
    """
    extractor = GitEventExtractor(repo_path)
    return extractor.scan_git_tags()


def scan_merge_events(
    repo_path: str | Path, since: str | None = None, limit: int | None = 50
) -> list[dict[str, Any]]:
    """Extract merge commits as timeline events.

    Args:
        repo_path: Path to git repository
        since: Git ref to start from
        limit: Maximum number of events (None for all)

    Returns:
        List of timeline event dictionaries
    """
    extractor = GitEventExtractor(repo_path)
    return extractor.scan_merge_events(since=since, limit=limit)


def compare_refs(repo_path: str | Path, from_ref: str, to_ref: str) -> dict[str, Any]:
    """Generate timeline event from ref comparison.

    Args:
        repo_path: Path to git repository
        from_ref: Starting ref
        to_ref: Ending ref

    Returns:
        Timeline event dictionary
    """
    extractor = GitEventExtractor(repo_path)
    return extractor.compare_refs(from_ref, to_ref)

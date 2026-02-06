"""Git sync service for importing timeline events and changelogs."""

import logging
from pathlib import Path
from typing import Any

from .git_events import GitEventExtractor
from ..storage.base import StorageBackend

logger = logging.getLogger(__name__)


class GitSyncStats:
    """Statistics from a git sync operation."""

    def __init__(self):
        self.changelogs_added = 0
        self.changelogs_skipped = 0
        self.timeline_added = 0
        self.timeline_skipped = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "changelogs_added": self.changelogs_added,
            "changelogs_skipped": self.changelogs_skipped,
            "timeline_added": self.timeline_added,
            "timeline_skipped": self.timeline_skipped,
            "total_added": self.changelogs_added + self.timeline_added,
            "total_skipped": self.changelogs_skipped + self.timeline_skipped,
            "errors": self.errors,
        }


class GitSyncService:
    """Service for syncing git history to memory."""

    def __init__(self, backend: StorageBackend, repo_path: Path | str, config=None):
        """Initialize git sync service.

        Args:
            backend: Storage backend for writing memory
            repo_path: Path to git repository
            config: Optional config object with summarization settings
        """
        self.backend = backend
        self.repo_path = Path(repo_path)
        self.extractor = GitEventExtractor(repo_path)
        self.config = config
        self._summarizer = None

    @property
    def summarizer(self):
        """Lazy load summarizer only if enabled in config."""
        if self._summarizer is None and self.config is not None:
            if hasattr(self.config, "summarization") and self.config.summarization.enabled:
                from .summarizer import get_summarizer

                self._summarizer = get_summarizer(self.config.summarization.model)
        return self._summarizer

    def sync(
        self,
        since: str | None = None,
        limit: int = 50,
        dry_run: bool = False,
        tags_only: bool = False,
        merges_only: bool = False,
        min_importance: str = "low",
    ) -> dict[str, Any]:
        """Sync git history to memory with deduplication.

        Args:
            since: Git ref to start from (e.g., 'v1.0.0', 'HEAD~50')
            limit: Maximum number of events to process
            dry_run: If True, don't write to backend
            tags_only: Only process tags, skip merges
            merges_only: Only process merges, skip tags
            min_importance: Minimum importance level ('high', 'medium', 'low')

        Returns:
            Dictionary with sync statistics
        """
        stats = GitSyncStats()

        # Process tags as changelogs (unless merges_only)
        if not merges_only:
            try:
                changelogs = self.extractor.scan_git_tags()
                for i, changelog_data in enumerate(changelogs):
                    # Check if already exists
                    if self._is_duplicate_changelog(changelog_data["tag"]):
                        stats.changelogs_skipped += 1
                        continue

                    # Enhance summary with AI if enabled
                    # Tags are sorted newest-first, so look at next tag (older) for commit range
                    if self.summarizer and i + 1 < len(changelogs):
                        try:
                            older_tag = changelogs[i + 1]["tag"]
                            commits = self.extractor.get_commits_between_tags(
                                older_tag, changelog_data["tag"]
                            )
                            if commits:
                                enhanced_summary = self.summarizer.enhance_changelog(
                                    changelog_data["tag"],
                                    changelog_data.get("summary", ""),
                                    commits,
                                )
                                changelog_data["summary"] = enhanced_summary
                                logger.debug(f"Enhanced changelog for {changelog_data['tag']}")
                        except Exception as e:
                            logger.debug(f"Could not enhance changelog: {e}")

                    if not dry_run:
                        self.backend.add_changelog(
                            tag=changelog_data["tag"],
                            version=changelog_data.get("version"),
                            summary=changelog_data.get("summary", ""),
                            breaking_changes=changelog_data.get("breaking_changes", []),
                            features=changelog_data.get("features", []),
                            fixes=changelog_data.get("fixes", []),
                            commit_hash=changelog_data.get("commit_hash"),
                            commit_time=changelog_data.get("commit_time"),
                        )
                    stats.changelogs_added += 1

                    # Early exit if hit limit
                    if stats.changelogs_added >= limit:
                        break
            except Exception as e:
                stats.errors.append(f"Error processing tags: {e}")

        # Process merge commits as timeline events (unless tags_only)
        if not tags_only:
            try:
                merge_events = self.extractor.scan_merge_events(since=since, limit=limit)
                for event_data in merge_events:
                    # Filter by importance
                    event_importance = event_data.get("importance", "medium")
                    if not self._meets_importance_threshold(event_importance, min_importance):
                        stats.timeline_skipped += 1
                        continue

                    # Check if already exists
                    if self._is_duplicate_event(
                        event_data["event_type"],
                        event_data["from_ref"],
                        event_data["to_ref"],
                    ):
                        stats.timeline_skipped += 1
                        continue

                    # Enhance summary with AI if enabled
                    if self.summarizer and "merge_commit" in event_data:
                        try:
                            commits = self.extractor.get_commits_in_merge(
                                event_data["merge_commit"]
                            )
                            if commits:
                                enhanced_summary = self.summarizer.enhance_timeline_event(
                                    event_data["summary"], commits
                                )
                                event_data["summary"] = enhanced_summary
                                logger.debug(
                                    f"Enhanced timeline event for merge {event_data['to_ref']}"
                                )
                        except Exception as e:
                            logger.debug(f"Could not enhance timeline event: {e}")

                    if not dry_run:
                        self.backend.add_timeline_event(
                            event_type=event_data["event_type"],
                            from_ref=event_data["from_ref"],
                            to_ref=event_data["to_ref"],
                            summary=event_data["summary"],
                            files_changed=event_data.get("files_changed", []),
                            diff_stats=event_data.get("diff_stats", {}),
                            importance=event_importance,
                            commit_hash=event_data.get("commit_hash"),
                            commit_time=event_data.get("commit_time"),
                        )
                    stats.timeline_added += 1

                    # Early exit if hit limit
                    if stats.timeline_added >= limit:
                        break
            except Exception as e:
                stats.errors.append(f"Error processing merges: {e}")

        return stats.to_dict()

    def _is_duplicate_changelog(self, tag: str) -> bool:
        """Check if changelog entry already exists.

        Args:
            tag: Git tag name

        Returns:
            True if changelog with this tag exists
        """
        try:
            existing = self.backend.get_changelogs(limit=1000)
            return any(c.tag == tag for c in existing)
        except Exception:
            # If check fails, assume not duplicate to avoid data loss
            return False

    def _is_duplicate_event(self, event_type: str, from_ref: str, to_ref: str) -> bool:
        """Check if timeline event already exists.

        Args:
            event_type: Type of event (merge, tag, etc.)
            from_ref: Source git ref
            to_ref: Target git ref

        Returns:
            True if event with these attributes exists
        """
        try:
            existing = self.backend.get_timeline_events(limit=1000)
            return any(
                e.event_type == event_type and e.from_ref == from_ref and e.to_ref == to_ref
                for e in existing
            )
        except Exception:
            # If check fails, assume not duplicate to avoid data loss
            return False

    def _meets_importance_threshold(self, event_importance: str, min_importance: str) -> bool:
        """Check if event meets minimum importance threshold.

        Args:
            event_importance: Importance level of event
            min_importance: Minimum required importance

        Returns:
            True if event importance >= min_importance
        """
        importance_order = {"low": 0, "medium": 1, "high": 2}
        event_level = importance_order.get(event_importance, 0)
        min_level = importance_order.get(min_importance, 0)
        return event_level >= min_level

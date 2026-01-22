"""Git sync service for importing timeline events and changelogs."""

from datetime import datetime
from pathlib import Path
from typing import Any

from .git_events import GitEventExtractor
from ..storage.base import StorageBackend


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

    def __init__(self, backend: StorageBackend, repo_path: Path | str):
        """Initialize git sync service.

        Args:
            backend: Storage backend for writing memory
            repo_path: Path to git repository
        """
        self.backend = backend
        self.repo_path = Path(repo_path)
        self.extractor = GitEventExtractor(repo_path)

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
                for changelog_data in changelogs:
                    # Check if already exists
                    if self._is_duplicate_changelog(changelog_data["tag"]):
                        stats.changelogs_skipped += 1
                        continue

                    if not dry_run:
                        self.backend.add_changelog(
                            tag=changelog_data["tag"],
                            version=changelog_data.get("version"),
                            summary=changelog_data.get("summary", ""),
                            breaking_changes=changelog_data.get("breaking_changes", []),
                            features=changelog_data.get("features", []),
                            fixes=changelog_data.get("fixes", []),
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

                    if not dry_run:
                        self.backend.add_timeline_event(
                            event_type=event_data["event_type"],
                            from_ref=event_data["from_ref"],
                            to_ref=event_data["to_ref"],
                            summary=event_data["summary"],
                            files_changed=event_data.get("files_changed", []),
                            diff_stats=event_data.get("diff_stats", {}),
                            importance=event_importance,
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

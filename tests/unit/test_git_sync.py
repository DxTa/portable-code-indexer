"""Unit tests for GitSyncService."""

from unittest.mock import MagicMock, patch
import subprocess

import pytest

from sia_code.memory.git_sync import GitSyncService, GitSyncStats


class TestGitSyncStats:
    """Tests for GitSyncStats class."""

    def test_stats_initialization(self):
        """Test GitSyncStats initializes with zeros."""
        stats = GitSyncStats()
        assert stats.changelogs_added == 0
        assert stats.changelogs_skipped == 0
        assert stats.timeline_added == 0
        assert stats.timeline_skipped == 0
        assert stats.errors == []

    def test_stats_to_dict(self):
        """Test GitSyncStats converts to dictionary."""
        stats = GitSyncStats()
        stats.changelogs_added = 2
        stats.timeline_added = 3

        result = stats.to_dict()
        assert result["changelogs_added"] == 2
        assert result["timeline_added"] == 3
        assert result["total_added"] == 5


class TestGitSyncService:
    """Tests for GitSyncService."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock backend."""
        backend = MagicMock()
        backend.add_timeline_event.return_value = 1
        backend.add_changelog.return_value = 1
        backend.get_timeline_events.return_value = []
        backend.get_changelogs.return_value = []
        return backend

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repository."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)

        return tmp_path

    @pytest.fixture
    def sync_service(self, mock_backend, git_repo):
        """Create GitSyncService with mock backend."""
        return GitSyncService(mock_backend, git_repo)

    def test_sync_empty_repo(self, sync_service, mock_backend):
        """Test sync on repo with no tags or merges."""
        stats = sync_service.sync(since="HEAD~1", limit=10)

        assert stats["changelogs_added"] == 0
        assert stats["timeline_added"] == 0

    def test_sync_with_tags(self, sync_service, mock_backend, git_repo):
        """Test sync extracts tags as changelogs."""
        # Create a tag
        subprocess.run(
            ["git", "tag", "-a", "v1.0.0", "-m", "Release 1.0"], cwd=git_repo, check=True
        )

        stats = sync_service.sync()

        # Should have called add_changelog
        assert mock_backend.add_changelog.called
        assert stats["changelogs_added"] >= 1

    def test_dry_run_no_writes(self, sync_service, mock_backend, git_repo):
        """Test dry run doesn't write to backend."""
        subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", "Test"], cwd=git_repo, check=True)

        sync_service.sync(dry_run=True)

        mock_backend.add_changelog.assert_not_called()
        mock_backend.add_timeline_event.assert_not_called()

    def test_tags_only_flag(self, sync_service, mock_backend):
        """Test --tags-only skips merge commits."""
        with patch.object(sync_service.extractor, "scan_merge_events") as mock_merges:
            sync_service.sync(tags_only=True)
            mock_merges.assert_not_called()

    def test_merges_only_flag(self, sync_service, mock_backend):
        """Test --merges-only skips tags."""
        with patch.object(sync_service.extractor, "scan_git_tags") as mock_tags:
            sync_service.sync(merges_only=True)
            mock_tags.assert_not_called()

    def test_deduplication_changelog(self, sync_service, mock_backend, git_repo):
        """Test that duplicate changelog entries are skipped."""
        # Create tag
        subprocess.run(["git", "tag", "-a", "v1.0.0", "-m", "Test"], cwd=git_repo, check=True)

        # Mock backend to return existing changelog
        from sia_code.core.models import ChangelogEntry

        mock_backend.get_changelogs.return_value = [
            ChangelogEntry(id=1, tag="v1.0.0", version="1.0.0")
        ]

        stats = sync_service.sync()

        # Should skip the duplicate
        assert stats["changelogs_skipped"] >= 1

    def test_importance_filtering(self, sync_service, mock_backend):
        """Test min_importance filters low-importance events."""
        # Mock extractor to return events with different importance
        mock_events = [
            {
                "importance": "high",
                "event_type": "merge",
                "from_ref": "a",
                "to_ref": "b",
                "summary": "Big change",
                "files_changed": [],
                "diff_stats": {},
            },
            {
                "importance": "low",
                "event_type": "merge",
                "from_ref": "c",
                "to_ref": "d",
                "summary": "Tiny fix",
                "files_changed": [],
                "diff_stats": {},
            },
        ]

        with patch.object(sync_service.extractor, "scan_merge_events", return_value=mock_events):
            stats = sync_service.sync(min_importance="high")

            # Should skip low importance
            assert stats["timeline_skipped"] >= 1

    def test_commit_context_passed_to_backend(self, sync_service, mock_backend):
        """Ensure commit metadata is forwarded to backend writes."""
        commit_time = datetime(2024, 1, 1, 12, 0, 0)
        tag_event = {
            "tag": "v1.0.0",
            "version": "1.0.0",
            "summary": "Release 1.0",
            "breaking_changes": [],
            "features": [],
            "fixes": [],
            "commit_hash": "abc123",
            "commit_time": commit_time,
        }
        merge_event = {
            "event_type": "merge",
            "from_ref": "feature",
            "to_ref": "main",
            "summary": "Merge feature",
            "files_changed": [],
            "diff_stats": {},
            "importance": "medium",
            "commit_hash": "def456",
            "commit_time": commit_time,
        }

        with patch.object(sync_service.extractor, "scan_git_tags", return_value=[tag_event]):
            with patch.object(sync_service.extractor, "scan_merge_events", return_value=[merge_event]):
                sync_service.sync()

        mock_backend.add_changelog.assert_called_with(
            tag="v1.0.0",
            version="1.0.0",
            summary="Release 1.0",
            breaking_changes=[],
            features=[],
            fixes=[],
            commit_hash="abc123",
            commit_time=commit_time,
        )
        mock_backend.add_timeline_event.assert_called_with(
            event_type="merge",
            from_ref="feature",
            to_ref="main",
            summary="Merge feature",
            files_changed=[],
            diff_stats={},
            importance="medium",
            commit_hash="def456",
            commit_time=commit_time,
        )

    def test_meets_importance_threshold(self, sync_service):
        """Test importance threshold logic."""
        assert sync_service._meets_importance_threshold("high", "low") is True
        assert sync_service._meets_importance_threshold("medium", "medium") is True
        assert sync_service._meets_importance_threshold("low", "high") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

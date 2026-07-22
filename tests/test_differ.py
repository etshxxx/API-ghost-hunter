"""Tests for the snapshot diff engine."""
import pytest

from api_ghost_hunter.models import Endpoint, Snapshot, DiffResult
from api_ghost_hunter.differ import Differ


def make_snapshot(endpoints, target="https://example.com", timestamp="2026-01-01T10:00:00"):
    return Snapshot(
        target_url=target,
        timestamp=timestamp,
        endpoints=endpoints,
    )


class TestDiffer:
    def test_identical_snapshots(self):
        eps = [
            Endpoint(method="get", path="/api/users"),
            Endpoint(method="post", path="/api/users"),
        ]
        old = make_snapshot(eps, timestamp="2026-01-01")
        new = make_snapshot(eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 0
        assert len(result.removed) == 0
        assert len(result.modified) == 0
        assert len(result.unchanged) == 2

    def test_added_endpoints(self):
        old_eps = [Endpoint(method="get", path="/api/users")]
        new_eps = [
            Endpoint(method="get", path="/api/users"),
            Endpoint(method="post", path="/api/users"),
            Endpoint(method="get", path="/api/products"),
        ]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 2
        added_keys = {ep.key for ep in result.added}
        assert "POST /api/users" in added_keys
        assert "GET /api/products" in added_keys

    def test_removed_endpoints(self):
        old_eps = [
            Endpoint(method="get", path="/api/users"),
            Endpoint(method="delete", path="/api/users/old"),
            Endpoint(method="get", path="/api/legacy"),
        ]
        new_eps = [Endpoint(method="get", path="/api/users")]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.removed) == 2
        removed_keys = {ep.key for ep in result.removed}
        assert "DELETE /api/users/old" in removed_keys
        assert "GET /api/legacy" in removed_keys

    def test_modified_endpoints(self):
        old_eps = [Endpoint(method="get", path="/api/users", summary="List users", deprecated=False)]
        new_eps = [Endpoint(method="get", path="/api/users", summary="List all users", deprecated=True)]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.modified) == 1
        mod = result.modified[0]
        assert mod["endpoint"] == "GET /api/users"
        assert "summary" in mod["changes"]
        assert "deprecated" in mod["changes"]
        assert mod["changes"]["summary"]["old"] == "List users"
        assert mod["changes"]["summary"]["new"] == "List all users"

    def test_unchanged_endpoints(self):
        old_eps = [Endpoint(method="get", path="/api/health", summary="Health check")]
        new_eps = [Endpoint(method="get", path="/api/health", summary="Health check")]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.unchanged) == 1
        assert result.unchanged[0].key == "GET /api/health"

    def test_mixed_changes(self):
        old_eps = [
            Endpoint(method="get", path="/api/users", summary="Old summary"),
            Endpoint(method="delete", path="/api/users/old"),
            Endpoint(method="get", path="/api/health", summary="Health"),
        ]
        new_eps = [
            Endpoint(method="get", path="/api/users", summary="New summary"),
            Endpoint(method="get", path="/api/health", summary="Health"),
            Endpoint(method="post", path="/api/products"),
        ]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 1
        assert len(result.removed) == 1
        assert len(result.modified) == 1
        assert len(result.unchanged) == 1
        assert result.total_changes == 3

    def test_empty_snapshots(self):
        old = make_snapshot([], timestamp="2026-01-01")
        new = make_snapshot([], timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 0
        assert len(result.removed) == 0
        assert len(result.modified) == 0
        assert len(result.unchanged) == 0

    def test_old_empty_new_full(self):
        old = make_snapshot([], timestamp="2026-01-01")
        new_eps = [
            Endpoint(method="get", path="/api/users"),
            Endpoint(method="post", path="/api/users"),
        ]
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 2
        assert len(result.removed) == 0

    def test_old_full_new_empty(self):
        old_eps = [
            Endpoint(method="get", path="/api/users"),
            Endpoint(method="post", path="/api/users"),
        ]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot([], timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.added) == 0
        assert len(result.removed) == 2

    def test_diff_result_has_correct_snapshots(self):
        old = make_snapshot([Endpoint(method="get", path="/a")], timestamp="2026-01-01")
        new = make_snapshot([Endpoint(method="get", path="/b")], timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert result.old_snapshot.timestamp == "2026-01-01"
        assert result.new_snapshot.timestamp == "2026-02-01"

    def test_security_change_detected_as_modified(self):
        old_eps = [Endpoint(method="get", path="/api/admin", security=[])]
        new_eps = [Endpoint(method="get", path="/api/admin", security=[{"BearerAuth": []}])]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        assert len(result.modified) == 1
        assert "security" in result.modified[0]["changes"]

    def test_to_dict_structure(self):
        old_eps = [Endpoint(method="delete", path="/api/old")]
        new_eps = [Endpoint(method="post", path="/api/new")]
        old = make_snapshot(old_eps, timestamp="2026-01-01")
        new = make_snapshot(new_eps, timestamp="2026-02-01")
        result = Differ.compare(old, new)
        d = result.to_dict()
        assert "summary" in d
        assert d["summary"]["added"] == 1
        assert d["summary"]["removed"] == 1
        assert "added" in d
        assert "removed" in d

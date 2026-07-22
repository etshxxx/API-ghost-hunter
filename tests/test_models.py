"""Tests for API Ghost Hunter data models."""
import json
import pytest

from api_ghost_hunter.models import Endpoint, Snapshot, GhostEndpoint, DiffResult


class TestEndpoint:
    def test_endpoint_creation_defaults(self):
        ep = Endpoint(method="get", path="/api/users")
        assert ep.method == "get"
        assert ep.path == "/api/users"
        assert ep.summary == ""
        assert ep.description == ""
        assert ep.parameters == []
        assert ep.request_body is None
        assert ep.responses == {}
        assert ep.security == []
        assert ep.tags == []
        assert ep.deprecated is False
        assert ep.source == "openapi"

    def test_endpoint_key(self):
        ep = Endpoint(method="get", path="/api/users")
        assert ep.key == "GET /api/users"

    def test_endpoint_key_uppercase_method(self):
        ep = Endpoint(method="POST", path="/api/items")
        assert ep.key == "POST /api/items"

    def test_requires_auth_with_security(self):
        ep = Endpoint(method="get", path="/api/users", security=[{"BearerAuth": []}])
        assert ep.requires_auth is True

    def test_requires_auth_without_security(self):
        ep = Endpoint(method="get", path="/api/users", security=[])
        assert ep.requires_auth is False

    def test_to_dict(self):
        ep = Endpoint(method="get", path="/api/users", summary="List users")
        d = ep.to_dict()
        assert d["method"] == "get"
        assert d["path"] == "/api/users"
        assert d["summary"] == "List users"

    def test_from_dict(self):
        data = {
            "method": "get",
            "path": "/api/users",
            "summary": "List users",
            "description": "Get all users",
            "parameters": [{"name": "page", "in": "query"}],
            "request_body": None,
            "responses": {"200": {"description": "OK"}},
            "security": [{"ApiKeyAuth": []}],
            "tags": ["users"],
            "deprecated": False,
            "source": "openapi",
            "extra_field": "ignored",
        }
        ep = Endpoint.from_dict(data)
        assert ep.method == "get"
        assert ep.path == "/api/users"
        assert ep.summary == "List users"
        assert ep.tags == ["users"]
        assert ep.security == [{"ApiKeyAuth": []}]

    def test_from_dict_ignores_unknown_fields(self):
        data = {"method": "get", "path": "/api/test", "unknown": "value"}
        ep = Endpoint.from_dict(data)
        assert ep.method == "get"
        assert ep.path == "/api/test"
        assert not hasattr(ep, "unknown")

    def test_diff_no_changes(self):
        ep1 = Endpoint(method="get", path="/api/users", summary="List users")
        ep2 = Endpoint(method="get", path="/api/users", summary="List users")
        changes = ep1.diff(ep2)
        assert changes == {}

    def test_diff_with_changes(self):
        ep1 = Endpoint(method="get", path="/api/users", summary="List users")
        ep2 = Endpoint(method="get", path="/api/users", summary="List all users")
        changes = ep1.diff(ep2)
        assert "summary" in changes
        assert changes["summary"]["old"] == "List users"
        assert changes["summary"]["new"] == "List all users"

    def test_diff_deprecated_change(self):
        ep1 = Endpoint(method="get", path="/api/users", deprecated=False)
        ep2 = Endpoint(method="get", path="/api/users", deprecated=True)
        changes = ep1.diff(ep2)
        assert "deprecated" in changes
        assert changes["deprecated"]["old"] is False
        assert changes["deprecated"]["new"] is True

    def test_diff_security_change(self):
        ep1 = Endpoint(method="get", path="/api/users", security=[])
        ep2 = Endpoint(method="get", path="/api/users", security=[{"BearerAuth": []}])
        changes = ep1.diff(ep2)
        assert "security" in changes

    def test_roundtrip_dict(self):
        ep = Endpoint(
            method="post",
            path="/api/items",
            summary="Create item",
            tags=["items"],
            security=[{"BearerAuth": []}],
            deprecated=False,
        )
        d = ep.to_dict()
        ep2 = Endpoint.from_dict(d)
        assert ep2.method == ep.method
        assert ep2.path == ep.path
        assert ep2.summary == ep.summary
        assert ep2.tags == ep.tags
        assert ep2.security == ep.security


class TestSnapshot:
    def test_snapshot_creation(self):
        ep1 = Endpoint(method="get", path="/api/users")
        ep2 = Endpoint(method="post", path="/api/users")
        snap = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01T10:00:00",
            endpoints=[ep1, ep2],
        )
        assert snap.target_url == "https://example.com"
        assert len(snap.endpoints) == 2
        assert snap.archive_timestamp == ""

    def test_snapshot_to_dict(self):
        ep = Endpoint(method="get", path="/api/users")
        snap = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01T10:00:00",
            endpoints=[ep],
            spec_url="https://example.com/openapi.json",
            spec_version="OpenAPI 3.0.3",
        )
        d = snap.to_dict()
        assert d["target_url"] == "https://example.com"
        assert d["timestamp"] == "2026-01-01T10:00:00"
        assert d["endpoint_count"] == 1
        assert d["spec_url"] == "https://example.com/openapi.json"
        assert d["spec_version"] == "OpenAPI 3.0.3"
        assert d["archive_timestamp"] == ""
        assert len(d["endpoints"]) == 1

    def test_snapshot_to_json(self):
        ep = Endpoint(method="get", path="/api/users")
        snap = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01T10:00:00",
            endpoints=[ep],
        )
        j = snap.to_json()
        data = json.loads(j)
        assert data["target_url"] == "https://example.com"

    def test_snapshot_from_dict(self):
        data = {
            "target_url": "https://example.com",
            "timestamp": "2026-01-01T10:00:00",
            "spec_url": "https://example.com/openapi.json",
            "spec_version": "OpenAPI 3.0.3",
            "source": "openapi",
            "archive_timestamp": "20250101120000",
            "endpoint_count": 2,
            "endpoints": [
                {"method": "get", "path": "/api/users", "summary": "List"},
                {"method": "post", "path": "/api/users", "summary": "Create"},
            ],
        }
        snap = Snapshot.from_dict(data)
        assert snap.target_url == "https://example.com"
        assert len(snap.endpoints) == 2
        assert snap.endpoints[0].method == "get"
        assert snap.endpoints[1].method == "post"
        assert snap.archive_timestamp == "20250101120000"

    def test_get_endpoint_map(self):
        ep1 = Endpoint(method="get", path="/api/users")
        ep2 = Endpoint(method="post", path="/api/users")
        ep3 = Endpoint(method="delete", path="/api/users/1")
        snap = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01T10:00:00",
            endpoints=[ep1, ep2, ep3],
        )
        m = snap.get_endpoint_map()
        assert "GET /api/users" in m
        assert "POST /api/users" in m
        assert "DELETE /api/users/1" in m
        assert len(m) == 3

    def test_snapshot_roundtrip(self):
        ep = Endpoint(method="get", path="/api/users", summary="List users")
        snap = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01T10:00:00",
            endpoints=[ep],
            spec_url="https://example.com/openapi.json",
            spec_version="OpenAPI 3.0.3",
            source="openapi",
            archive_timestamp="20250101120000",
        )
        d = snap.to_dict()
        snap2 = Snapshot.from_dict(d)
        assert snap2.target_url == snap.target_url
        assert snap2.timestamp == snap.timestamp
        assert snap2.spec_url == snap.spec_url
        assert snap2.archive_timestamp == snap.archive_timestamp
        assert len(snap2.endpoints) == 1
        assert snap2.endpoints[0].key == "GET /api/users"


class TestGhostEndpoint:
    def test_ghost_creation(self):
        ep = Endpoint(method="get", path="/api/old", security=[{"BearerAuth": []}])
        ghost = GhostEndpoint(
            endpoint=ep,
            status_code=200,
            response_length=1024,
            response_time=0.5,
            still_alive=True,
            auth_bypassed=True,
        )
        assert ghost.endpoint.path == "/api/old"
        assert ghost.status_code == 200
        assert ghost.still_alive is True
        assert ghost.auth_bypassed is True
        assert ghost.error == ""
        assert ghost.response_snippet == ""
        assert ghost.probed_with_auth is False
        assert ghost.auth_status_code == 0

    def test_ghost_to_dict(self):
        ep = Endpoint(method="get", path="/api/old")
        ghost = GhostEndpoint(
            endpoint=ep,
            status_code=404,
            response_length=0,
            response_time=0.1,
            still_alive=False,
            auth_bypassed=False,
            error="Not found",
        )
        d = ghost.to_dict()
        assert d["status_code"] == 404
        assert d["still_alive"] is False
        assert d["error"] == "Not found"
        assert "endpoint" in d

    def test_ghost_with_auth_probe(self):
        ep = Endpoint(method="get", path="/api/admin", security=[{"BearerAuth": []}])
        ghost = GhostEndpoint(
            endpoint=ep,
            status_code=200,
            response_length=500,
            response_time=0.3,
            still_alive=True,
            auth_bypassed=True,
        )
        ghost.probed_with_auth = True
        ghost.auth_status_code = 403
        d = ghost.to_dict()
        assert d["probed_with_auth"] is True
        assert d["auth_status_code"] == 403


class TestDiffResult:
    def test_diff_result_creation(self):
        snap_old = Snapshot(target_url="https://example.com", timestamp="2026-01-01")
        snap_new = Snapshot(target_url="https://example.com", timestamp="2026-02-01")
        result = DiffResult(
            old_snapshot=snap_old,
            new_snapshot=snap_new,
        )
        assert result.added == []
        assert result.removed == []
        assert result.modified == []
        assert result.unchanged == []

    def test_total_changes(self):
        snap_old = Snapshot(target_url="https://example.com", timestamp="2026-01-01")
        snap_new = Snapshot(target_url="https://example.com", timestamp="2026-02-01")
        ep1 = Endpoint(method="get", path="/api/new")
        ep2 = Endpoint(method="delete", path="/api/old")
        result = DiffResult(
            old_snapshot=snap_old,
            new_snapshot=snap_new,
            added=[ep1],
            removed=[ep2],
            modified=[{"endpoint": "GET /api/users", "changes": {}}],
        )
        assert result.total_changes == 3

    def test_diff_result_to_dict(self):
        snap_old = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01",
            endpoints=[Endpoint(method="get", path="/api/old")],
        )
        snap_new = Snapshot(
            target_url="https://example.com",
            timestamp="2026-02-01",
            endpoints=[Endpoint(method="get", path="/api/new")],
        )
        ep_added = Endpoint(method="get", path="/api/new")
        ep_removed = Endpoint(method="get", path="/api/old")
        result = DiffResult(
            old_snapshot=snap_old,
            new_snapshot=snap_new,
            added=[ep_added],
            removed=[ep_removed],
        )
        d = result.to_dict()
        assert d["summary"]["added"] == 1
        assert d["summary"]["removed"] == 1
        assert d["summary"]["total_changes"] == 2
        assert len(d["added"]) == 1
        assert len(d["removed"]) == 1

    def test_diff_result_with_archive_timestamps(self):
        snap_old = Snapshot(
            target_url="https://example.com",
            timestamp="2026-01-01",
            archive_timestamp="20250101120000",
        )
        snap_new = Snapshot(
            target_url="https://example.com",
            timestamp="2026-02-01",
        )
        result = DiffResult(old_snapshot=snap_old, new_snapshot=snap_new)
        d = result.to_dict()
        assert d["old_snapshot"]["archive_timestamp"] == "20250101120000"
        assert d["new_snapshot"]["archive_timestamp"] == ""

"""Tests for the Wayback Machine archiver (with mocked HTTP)."""
import json
import pytest
from unittest.mock import patch, MagicMock

from api_ghost_hunter.archiver import Archiver, ArchivedSpec


class TestArchivedSpec:
    def test_creation(self):
        a = ArchivedSpec(
            timestamp="20250101120000",
            original_url="https://example.com/openapi.json",
            status_code="200",
            digest="abc123",
        )
        assert a.timestamp == "20250101120000"
        assert a.original_url == "https://example.com/openapi.json"
        assert a.status_code == "200"
        assert a.digest == "abc123"
        assert a.spec_data is None
        assert a.endpoints_count == 0
        assert a.error == ""

    def test_formatted_date_full(self):
        a = ArchivedSpec("20250101120000", "https://example.com", "200", "abc")
        assert a.formatted_date == "2025-01-01 12:00:00"

    def test_formatted_date_date_only(self):
        a = ArchivedSpec("20250101", "https://example.com", "200", "abc")
        assert a.formatted_date == "2025-01-01"

    def test_formatted_date_invalid(self):
        a = ArchivedSpec("invalid", "https://example.com", "200", "abc")
        assert a.formatted_date == "invalid"

    def test_formatted_date_empty(self):
        a = ArchivedSpec("", "https://example.com", "200", "abc")
        assert a.formatted_date == ""

    def test_to_dict(self):
        a = ArchivedSpec("20250101120000", "https://example.com/openapi.json", "200", "abc123")
        a.endpoints_count = 5
        a.spec_version = "OpenAPI 3.0.3"
        d = a.to_dict()
        assert d["timestamp"] == "20250101120000"
        assert d["original_url"] == "https://example.com/openapi.json"
        assert d["status_code"] == "200"
        assert d["digest"] == "abc123"
        assert d["endpoints_count"] == 5
        assert d["spec_version"] == "OpenAPI 3.0.3"
        assert d["error"] == ""
        assert d["formatted_date"] == "2025-01-01 12:00:00"


class TestArchiver:
    def _make_cdx_response(self, rows):
        headers = ["timestamp", "original", "statuscode", "digest"]
        return [headers] + rows

    def _make_mock_response(self, status_code=200, json_data=None, text=None):
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is not None:
            resp.json.return_value = json_data
        resp.text = text if text else (json.dumps(json_data) if json_data else "")
        return resp

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_query_cdx_returns_results(self, mock_get):
        cdx_data = self._make_cdx_response([
            ["20250101120000", "https://example.com/openapi.json", "200", "abc123"],
            ["20250201120000", "https://example.com/openapi.json", "200", "def456"],
        ])
        mock_get.return_value = self._make_mock_response(json_data=cdx_data)

        archiver = Archiver(delay=0)
        results = archiver._query_cdx("https://example.com/openapi.json")
        assert len(results) == 2
        assert results[0]["timestamp"] == "20250101120000"
        assert results[1]["timestamp"] == "20250201120000"

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_query_cdx_empty(self, mock_get):
        mock_get.return_value = self._make_mock_response(json_data=[])
        archiver = Archiver(delay=0)
        results = archiver._query_cdx("https://example.com/openapi.json")
        assert results == []

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_query_cdx_only_headers(self, mock_get):
        cdx_data = self._make_cdx_response([])
        mock_get.return_value = self._make_mock_response(json_data=cdx_data)
        archiver = Archiver(delay=0)
        results = archiver._query_cdx("https://example.com/openapi.json")
        assert results == []

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_query_cdx_non_200(self, mock_get):
        mock_get.return_value = self._make_mock_response(status_code=500)
        archiver = Archiver(delay=0)
        results = archiver._query_cdx("https://example.com/openapi.json")
        assert results == []

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_query_cdx_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("Connection error")
        archiver = Archiver(delay=0)
        results = archiver._query_cdx("https://example.com/openapi.json")
        assert results == []

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_find_archived_specs(self, mock_get):
        cdx_data = self._make_cdx_response([
            ["20250101120000", "https://example.com/openapi.json", "200", "abc123"],
            ["20250601120000", "https://example.com/openapi.json", "200", "def456"],
        ])
        mock_get.return_value = self._make_mock_response(json_data=cdx_data)

        archiver = Archiver(delay=0)
        results = archiver.find_archived_specs(
            "https://example.com",
            spec_url="https://example.com/openapi.json",
        )
        assert len(results) == 2
        assert results[0].timestamp == "20250101120000"
        assert results[1].timestamp == "20250601120000"

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_find_archived_specs_dedup_across_urls(self, mock_get):
        cdx_data = self._make_cdx_response([
            ["20250101120000", "https://example.com/openapi.json", "200", "abc123"],
        ])
        mock_get.return_value = self._make_mock_response(json_data=cdx_data)

        archiver = Archiver(delay=0)
        results = archiver.find_archived_specs(
            "https://example.com",
            spec_url="https://example.com/openapi.json",
        )
        assert len(results) == 1

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_fetch_archived_spec_json(self, mock_get):
        spec = {"openapi": "3.0.3", "paths": {"/api/users": {"get": {"summary": "List"}}}}
        mock_get.return_value = self._make_mock_response(text=json.dumps(spec))

        archiver = Archiver(delay=0)
        result = archiver.fetch_archived_spec("20250101120000", "https://example.com/openapi.json")
        assert result is not None
        assert "openapi" in result
        assert "/api/users" in result["paths"]

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_fetch_archived_spec_yaml(self, mock_get):
        yaml_text = "openapi: 3.0.3\npaths:\n  /api/users:\n    get:\n      summary: List\n"
        mock_get.return_value = self._make_mock_response(text=yaml_text)

        archiver = Archiver(delay=0)
        result = archiver.fetch_archived_spec("20250101120000", "https://example.com/openapi.json")
        assert result is not None
        assert result["openapi"] == "3.0.3"

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_fetch_archived_spec_invalid(self, mock_get):
        mock_get.return_value = self._make_mock_response(text="<html>Not an API spec</html>")
        archiver = Archiver(delay=0)
        result = archiver.fetch_archived_spec("20250101120000", "https://example.com/openapi.json")
        assert result is None

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_fetch_archived_spec_non_200(self, mock_get):
        mock_get.return_value = self._make_mock_response(status_code=404)
        archiver = Archiver(delay=0)
        result = archiver.fetch_archived_spec("20250101120000", "https://example.com/openapi.json")
        assert result is None

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_fetch_archived_spec_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("Timeout")
        archiver = Archiver(delay=0)
        result = archiver.fetch_archived_spec("20250101120000", "https://example.com/openapi.json")
        assert result is None

    @patch.object(Archiver, "find_archived_specs")
    @patch.object(Archiver, "fetch_archived_spec")
    def test_fetch_all_archived_specs(self, mock_fetch, mock_find):
        archived1 = ArchivedSpec("20250101120000", "https://example.com/openapi.json", "200", "abc")
        archived2 = ArchivedSpec("20250601120000", "https://example.com/openapi.json", "200", "def")

        spec1 = {"openapi": "3.0.0", "paths": {"/api/v1/users": {"get": {}}}}
        spec2 = {"openapi": "3.0.3", "paths": {"/api/v1/users": {"get": {}}, "/api/v2/users": {"get": {}}}}

        archived1.spec_data = spec1
        archived2.spec_data = spec2

        mock_find.return_value = [archived1, archived2]
        mock_fetch.side_effect = [spec1, spec2]

        archiver = Archiver(delay=0)
        results = archiver.fetch_all_archived_specs(
            "https://example.com",
            spec_url="https://example.com/openapi.json",
        )

        assert len(results) == 2
        valid = [r for r in results if r.spec_data is not None]
        assert len(valid) == 2

    @patch.object(Archiver, "find_archived_specs")
    def test_fetch_all_archived_specs_none_found(self, mock_find):
        mock_find.return_value = []
        archiver = Archiver(delay=0)
        results = archiver.fetch_all_archived_specs("https://example.com")
        assert results == []

    def test_is_valid_spec_openapi(self):
        archiver = Archiver(delay=0)
        assert archiver._is_valid_spec({"openapi": "3.0.3", "paths": {}}) is True

    def test_is_valid_spec_swagger(self):
        archiver = Archiver(delay=0)
        assert archiver._is_valid_spec({"swagger": "2.0", "paths": {}}) is True

    def test_is_valid_spec_paths_only(self):
        archiver = Archiver(delay=0)
        assert archiver._is_valid_spec({"paths": {"/api": {}}}) is True

    def test_is_valid_spec_invalid(self):
        archiver = Archiver(delay=0)
        assert archiver._is_valid_spec({"foo": "bar"}) is False
        assert archiver._is_valid_spec("not a dict") is False
        assert archiver._is_valid_spec(None) is False

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_find_archived_specs_with_date_filters(self, mock_get):
        cdx_data = self._make_cdx_response([
            ["20250301120000", "https://example.com/openapi.json", "200", "abc"],
        ])
        mock_get.return_value = self._make_mock_response(json_data=cdx_data)

        archiver = Archiver(delay=0)
        results = archiver.find_archived_specs(
            "https://example.com",
            spec_url="https://example.com/openapi.json",
            from_date="20250101",
            to_date="20251231",
        )
        assert len(results) == 1

        call_args = mock_get.call_args
        params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert params["from"] == "20250101"
        assert params["to"] == "20251231"

    @patch("api_ghost_hunter.archiver.requests.Session.get")
    def test_find_archived_specs_uses_common_paths(self, mock_get):
        mock_get.return_value = self._make_mock_response(json_data=[])

        archiver = Archiver(delay=0)
        archiver.find_archived_specs("https://example.com")

        assert mock_get.call_count > 1
        called_urls = []
        for call in mock_get.call_args_list:
            params = call[1].get("params", {}) if call[1] else {}
            if "url" in params:
                called_urls.append(params["url"])
        assert any("openapi.json" in u for u in called_urls)
        assert any("swagger.json" in u for u in called_urls)

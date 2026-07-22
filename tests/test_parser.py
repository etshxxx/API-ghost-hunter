"""Tests for the OpenAPI and JS endpoint parsers."""
import json
import os
import pytest

from api_ghost_hunter.parser import OpenAPIParser, JSParser, VALID_METHODS


SAMPLE_SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples",
    "sample_openapi.json",
)


def load_sample_spec():
    with open(SAMPLE_SPEC_PATH, "r") as f:
        return json.load(f)


class TestOpenAPIParser:
    def test_parse_sample_spec(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec, "https://api.example.com/openapi.json")
        assert len(endpoints) > 0

    def test_parse_returns_endpoints_with_correct_methods(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        methods = {ep.method for ep in endpoints}
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods
        assert "PUT" in methods
        assert "PATCH" in methods

    def test_parse_paths(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/users" in paths
        assert "/api/v1/users/{user_id}" in paths
        assert "/api/v1/products" in paths
        assert "/health" in paths

    def test_parse_endpoint_key_format(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        keys = {ep.key for ep in endpoints}
        assert "GET /api/v1/users" in keys
        assert "POST /api/v1/users" in keys
        assert "DELETE /api/v1/users/{user_id}" in keys

    def test_parse_security_from_endpoint(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        users_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users")
        assert users_get.requires_auth is True
        assert len(users_get.security) > 0

    def test_parse_security_from_global(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        products_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/products")
        assert products_get.requires_auth is True

    def test_parse_no_security_override(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        logs_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/admin/logs")
        assert logs_get.requires_auth is False
        assert logs_get.security == []

    def test_parse_export_no_security_override(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        export_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users/export")
        assert export_get.requires_auth is False

    def test_parse_deprecated_flag(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        export_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users/export")
        assert export_get.deprecated is True

    def test_parse_tags(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        admin_config = next(ep for ep in endpoints if ep.key == "GET /api/v1/admin/config")
        assert "admin" in admin_config.tags

    def test_parse_summary_and_description(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        users_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users")
        assert users_get.summary == "List all users"
        assert "paginated list" in users_get.description

    def test_parse_parameters(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        users_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users")
        assert len(users_get.parameters) == 2
        param_names = {p["name"] for p in users_get.parameters}
        assert "page" in param_names
        assert "limit" in param_names

    def test_parse_request_body(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        users_post = next(ep for ep in endpoints if ep.key == "POST /api/v1/users")
        assert users_post.request_body is not None
        assert "content" in users_post.request_body

    def test_parse_responses(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec)
        users_get = next(ep for ep in endpoints if ep.key == "GET /api/v1/users")
        assert "200" in users_get.responses
        assert "401" in users_get.responses

    def test_parse_source(self):
        spec = load_sample_spec()
        endpoints = OpenAPIParser.parse(spec, "https://api.example.com/openapi.json")
        for ep in endpoints:
            assert ep.source == "openapi"

    def test_get_spec_version_openapi(self):
        spec = load_sample_spec()
        version = OpenAPIParser.get_spec_version(spec)
        assert version == "OpenAPI 3.0.3"

    def test_get_spec_version_swagger(self):
        spec = {"swagger": "2.0", "paths": {}}
        version = OpenAPIParser.get_spec_version(spec)
        assert version == "Swagger 2.0"

    def test_get_spec_version_unknown(self):
        spec = {"paths": {}}
        version = OpenAPIParser.get_spec_version(spec)
        assert version == "Unknown"

    def test_parse_empty_spec(self):
        endpoints = OpenAPIParser.parse({"paths": {}})
        assert endpoints == []

    def test_parse_skips_non_http_methods(self):
        spec = {
            "paths": {
                "/api/test": {
                    "get": {"summary": "Test"},
                    "x-custom": {"foo": "bar"},
                    "parameters": [{"name": "id", "in": "query"}],
                }
            }
        }
        endpoints = OpenAPIParser.parse(spec)
        assert len(endpoints) == 1
        assert endpoints[0].method == "GET"

    def test_parse_all_valid_methods(self):
        spec = {"paths": {}}
        for method in VALID_METHODS:
            spec["paths"][f"/api/{method.lower()}"] = {
                method.lower(): {"summary": f"Test {method}"}
            }
        endpoints = OpenAPIParser.parse(spec)
        methods = {ep.method for ep in endpoints}
        assert methods == VALID_METHODS

    def test_parse_minimal_spec(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/api/items": {
                    "get": {"summary": "List items"},
                }
            },
        }
        endpoints = OpenAPIParser.parse(spec)
        assert len(endpoints) == 1
        assert endpoints[0].key == "GET /api/items"


class TestJSParser:
    def test_parse_fetch_calls(self):
        js = """
        fetch('/api/v1/users')
        fetch("/api/v1/products")
        fetch(`/api/v1/orders`)
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/users" in paths
        assert "/api/v1/products" in paths
        assert "/api/v1/orders" in paths

    def test_parse_axios_calls(self):
        js = """
        axios.get('/api/v1/users')
        axios.post('/api/v1/users')
        axios.delete('/api/v1/users/1')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/users" in paths

    def test_parse_xmlhttp_open(self):
        js = """
        xhr.open('GET', '/api/v1/data')
        xhr.open('POST', '/api/v1/submit')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        keys = {ep.key for ep in endpoints}
        assert "GET /api/v1/data" in keys
        assert "POST /api/v1/submit" in keys

    def test_parse_url_pattern(self):
        js = """
        var config = {url: '/api/v1/settings'}
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/settings" in paths

    def test_parse_deduplication(self):
        js = """
        fetch('/api/v1/users')
        fetch('/api/v1/users')
        axios.get('/api/v1/users')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        users_endpoints = [ep for ep in endpoints if ep.path == "/api/v1/users"]
        assert len(users_endpoints) == 1

    def test_parse_filters_static_assets(self):
        js = """
        fetch('/api/v1/users')
        fetch('/static/main.js')
        fetch('/assets/style.css')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/users" in paths
        assert "/static/main.js" not in paths
        assert "/assets/style.css" not in paths

    def test_parse_requires_api_keyword(self):
        js = """
        fetch('/random/path')
        fetch('/api/v1/valid')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/valid" in paths
        assert "/random/path" not in paths

    def test_parse_source_is_js(self):
        js = "fetch('/api/v1/test')"
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        assert endpoints[0].source == "js"

    def test_parse_empty_js(self):
        endpoints = JSParser.parse("", "https://example.com/app.js")
        assert endpoints == []

    def test_parse_no_api_paths(self):
        js = """
        fetch('/static/image.png')
        console.log('hello')
        """
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        assert endpoints == []

    def test_parse_rest_keyword(self):
        js = "fetch('/rest/v1/items')"
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        assert any(ep.path == "/rest/v1/items" for ep in endpoints)

    def test_parse_graphql_keyword(self):
        js = "fetch('/graphql')"
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        assert any(ep.path == "/graphql" for ep in endpoints)

    def test_parse_description_includes_source(self):
        js = "fetch('/api/v1/test')"
        endpoints = JSParser.parse(js, "https://example.com/app.js")
        assert "https://example.com/app.js" in endpoints[0].description

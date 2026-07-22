import re
import logging
from typing import List, Dict

from .models import Endpoint

logger = logging.getLogger("api-ghost-hunter")

VALID_METHODS = {
    "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"
}


class OpenAPIParser:
    @staticmethod
    def parse(spec: Dict, source_url: str = "") -> List[Endpoint]:
        endpoints = []
        paths = spec.get("paths", {})

        global_security = spec.get("security", [])

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue

            for method, details in methods.items():
                method = method.upper()
                if method not in VALID_METHODS:
                    continue
                if not isinstance(details, dict):
                    continue

                security = details.get(
                    "security",
                    global_security if global_security else [],
                )

                endpoint = Endpoint(
                    method=method,
                    path=path,
                    summary=details.get("summary", ""),
                    description=details.get("description", ""),
                    parameters=details.get("parameters", []),
                    request_body=details.get("requestBody"),
                    responses=details.get("responses", {}),
                    security=security,
                    tags=details.get("tags", []),
                    deprecated=details.get("deprecated", False),
                    source="openapi",
                )
                endpoints.append(endpoint)

        logger.info(f"Parsed {len(endpoints)} endpoints from OpenAPI spec")
        return endpoints

    @staticmethod
    def get_spec_version(spec: Dict) -> str:
        if "openapi" in spec:
            return f"OpenAPI {spec['openapi']}"
        elif "swagger" in spec:
            return f"Swagger {spec['swagger']}"
        return "Unknown"


class JSParser:
    PATTERNS = [
        re.compile(r'fetch\s*\(\s*["\'`]([^"\'`]+)["\'`]', re.IGNORECASE),
        re.compile(r'axios\.\w+\s*\(\s*["\'`]([^"\'`]+)["\'`]', re.IGNORECASE),
        re.compile(r'\.open\s*\(\s*["\'`](\w+)["\'`]\s*,\s*["\'`]([^"\'`]+)["\'`]', re.IGNORECASE),
        re.compile(r'url\s*:\s*["\'`]([^"\'`]+)["\'`]', re.IGNORECASE),
        re.compile(r'["\'`](/api/[^"\'`]+)["\'`]', re.IGNORECASE),
        re.compile(r'["\'`](/v\d+/[^"\'`]+)["\'`]', re.IGNORECASE),
    ]

    @staticmethod
    def parse(js_content: str, source_url: str = "") -> List[Endpoint]:
        endpoints = []
        seen = set()

        for pattern in JSParser.PATTERNS:
            matches = pattern.findall(js_content)
            for match in matches:
                if isinstance(match, tuple):
                    method, path = match[0].upper(), match[1]
                else:
                    method, path = "GET", match

                if not JSParser._is_api_path(path):
                    continue

                if method not in VALID_METHODS:
                    method = "GET"

                key = f"{method} {path}"
                if key in seen:
                    continue
                seen.add(key)

                endpoint = Endpoint(
                    method=method,
                    path=path,
                    summary="",
                    description=f"Extracted from JS: {source_url}",
                    source="js",
                )
                endpoints.append(endpoint)

        logger.info(f"Extracted {len(endpoints)} endpoints from JS files")
        return endpoints

    @staticmethod
    def _is_api_path(path: str) -> bool:
        if not path or len(path) < 2:
            return False
        if not path.startswith("/"):
            return False
        static_exts = [
            ".js", ".css", ".png", ".jpg", ".jpeg", ".gif",
            ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map",
        ]
        if any(path.endswith(ext) for ext in static_exts):
            return False
        api_keywords = ["/api/", "/v1/", "/v2/", "/v3/", "/rest/", "/graphql"]
        if any(kw in path.lower() for kw in api_keywords):
            return True
        if "{" in path and "}" in path:
            return True
        return False

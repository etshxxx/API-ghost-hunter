import re
import time
import logging
from typing import List, Optional, Dict

import requests

from .models import Endpoint, GhostEndpoint
from .utils import normalize_url

logger = logging.getLogger("api-ghost-hunter")


class Analyzer:
    def __init__(
        self,
        timeout: int = 15,
        verify_ssl: bool = True,
        user_agent: str = "API-Ghost-Hunter/1.0",
        delay: float = 0.5,
        auth_header: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.delay = delay
        self.auth_header = auth_header
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        if headers:
            self.session.headers.update(headers)
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def probe_endpoint(self, base_url: str, endpoint: Endpoint) -> GhostEndpoint:
        url = self._build_url(base_url, endpoint.path)
        method = endpoint.method.lower()

        start_time = time.time()
        try:
            resp = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=False,
                json=self._build_body(endpoint),
            )
            elapsed = time.time() - start_time

            still_alive = resp.status_code < 400
            auth_bypassed = self._check_auth_bypass(resp, endpoint)
            snippet = resp.text[:500] if resp.text else ""

            ghost = GhostEndpoint(
                endpoint=endpoint,
                status_code=resp.status_code,
                response_length=len(resp.content),
                response_time=round(elapsed, 3),
                still_alive=still_alive,
                auth_bypassed=auth_bypassed,
                response_snippet=snippet,
            )

            if self.auth_header and still_alive and endpoint.requires_auth:
                ghost = self._probe_with_auth(base_url, endpoint, ghost)

            return ghost
        except requests.RequestException as e:
            elapsed = time.time() - start_time
            return GhostEndpoint(
                endpoint=endpoint,
                status_code=0,
                response_length=0,
                response_time=round(elapsed, 3),
                still_alive=False,
                auth_bypassed=False,
                error=str(e),
            )
        finally:
            if self.delay > 0:
                time.sleep(self.delay)

    def _probe_with_auth(
        self, base_url: str, endpoint: Endpoint, ghost_no_auth: GhostEndpoint
    ) -> GhostEndpoint:
        url = self._build_url(base_url, endpoint.path)
        method = endpoint.method.lower()

        auth_headers = {}
        if ":" in self.auth_header:
            key, value = self.auth_header.split(":", 1)
            auth_headers[key.strip()] = value.strip()
        else:
            auth_headers["Authorization"] = self.auth_header

        try:
            resp = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=False,
                headers=auth_headers,
                json=self._build_body(endpoint),
            )
            ghost_no_auth.probed_with_auth = True
            ghost_no_auth.auth_status_code = resp.status_code
        except requests.RequestException as e:
            logger.debug(f"Auth probe failed for {endpoint.key}: {e}")

        return ghost_no_auth

    def probe_endpoints(
        self, base_url: str, endpoints: List[Endpoint]
    ) -> List[GhostEndpoint]:
        results = []
        for i, ep in enumerate(endpoints):
            logger.info(f"Probing [{i + 1}/{len(endpoints)}] {ep.key}")
            result = self.probe_endpoint(base_url, ep)
            results.append(result)

            if result.still_alive:
                status = f"ALIVE ({result.status_code})"
            else:
                status = f"DEAD ({result.status_code})"

            if result.auth_bypassed:
                status += " - AUTH BYPASS!"

            logger.info(f"  -> {status}")

        return results

    def find_ghosts(
        self, base_url: str, removed_endpoints: List[Endpoint]
    ) -> List[GhostEndpoint]:
        logger.info(
            f"Hunting for {len(removed_endpoints)} ghost endpoints..."
        )
        return self.probe_endpoints(base_url, removed_endpoints)

    def _build_url(self, base_url: str, path: str) -> str:
        base_url = normalize_url(base_url)
        clean_path = re.sub(r"\{[^}]+\}", "1", path)
        return base_url + clean_path

    def _build_body(self, endpoint: Endpoint) -> Optional[Dict]:
        if endpoint.method.upper() not in ("POST", "PUT", "PATCH"):
            return None
        if endpoint.request_body:
            content = endpoint.request_body.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})
            return self._generate_example_body(schema)
        return {}

    def _generate_example_body(self, schema: Dict) -> Dict:
        if not schema:
            return {}
        example = {}
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "string")
            if prop_type == "string":
                example[prop_name] = "test"
            elif prop_type == "integer":
                example[prop_name] = 1
            elif prop_type == "boolean":
                example[prop_name] = True
            elif prop_type == "array":
                example[prop_name] = []
            elif prop_type == "object":
                example[prop_name] = {}
            else:
                example[prop_name] = "test"
        return example

    def _check_auth_bypass(
        self, response: requests.Response, endpoint: Endpoint
    ) -> bool:
        if not endpoint.requires_auth:
            return False
        if response.status_code in (401, 403):
            return False
        if response.status_code < 400:
            return True
        return False

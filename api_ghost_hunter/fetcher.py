import json
import logging
from typing import Optional, Dict, List

import requests
import yaml
from bs4 import BeautifulSoup

from .utils import normalize_url, merge_urls

logger = logging.getLogger("api-ghost-hunter")

COMMON_SPEC_PATHS = [
    "/swagger.json",
    "/swagger/v1/swagger.json",
    "/swagger/v2/swagger.json",
    "/api/swagger.json",
    "/api-docs",
    "/api/docs",
    "/openapi.json",
    "/api/openapi.json",
    "/v1/swagger.json",
    "/v2/swagger.json",
    "/v3/swagger.json",
    "/api/v1/swagger.json",
    "/api/v2/swagger.json",
    "/api/v3/swagger.json",
    "/api/v1/openapi.json",
    "/api/v2/openapi.json",
    "/api/v3/openapi.json",
    "/apidocs",
    "/api-docs/json",
    "/swagger.yaml",
    "/openapi.yaml",
    "/api/swagger.yaml",
    "/api/openapi.yaml",
    "/spec",
    "/api/spec",
    "/redoc",
    "/api-docs/swagger.json",
    "/api-docs/openapi.json",
    "/docs/swagger.json",
    "/docs/openapi.json",
    "/api/swagger/v1/swagger.json",
    "/api/swagger/v2/swagger.json",
    "/swagger-ui/swagger.json",
    "/swagger-ui/v2/swagger.json",
    "/swagger-resources",
    "/swagger-resources/configuration/ui",
    "/v1/api-docs",
    "/v2/api-docs",
    "/v3/api-docs",
    "/api/v1/api-docs",
    "/api/v2/api-docs",
    "/api/v3/api-docs",
    "/openapi/v1",
    "/openapi/v2",
    "/rest-api-docs",
    "/api/spec.json",
    "/api-docs/v2",
    "/api/schema",
    "/api/v1/schema",
    "/graphql",
    "/api/graphql",
    "/.well-known/openapi.json",
    "/.well-known/schema.json",
]


class Fetcher:
    def __init__(
        self,
        timeout: int = 15,
        verify_ssl: bool = True,
        user_agent: str = "API-Ghost-Hunter/1.0",
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        if headers:
            self.session.headers.update(headers)
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def fetch_url(self, url: str) -> Optional[requests.Response]:
        try:
            resp = self.session.get(
                url, timeout=self.timeout, verify=self.verify_ssl
            )
            return resp
        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None

    def fetch_spec(self, url: str) -> Optional[Dict]:
        resp = self.fetch_url(url)
        if resp is None or resp.status_code != 200:
            return None
        content = resp.text.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        try:
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                return data
        except yaml.YAMLError:
            pass
        return None

    def discover_spec(self, base_url: str) -> Optional[Dict]:
        base_url = normalize_url(base_url)
        logger.info(f"Discovering API spec for {base_url}...")

        for path in COMMON_SPEC_PATHS:
            url = base_url + path
            logger.debug(f"Trying {url}")
            spec = self.fetch_spec(url)
            if spec and self._is_valid_spec(spec):
                logger.info(f"Found API spec at {url}")
                return {"spec": spec, "url": url}

        spec = self._find_spec_in_html(base_url)
        if spec:
            return spec

        return None

    def discover_all_specs(self, base_url: str) -> List[Dict]:
        base_url = normalize_url(base_url)
        logger.info(f"Discovering all API specs for {base_url}...")
        found = []
        seen_urls = set()

        for path in COMMON_SPEC_PATHS:
            url = base_url + path
            if url in seen_urls:
                continue
            spec = self.fetch_spec(url)
            if spec and self._is_valid_spec(spec):
                logger.info(f"Found API spec at {url}")
                found.append({"spec": spec, "url": url})
                seen_urls.add(url)

        html_spec = self._find_spec_in_html(base_url)
        if html_spec and html_spec["url"] not in seen_urls:
            found.append(html_spec)

        return found

    def _is_valid_spec(self, data: Dict) -> bool:
        if not isinstance(data, dict):
            return False
        if "openapi" in data:
            return True
        if "swagger" in data:
            return True
        if "paths" in data and isinstance(data["paths"], dict):
            return True
        return False

    def _find_spec_in_html(self, base_url: str) -> Optional[Dict]:
        resp = self.fetch_url(base_url)
        if resp is None or resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.find_all("link"):
            href = link.get("href", "")
            if any(
                kw in href.lower()
                for kw in ["swagger", "openapi", "api-docs", "api-spec"]
            ):
                url = merge_urls(base_url, href)
                spec = self.fetch_spec(url)
                if spec and self._is_valid_spec(spec):
                    logger.info(f"Found API spec at {url} (from HTML link)")
                    return {"spec": spec, "url": url}

        for script in soup.find_all("script"):
            src = script.get("src", "")
            if any(kw in src.lower() for kw in ["swagger", "openapi"]):
                url = merge_urls(base_url, src)
                spec = self.fetch_spec(url)
                if spec and self._is_valid_spec(spec):
                    logger.info(f"Found API spec at {url} (from script tag)")
                    return {"spec": spec, "url": url}

        return None

    def fetch_js_files(self, base_url: str) -> List[Dict]:
        base_url = normalize_url(base_url)
        resp = self.fetch_url(base_url)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        js_files = []

        for script in soup.find_all("script"):
            src = script.get("src", "")
            if src and src.endswith(".js"):
                url = merge_urls(base_url, src)
                js_resp = self.fetch_url(url)
                if js_resp and js_resp.status_code == 200:
                    js_files.append({"url": url, "content": js_resp.text})

        logger.info(f"Found {len(js_files)} JavaScript files")
        return js_files

import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import requests
import yaml

from .utils import normalize_url
from .fetcher import COMMON_SPEC_PATHS

logger = logging.getLogger("api-ghost-hunter")


class ArchivedSpec:
    def __init__(
        self,
        timestamp: str,
        original_url: str,
        status_code: str,
        digest: str,
    ):
        self.timestamp = timestamp
        self.original_url = original_url
        self.status_code = status_code
        self.digest = digest
        self.spec_data: Optional[Dict] = None
        self.endpoints_count: int = 0
        self.spec_version: str = ""
        self.error: str = ""

    @property
    def formatted_date(self) -> str:
        if not self.timestamp or len(self.timestamp) < 8:
            return self.timestamp
        try:
            dt = datetime.strptime(self.timestamp[:14], "%Y%m%d%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                dt = datetime.strptime(self.timestamp[:8], "%Y%m%d")
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return self.timestamp

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "original_url": self.original_url,
            "status_code": self.status_code,
            "digest": self.digest,
            "formatted_date": self.formatted_date,
            "endpoints_count": self.endpoints_count,
            "spec_version": self.spec_version,
            "error": self.error,
        }


class Archiver:
    CDX_API = "https://web.archive.org/cdx/search/cdx"
    WEB_BASE = "https://web.archive.org/web"

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        user_agent: str = "API-Ghost-Hunter/1.0",
        delay: float = 1.0,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def find_archived_specs(
        self,
        target_url: str,
        spec_url: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArchivedSpec]:
        target_url = normalize_url(target_url)

        urls_to_check = set()
        if spec_url:
            urls_to_check.add(spec_url)

        for path in COMMON_SPEC_PATHS:
            urls_to_check.add(target_url + path)

        all_results: Dict[str, ArchivedSpec] = {}

        for url in sorted(urls_to_check):
            logger.info(f"Querying Wayback Machine for: {url}")
            results = self._query_cdx(
                url, from_date=from_date, to_date=to_date, limit=limit
            )
            for row in results:
                key = f"{row.get('timestamp', '')}_{row.get('digest', '')}"
                if key not in all_results:
                    archived = ArchivedSpec(
                        timestamp=row.get("timestamp", ""),
                        original_url=row.get("original", url),
                        status_code=row.get("statuscode", ""),
                        digest=row.get("digest", ""),
                    )
                    all_results[key] = archived
            if self.delay > 0:
                time.sleep(self.delay)

        sorted_results = sorted(
            all_results.values(), key=lambda x: x.timestamp
        )
        logger.info(
            f"Found {len(sorted_results)} unique archived specs "
            f"across {len(urls_to_check)} candidate URLs"
        )
        return sorted_results

    def _query_cdx(
        self,
        url: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        params = {
            "url": url,
            "output": "json",
            "fl": "timestamp,original,statuscode,digest",
            "collapse": "digest",
            "filter": "statuscode:200",
            "limit": str(limit),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        try:
            resp = self.session.get(
                self.CDX_API,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            if resp.status_code != 200:
                logger.debug(f"CDX API returned {resp.status_code} for {url}")
                return []

            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return []

            headers = data[0]
            rows = []
            for row in data[1:]:
                row_dict = dict(zip(headers, row))
                rows.append(row_dict)

            logger.info(f"  CDX returned {len(rows)} archived versions")
            return rows
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            logger.debug(f"CDX query failed for {url}: {e}")
            return []

    def fetch_archived_spec(
        self, timestamp: str, original_url: str
    ) -> Optional[Dict]:
        url = f"{self.WEB_BASE}/{timestamp}id_/{original_url}"
        logger.debug(f"Fetching archived spec from: {url}")

        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                logger.debug(f"Archive fetch returned {resp.status_code}")
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

            logger.debug("Archived content is not valid JSON or YAML")
            return None
        except requests.RequestException as e:
            logger.debug(f"Failed to fetch archived spec: {e}")
            return None

    def fetch_all_archived_specs(
        self,
        target_url: str,
        spec_url: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
    ) -> List[ArchivedSpec]:
        archived_specs = self.find_archived_specs(
            target_url,
            spec_url=spec_url,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

        if not archived_specs:
            logger.info("No archived specs found on Wayback Machine")
            return []

        logger.info(
            f"Fetching and parsing {len(archived_specs)} archived specs..."
        )

        for i, archived in enumerate(archived_specs, 1):
            logger.info(
                f"  [{i}/{len(archived_specs)}] "
                f"Fetching {archived.formatted_date}..."
            )
            spec_data = self.fetch_archived_spec(
                archived.timestamp, archived.original_url
            )

            if spec_data and self._is_valid_spec(spec_data):
                archived.spec_data = spec_data
                if "openapi" in spec_data:
                    archived.spec_version = f"OpenAPI {spec_data['openapi']}"
                elif "swagger" in spec_data:
                    archived.spec_version = f"Swagger {spec_data['swagger']}"
                else:
                    archived.spec_version = "Unknown"
            else:
                archived.error = "Failed to parse or invalid spec"

            if self.delay > 0:
                time.sleep(self.delay)

        valid = [a for a in archived_specs if a.spec_data is not None]
        logger.info(
            f"Successfully parsed {len(valid)}/{len(archived_specs)} archived specs"
        )
        return archived_specs

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

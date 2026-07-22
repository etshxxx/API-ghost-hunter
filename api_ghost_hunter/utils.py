import os
import re
import json
import logging
from datetime import datetime
from typing import Dict
from urllib.parse import urljoin

from rich.logging import RichHandler


def setup_logger(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    return logging.getLogger("api-ghost-hunter")


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def parse_headers(headers_input: str) -> Dict[str, str]:
    if not headers_input:
        return {}
    if os.path.isfile(headers_input):
        with open(headers_input, "r") as f:
            return json.load(f)
    return json.loads(headers_input)


def format_timestamp(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts


def format_archive_timestamp(ts: str) -> str:
    if not ts or len(ts) < 8:
        return ts
    try:
        dt = datetime.strptime(ts[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(ts[:8], "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return ts


def merge_urls(base_url: str, relative_url: str) -> str:
    if relative_url.startswith(("http://", "https://")):
        return relative_url
    if relative_url.startswith("//"):
        return "https:" + relative_url
    if not relative_url.startswith("/"):
        relative_url = "/" + relative_url
    return base_url.rstrip("/") + relative_url

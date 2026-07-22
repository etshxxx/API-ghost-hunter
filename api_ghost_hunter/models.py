from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
import json


@dataclass
class Endpoint:
    method: str
    path: str
    summary: str = ""
    description: str = ""
    parameters: List[Dict] = field(default_factory=list)
    request_body: Optional[Dict] = None
    responses: Dict = field(default_factory=dict)
    security: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    deprecated: bool = False
    source: str = "openapi"

    @property
    def key(self) -> str:
        return f"{self.method.upper()} {self.path}"

    @property
    def requires_auth(self) -> bool:
        return len(self.security) > 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Endpoint":
        known_fields = {
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        }
        return cls(**known_fields)

    def diff(self, other: "Endpoint") -> Dict[str, Any]:
        changes = {}
        for field_name in [
            "summary", "description", "parameters", "request_body",
            "responses", "security", "tags", "deprecated"
        ]:
            if getattr(self, field_name) != getattr(other, field_name):
                changes[field_name] = {
                    "old": getattr(self, field_name),
                    "new": getattr(other, field_name),
                }
        return changes


@dataclass
class Snapshot:
    target_url: str
    timestamp: str
    endpoints: List[Endpoint] = field(default_factory=list)
    spec_url: str = ""
    spec_version: str = ""
    source: str = "openapi"
    archive_timestamp: str = ""

    def to_dict(self) -> Dict:
        return {
            "target_url": self.target_url,
            "timestamp": self.timestamp,
            "spec_url": self.spec_url,
            "spec_version": self.spec_version,
            "source": self.source,
            "archive_timestamp": self.archive_timestamp,
            "endpoint_count": len(self.endpoints),
            "endpoints": [ep.to_dict() for ep in self.endpoints],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> "Snapshot":
        endpoints = [Endpoint.from_dict(ep) for ep in data.get("endpoints", [])]
        return cls(
            target_url=data["target_url"],
            timestamp=data["timestamp"],
            endpoints=endpoints,
            spec_url=data.get("spec_url", ""),
            spec_version=data.get("spec_version", ""),
            source=data.get("source", "openapi"),
            archive_timestamp=data.get("archive_timestamp", ""),
        )

    def get_endpoint_map(self) -> Dict[str, Endpoint]:
        return {ep.key: ep for ep in self.endpoints}


@dataclass
class GhostEndpoint:
    endpoint: Endpoint
    status_code: int
    response_length: int
    response_time: float
    still_alive: bool
    auth_bypassed: bool
    error: str = ""
    response_snippet: str = ""
    probed_with_auth: bool = False
    auth_status_code: int = 0

    def to_dict(self) -> Dict:
        return {
            "endpoint": self.endpoint.to_dict(),
            "status_code": self.status_code,
            "response_length": self.response_length,
            "response_time": self.response_time,
            "still_alive": self.still_alive,
            "auth_bypassed": self.auth_bypassed,
            "error": self.error,
            "response_snippet": self.response_snippet,
            "probed_with_auth": self.probed_with_auth,
            "auth_status_code": self.auth_status_code,
        }


@dataclass
class DiffResult:
    old_snapshot: Snapshot
    new_snapshot: Snapshot
    added: List[Endpoint] = field(default_factory=list)
    removed: List[Endpoint] = field(default_factory=list)
    modified: List[Dict] = field(default_factory=list)
    unchanged: List[Endpoint] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.removed) + len(self.modified)

    def to_dict(self) -> Dict:
        return {
            "old_snapshot": {
                "target_url": self.old_snapshot.target_url,
                "timestamp": self.old_snapshot.timestamp,
                "archive_timestamp": self.old_snapshot.archive_timestamp,
                "endpoint_count": len(self.old_snapshot.endpoints),
            },
            "new_snapshot": {
                "target_url": self.new_snapshot.target_url,
                "timestamp": self.new_snapshot.timestamp,
                "archive_timestamp": self.new_snapshot.archive_timestamp,
                "endpoint_count": len(self.new_snapshot.endpoints),
            },
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "modified": len(self.modified),
                "unchanged": len(self.unchanged),
                "total_changes": self.total_changes,
            },
            "added": [ep.to_dict() for ep in self.added],
            "removed": [ep.to_dict() for ep in self.removed],
            "modified": self.modified,
            "unchanged_count": len(self.unchanged),
        }

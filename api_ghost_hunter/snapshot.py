import os
import json
import logging
from typing import List, Optional

from .models import Snapshot
from .utils import sanitize_filename

logger = logging.getLogger("api-ghost-hunter")

DEFAULT_SNAPSHOT_DIR = "snapshots"


class SnapshotManager:
    def __init__(self, snapshot_dir: str = DEFAULT_SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        os.makedirs(snapshot_dir, exist_ok=True)

    def save(self, snapshot: Snapshot) -> str:
        target_name = sanitize_filename(
            snapshot.target_url
            .replace("https://", "")
            .replace("http://", "")
        )
        timestamp_clean = snapshot.timestamp.replace(":", "-").replace(".", "-")
        filename = f"{target_name}_{timestamp_clean}.json"
        filepath = os.path.join(self.snapshot_dir, filename)

        with open(filepath, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        logger.info(f"Snapshot saved to {filepath}")
        return filepath

    def load(self, filepath: str) -> Optional[Snapshot]:
        if not os.path.isabs(filepath):
            candidate = os.path.join(self.snapshot_dir, filepath)
            if os.path.exists(candidate):
                filepath = candidate
            elif not os.path.exists(filepath):
                return None

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return Snapshot.from_dict(data)
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            logger.error(f"Failed to load snapshot {filepath}: {e}")
            return None

    def list_snapshots(self, target: str = "") -> List[dict]:
        snapshots = []
        if not os.path.exists(self.snapshot_dir):
            return snapshots

        for filename in sorted(os.listdir(self.snapshot_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.snapshot_dir, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                if target and target not in data.get("target_url", ""):
                    continue
                snapshots.append(
                    {
                        "filename": filename,
                        "filepath": filepath,
                        "target_url": data.get("target_url", ""),
                        "timestamp": data.get("timestamp", ""),
                        "endpoint_count": data.get("endpoint_count", 0),
                        "spec_url": data.get("spec_url", ""),
                        "source": data.get("source", ""),
                        "archive_timestamp": data.get("archive_timestamp", ""),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return snapshots

    def get_latest(self, target: str = "") -> Optional[Snapshot]:
        snapshots = self.list_snapshots(target)
        if not snapshots:
            return None
        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return self.load(snapshots[0]["filepath"])

    def get_previous(self, target: str, current_timestamp: str) -> Optional[Snapshot]:
        snapshots = self.list_snapshots(target)
        if not snapshots:
            return None
        previous = [s for s in snapshots if s["timestamp"] < current_timestamp]
        if not previous:
            return None
        previous.sort(key=lambda x: x["timestamp"], reverse=True)
        return self.load(previous[0]["filepath"])

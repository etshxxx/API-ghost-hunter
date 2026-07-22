import logging
from typing import List, Dict

from .models import Snapshot, DiffResult

logger = logging.getLogger("api-ghost-hunter")


class Differ:
    @staticmethod
    def compare(old: Snapshot, new: Snapshot) -> DiffResult:
        old_map = old.get_endpoint_map()
        new_map = new.get_endpoint_map()

        old_keys = set(old_map.keys())
        new_keys = set(new_map.keys())

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        added = [new_map[k] for k in sorted(added_keys)]
        removed = [old_map[k] for k in sorted(removed_keys)]

        modified = []
        unchanged = []

        for key in sorted(common_keys):
            old_ep = old_map[key]
            new_ep = new_map[key]
            changes = old_ep.diff(new_ep)
            if changes:
                modified.append(
                    {
                        "endpoint": key,
                        "changes": changes,
                        "old_endpoint": old_ep.to_dict(),
                        "new_endpoint": new_ep.to_dict(),
                    }
                )
            else:
                unchanged.append(new_ep)

        logger.info(
            f"Diff complete: {len(added)} added, {len(removed)} removed, "
            f"{len(modified)} modified, {len(unchanged)} unchanged"
        )

        return DiffResult(
            old_snapshot=old,
            new_snapshot=new,
            added=added,
            removed=removed,
            modified=modified,
            unchanged=unchanged,
        )

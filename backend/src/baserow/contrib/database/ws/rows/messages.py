from typing import Any, Dict, List, Optional

from baserow.contrib.database.table.models import GeneratedTableModel


class RealtimeRowMessages:
    """
    A collection of functions which construct the payloads for the realtime
    websocket messages related to rows.
    """

    @staticmethod
    def rows_deleted(
        table_id: int, serialized_rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "type": "rows_deleted",
            "table_id": table_id,
            "row_ids": [r["id"] for r in serialized_rows],
            "rows": serialized_rows,
        }

    @staticmethod
    def rows_created(
        table_id: int,
        serialized_rows: List[Dict[str, Any]],
        metadata: Dict[int, Dict[str, Any]],
        before: Optional[GeneratedTableModel],
    ) -> Dict[str, Any]:
        return {
            "type": "rows_created",
            "table_id": table_id,
            "rows": serialized_rows,
            # Keys must be stringified here: this payload is sent to the channel
            # layer, and channels_redis unpacks it with msgpack's
            # strict_map_key=True, which rejects int map keys.
            "metadata": {str(k): v for k, v in metadata.items()},
            "before_row_id": before.id if before else None,
        }

    @staticmethod
    def rows_updated(
        table_id: int,
        serialized_rows_before_update: List[Dict[str, Any]],
        serialized_rows: List[Dict[str, Any]],
        metadata: Dict[int, Dict[str, Any]],
        updated_field_ids: List[int],
    ) -> Dict[str, Any]:
        return {
            "type": "rows_updated",
            "table_id": table_id,
            # The web-frontend expects a serialized version of the rows before it
            # was updated in order to estimate what position the row had in the
            # view.
            "rows_before_update": serialized_rows_before_update,
            "rows": serialized_rows,
            # Keys must be stringified here: this payload is sent to the channel
            # layer, and channels_redis unpacks it with msgpack's
            # strict_map_key=True, which rejects int map keys.
            "metadata": {str(k): v for k, v in metadata.items()},
            "updated_field_ids": updated_field_ids,
        }

    @staticmethod
    def row_orders_recalculated(table_id: int) -> Dict[str, Any]:
        return {
            "type": "row_orders_recalculated",
            "table_id": table_id,
        }

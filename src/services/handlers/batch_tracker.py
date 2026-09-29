import threading
import time
from typing import Dict, List, Optional, Tuple
from uuid import UUID


class BatchTracker:
    """
    Thread-safe in-memory tracker for the most recent transaction batch created by each user.
    Enables bare /undo to atomically revert an entire batch of transactions created in a single message.
    """
    _lock = threading.Lock()
    # Maps user_uuid -> (timestamp, list_of_transaction_uuids)
    _batches: Dict[UUID, Tuple[float, List[UUID]]] = {}
    _TTL_SECONDS: float = 3600.0  # Batches expire after 1 hour

    @classmethod
    def set_last_batch(cls, user_uuid: UUID, transaction_ids: List[UUID]) -> None:
        """Stores the list of transaction IDs created in the latest interaction for this user."""
        if not user_uuid or not transaction_ids:
            return
        with cls._lock:
            cls._batches[user_uuid] = (time.time(), list(transaction_ids))

    @classmethod
    def get_last_batch(cls, user_uuid: UUID) -> Optional[List[UUID]]:
        """
        Retrieves the latest transaction batch for this user if it has not expired.
        Does not automatically remove it (removal happens on commit of undo).
        """
        if not user_uuid:
            return None
        with cls._lock:
            entry = cls._batches.get(user_uuid)
            if not entry:
                return None
            created_at, tx_ids = entry
            if time.time() - created_at > cls._TTL_SECONDS:
                del cls._batches[user_uuid]
                return None
            return list(tx_ids)

    @classmethod
    def clear_last_batch(cls, user_uuid: UUID) -> None:
        """Clears the tracked batch for this user (e.g. after successful undo)."""
        with cls._lock:
            cls._batches.pop(user_uuid, None)

    @classmethod
    def clear_all(cls) -> None:
        """Resets all batches (useful for test isolation)."""
        with cls._lock:
            cls._batches.clear()

from dataclasses import dataclass
from typing import Dict, Set
from enum import Enum
import threading

# TODO: add timeout to locks
# TODO: add queue based locking

class LockType(Enum):
    SHARED = "SHARED"
    EXCLUSIVE = "EXCLUSIVE"

@dataclass
class FileLock:
    lock_type: LockType
    txn_ids: Set[str]

class FileLockManager:
    def __init__(self):
        self._locks: Dict[str, FileLock] = {}
        self._lock = threading.Lock()

    def acquire_lock(self, file_id: str, txn_id: str, requested_lock_type: LockType) -> bool:
        with self._lock:
            if file_id not in self._locks:
                self._locks[file_id] = FileLock(requested_lock_type, {txn_id})
                return True
            
            current_lock = self._locks[file_id]
            
            if txn_id in current_lock.txn_ids:
                # shared -> exclusive upgrade is not allowed, all other requests are allowed
                if current_lock.lock_type == LockType.SHARED and requested_lock_type == LockType.EXCLUSIVE:
                    return False 

                return True 

            # allow multiple threads to acquire a shared lock 
            if requested_lock_type == LockType.SHARED and current_lock.lock_type == LockType.SHARED:
                current_lock.txn_ids.add(txn_id)
                return True

            return False

    def release_lock(self, file_id: str, txn_id: str) -> None:
        with self._lock:
            if file_id not in self._locks:
                return

            current_lock = self._locks[file_id]

            if txn_id not in current_lock.txn_ids:
                return

            current_lock.txn_ids.remove(txn_id)

            if not current_lock.txn_ids:
                del self._locks[file_id]

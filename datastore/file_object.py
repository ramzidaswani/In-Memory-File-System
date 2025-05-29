from __future__ import annotations
from typing import List
from dataclasses import dataclass
import uuid
from datetime import datetime
from utils import get_diff_operations, apply_diff_operations, DiffOperations

@dataclass
class FileVersion:
    diff_operations: DiffOperations
    timestamp: datetime

class FileObject:
    def __init__(self, file_name: str) -> None:
        self.file_id = str(uuid.uuid4())
        self.file_name: str = file_name
        
        self._snapshot = ""
        self._file_versions: List[FileVersion] = []
        self._active_transaction_count = 0

    def read_version_at_timestamp(self, timestamp: datetime) -> str:
        file_contents = self._snapshot
        for file_version in sorted(self._file_versions, key=lambda v: v.timestamp):
            if file_version.timestamp > timestamp:
                break
            file_contents = apply_diff_operations(file_contents, file_version.diff_operations)

        return file_contents
    
    # optimization: use diff_operations from transaction without converting to file first 
    def commit_version_at_timestamp(self,  file_contents: str, timestamp: datetime) -> None:
        previous_version = self.read_version_at_timestamp(timestamp)
        diff_operations = get_diff_operations(previous_version, file_contents)
        self._file_versions.append(FileVersion(diff_operations, timestamp))  

    def rollback_commit(self, txn_start_time: datetime, txn_commit_time: datetime, rollback_time:datetime) -> None: 
        # verify commit change was applied 
        is_commit_version_found = any(version.timestamp == txn_commit_time for version in self._file_versions)
        if not is_commit_version_found:
             # No matching commit found; nothing to rollback
            return
        
        file_at_start_time = self.read_version_at_timestamp(txn_start_time)
        file_at_commit_time = self.read_version_at_timestamp(txn_commit_time)
        file_diff_operations = get_diff_operations(file_at_commit_time, file_at_start_time)
        self._file_versions.append(FileVersion(file_diff_operations, rollback_time))  


    """
        Incomplete implementation: limited by time constraints

        Purpose: Optimize file storage through version compaction

        Locking Requirements:
        - increment_transaction_count() and decrement_transaction_count(): 
        Must use exclusive locks when modifying transaction_count to prevent race conditions
        - compact_file(): 
        Must obtain exclusive locks on both transaction_count and file data to ensure data consistency

        Implementation Notes:
        - Should be called after transaction commit/rollback to maintain optimal performance

        Limitation:
        This compaction is not fool proof; crashed transactions leave elevated _active_transaction_count, preventing compaction.
        Better approach: Cron-based background thread that:
        - Maintains count of active transaction ids
        - Periodically validates transactions are truly alive (heartbeat/timeout mechanism)
        - Performs compaction when no genuinely active transactions detected
        - Handles crash recovery independently of normal transaction flow
    """

    def increment_transaction_count(self):
        self._active_transaction_count+=1

    def decrement_transaction_count(self):
        self._active_transaction_count-=1
    
    def compact_file(self, commit_time: datetime) -> bool:
        if self._active_transaction_count > 0:
            return False  # Cannot compact with active transactions
        
        if not self._file_versions:
            return True 
    
        max_version_time = max((v.timestamp for v in self._file_versions), default=datetime.min)
        if max_version_time > commit_time:
            return False  # Cannot compact safely
        
        latest_version = self.read_version_at_timestamp(commit_time)
        self._snapshot = latest_version
        self._file_versions = []
        self._active_transaction_count -= 1
        return True 
       


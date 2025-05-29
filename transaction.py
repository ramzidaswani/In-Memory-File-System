from typing import Dict, List
from dataclasses import dataclass
from file_object import FileObject
from datetime import datetime, timezone
from transaction_manager import TransactionManager, TransactionStatus
from file_lock_manager import FileLockManager, LockType
from diff_operations import apply_diff_operations, DiffOperations
from enum import Enum
import uuid

# READ_UNCOMMITTED and READ_COMMITTED are used for read-mode only
class IsolationLevel(Enum):
    READ_UNCOMMITTED = "READ_UNCOMMITTED"  # allows dirty reads, fastest but least safe 
    READ_COMMITTED = "READ_COMMITTED"      # prevents dirty reads, sees only committed changes, may see different values during transaction
    SNAPSHOT = "SNAPSHOT"                  # provides consistent view of all files at transaction start time, prevents phantom reads


# TODO: limit total active transaction to prevent memory bloat

@dataclass
class RollbackLog:
    file_object: FileObject 
    txn_start_time: datetime
    txn_commit_time: datetime

@dataclass
class ModifiedFile:
    file_object: FileObject
    file_diff_operations: List[DiffOperations]

class Transaction:
    """
        Args:
        file_lock_manager: Manages file locks
        transaction_status_manager: Tracks transaction states
        isolation_level: Transaction isolation level

        all timestamps are in utc to prevent time change issues
    """
    def __init__(self, file_lock_manager: FileLockManager, transaction_status_manager: TransactionManager, isolation_level: IsolationLevel) -> None:
        txn_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc).replace(tzinfo=None)

        self.txn_id = txn_id
        self._start_time = start_time
        self._isolation_level = isolation_level
        self._is_active = True

        self.file_lock_manager = file_lock_manager
        self.transaction_status_manager = transaction_status_manager
     
        self._modified_files: Dict[str, ModifiedFile] = {}

        self.transaction_status_manager.create_transaction_metadata(txn_id, start_time)

    def read_file(self, file_object: FileObject) -> str:
        self._validate_txn_is_active()
        
        file_id = file_object.file_id
        file_snapshot = self._get_file_by_isolation_level(file_object, self._isolation_level)

        if file_id in self._modified_files:
            file_diff_operations = self._modified_files[file_id].file_diff_operations
            for file_diff_operation in file_diff_operations:
                file_snapshot = apply_diff_operations(file_snapshot, file_diff_operation)

        return file_snapshot

    def write_file(self, file_object: FileObject, file_diff_operations: DiffOperations) -> None:
        self._validate_txn_is_active()
        
        if self._isolation_level in (IsolationLevel.READ_COMMITTED, IsolationLevel.READ_UNCOMMITTED):
            raise ValueError(f"Write operations not supported for {self._isolation_level.value} isolation level")
        
        file_id = file_object.file_id

        if file_id not in self._modified_files:
            self._modified_files[file_id] = ModifiedFile(file_object = file_object, file_diff_operations=[])
        
        if file_diff_operations:
            self._modified_files[file_id].file_diff_operations.append(file_diff_operations)

    def commit(self) -> None:
        self._validate_txn_is_active()
        
        if not self._modified_files:
            self._end_transaction(TransactionStatus.COMMITTED)
            return 
        
        acquired_locks: List[str] = []
        try:
            # lock by sorted file id to prevent deadlocks
            for file_id in sorted(self._modified_files.keys()):
                if not self.file_lock_manager.acquire_lock(file_id, self.txn_id, LockType.EXCLUSIVE):
                    raise RuntimeError(f"Failed to acquire exclusive lock on file {file_id} for transaction {self.txn_id}")
                
                acquired_locks.append(file_id)

            # commit time is set after all exclusive locks are obtained to ensure timestamp uniqueness
            commit_time = datetime.now(timezone.utc).replace(tzinfo=None)
            self._commit_file_changes(commit_time)
                
            self._end_transaction(TransactionStatus.COMMITTED)

        finally:
            for file_id in acquired_locks:
                self.file_lock_manager.release_lock(file_id, self.txn_id)

    def abort(self):
        self._validate_txn_is_active()
        self._end_transaction(TransactionStatus.ABORTED)
        return 
    
    def is_active(self):
        return self._is_active
    
    # TODO: move to decorator 
    def _validate_txn_is_active(self):
        if not self._is_active:
            self._end_transaction(TransactionStatus.FAILED)
            raise RuntimeError(f"Transaction {self.txn_id} is not active")
    
    def _commit_file_changes(self, commit_time: datetime):
        rollback_logs: List[RollbackLog] = []
       
        for _, modified_file in self._modified_files.items():
            file_object = modified_file.file_object

            # read file returns the file with diff operations applied
            updated_file = self.read_file(file_object)
            
            # Add rollback log before write, in case the write succeeds but an error occurs after
            rollback_logs.append(RollbackLog(file_object, self._start_time, commit_time))
            
            try: 
                file_object.commit_version_at_timestamp(updated_file, commit_time)    
            except Exception as e:
                self._rollback(rollback_logs)
                raise RuntimeError(f"Transaction {self.txn_id} rolled back due to commit failure: {str(e)}") 

    def _rollback(self, rollback_logs: List[RollbackLog]):
        try: 
            rollback_time = datetime.now(timezone.utc).replace(tzinfo=None)
            for rollback_log in rollback_logs:
                file_object = rollback_log.file_object
                file_object.rollback_commit(rollback_log.txn_start_time, rollback_log.txn_commit_time, rollback_time)
            self._end_transaction(TransactionStatus.ROLLED_BACK)
        except Exception as e:
            # Locks will still be released on ROLLBACK_FAILED; this may allow other threads to encounter inconsistent state.
            # Optimization: use an atomic commit protocol to ensure durability and consistency guarantees.
            self._end_transaction(TransactionStatus.ROLLBACK_FAILED)
            raise RuntimeError(f"Critical error: Failed to rollback transaction {self.txn_id}: {str(e)}")
    
    def _get_file_by_isolation_level(self, file_object: FileObject,  isolation_level: IsolationLevel) -> str:
        file_id = file_object.file_id
        if isolation_level == IsolationLevel.READ_UNCOMMITTED:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            return file_object.read_version_at_timestamp(current_time)
        
        if not self.file_lock_manager.acquire_lock(file_id, self.txn_id, LockType.SHARED):
            raise RuntimeError(f"Failed to acquire shared lock on file {file_id} for transaction {self.txn_id}")
        
        try:
            if isolation_level == IsolationLevel.SNAPSHOT:
                return file_object.read_version_at_timestamp(self._start_time)
            elif isolation_level == IsolationLevel.READ_COMMITTED:
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                return file_object.read_version_at_timestamp(current_time)
            
        finally:
            self.file_lock_manager.release_lock(file_id, self.txn_id)

    def _end_transaction(self, status: TransactionStatus):
        self._is_active = False
        self.transaction_status_manager.update_transaction_metadata(
            self.txn_id, 
            status, 
            datetime.now(timezone.utc).replace(tzinfo=None)
        )
        
        # free up memory
        self._modified_files.clear()
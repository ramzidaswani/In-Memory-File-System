from __future__ import annotations
from typing import Optional, List, Dict
from file_lock_manager import FileLockManager
from transaction_manager import TransactionManager, TransactionData
from file_lock_manager import FileLockManager
from file_object import FileObject
from diff_operations import get_diff_operations
from transaction import Transaction, IsolationLevel
from contextlib import contextmanager

# TODO: add locking for concurrent file system access (currently only transactions support concurrency)

class Node:
    def __init__(self, name: str, parent: Optional[Directory] = None):
        is_root = parent is None or parent.name == "/"
        self.name = name if is_root else name.rstrip("/")
        self.parent = parent
    
    def get_full_path(self) -> str:
        path: List[str] = []
        curr_node = self
        while curr_node and curr_node.parent is not None:
            path.append(curr_node.name)
            curr_node = curr_node.parent
        return "/" + "/".join(reversed(path))
    
class File(Node):
    def __init__(self, name: str, parent: Directory, file_lock_manager: FileLockManager, transaction_status_manager: TransactionManager   ):
        super().__init__(name, parent)
        self.file_object: FileObject = FileObject(name)

        self.file_lock_manager = file_lock_manager
        self.transaction_status_manager = transaction_status_manager
        
        # Tracks the latest visible state of each file opened by the client
        # Enables efficient updates by transmitting only the modified portions of the file
        self.opened_files: Dict[str, str] = {} 

    # Unclosed files can accumulate and cause memory bloat.
    # Optimization: implement a cleanup mechanism via a background thread (cron) or use an LRU/LFU cache to manage memory.
    def close(self, transaction: Transaction | None = None) -> None:
        if not transaction or transaction.txn_id not in self.opened_files:
            return 
        
        del self.opened_files[transaction.txn_id]
 
    def read(self, transaction: Transaction | None = None ) -> str:
        if not transaction:
            with self._auto_transaction(self.file_lock_manager, self.transaction_status_manager) as txn:
                return self.read(txn)
            
        if transaction.txn_id not in self.opened_files:
            self._initialize(transaction)
        
        file = transaction.read_file(self.file_object)
        self.opened_files[transaction.txn_id] = file
        return file

    def write(self, content: str, transaction: Transaction | None = None ) -> None:
        if not transaction:
            with self._auto_transaction(self.file_lock_manager, self.transaction_status_manager) as txn:
                return self.write(content, txn)
            
        if transaction.txn_id not in self.opened_files:
            self._initialize(transaction)
        
        file_at_read = self.opened_files[transaction.txn_id]
        file_diff_operations = get_diff_operations(file_at_read, content)
        transaction.write_file(self.file_object, file_diff_operations)
        self.opened_files[transaction.txn_id] = content

    @contextmanager
    def _auto_transaction(self, file_lock_manager: FileLockManager, transaction_status_manager: TransactionManager):
        # default to safest isolation level
        transaction = Transaction(file_lock_manager, transaction_status_manager, IsolationLevel.SNAPSHOT)
        yield transaction
        transaction.commit()
   
    def _initialize(self, transaction: Transaction) -> None:
        if transaction.txn_id not in self.opened_files:
            current_content = transaction.read_file(self.file_object)
            self.opened_files[transaction.txn_id] = current_content 

class Directory(Node):
    def __init__(self, name: str, parent: Optional[Directory] = None):
        super().__init__(name, parent)
        self.children: Dict[str, Node] = {}

    def add_child(self, node: Node) -> None:
        self.children[node.name] = node
        node.parent = self

    def remove_child(self, name: str) -> None:
        if name in self.children:
            del self.children[name]

    def get_child(self, name: str) -> Optional[Node]:
        return self.children.get(name)


class FileSystem:
    def __init__(self) -> None:
        self.root: Directory = Directory("/")
        self.current_directory: Directory = self.root

        self.file_lock_manager = FileLockManager()
        self.transaction_status_manager = TransactionManager()
    
    def pwd(self) -> str:
        return self.current_directory.get_full_path()

    def ls(self) -> List[str]:
        return sorted(self.current_directory.children.keys())

    def cd(self, path: str) -> None:
        target: Node = self._resolve_path(path)
        if isinstance(target, Directory):
            self.current_directory = target
        else:
            raise Exception("Not a directory")

    def mkdir(self, name: str) -> None:
        self._validate_name(name)
        if name in self.current_directory.children:
            raise Exception("Already exists")
        new_directory: Directory = Directory(name, self.current_directory)
        self.current_directory.add_child(new_directory)

    def rmdir(self, name: str) -> None:
        node: Optional[Node] = self.current_directory.children.get(name)
        if not node or not isinstance(node, Directory):
            raise Exception("Directory not found")
        if node.children:
            raise Exception("Directory not empty")
        self.current_directory.remove_child(name)

    def touch(self, name: str) -> None:
        self._validate_name(name)
        if name in self.current_directory.children:
            raise Exception("Already exists")
        new_file: File = File(name, self.current_directory, self.file_lock_manager, self.transaction_status_manager)
        self.current_directory.add_child(new_file)

    # Default to safest isolation level
    def start_transaction(self, isolation_level: IsolationLevel = IsolationLevel.SNAPSHOT) -> Transaction:
        return Transaction(self.file_lock_manager, self.transaction_status_manager, isolation_level) 
    
    def commit_transaction(self, transaction: Transaction) -> None:
        return transaction.commit()

    # TODO: better formatting
    def get_transaction_status(self, transaction_id: str) -> TransactionData:
        return self.transaction_status_manager.get_transaction_status(transaction_id)
    
    def open_file(self, file_name: str) -> File:
        node: Optional[Node] = self.current_directory.children.get(file_name)
        if not node or not isinstance(node, File):
            raise Exception("File not found")
        
        return node
   
    # For active transactions, the FileNode remains accessible
    def rm(self, name:str):
        node = self.current_directory.children.get(name)
        if not node or not isinstance(node, File):
            raise Exception("File not found")
        
        self.current_directory.remove_child(name)

    # For active transactions, the FileNode remains accessible
    def mv(self, source_name:str, destination_path: str): 
        node = self.current_directory.children.get(source_name)
        if not node or not isinstance(node, File):
            raise Exception("File not found")

        destination = self._resolve_path(destination_path)
        if not isinstance(destination, Directory):
            raise Exception("Destination must be a directory")
        
        if node.name in destination.children:
            raise Exception("Name already exists in destination")
        
        self.current_directory.remove_child(source_name)
        destination.add_child(node) 
        
    def find(self, name: str, current_directory: Optional[Directory] = None) -> List[str]:
        if current_directory is None:
            current_directory = self.root
        results: List[str] = []
        if name == current_directory.name:
            results.append(current_directory.get_full_path())
        for child in current_directory.children.values():
            if child.name == name:
                results.append(child.get_full_path())
            if isinstance(child, Directory):
                results.extend(self.find(name, child))
        return results
    
    def _resolve_path(self, path: str) -> Node:
        parts: List[str] = path.strip("/").split("/")
        current_node: Node = self.root if path.startswith("/") else self.current_directory
        for part in parts:
            if part == "..":
                current_node = current_node.parent if isinstance(current_node.parent, Directory) else current_node
            elif part == "." or part == "":
                continue
            else:
                if isinstance(current_node, Directory):
                    directory_node: Optional[Node] = current_node.children.get(part)
                    if directory_node is None:
                        raise Exception("Invalid path")
                    current_node = directory_node
                else:
                    raise Exception("Not a directory")
        return current_node
    
    def _validate_name(self, name: str) -> None:
        if not name or "/" in name or name in [".", ".."]:
            raise ValueError(f"Invalid name: {name}")
        
    








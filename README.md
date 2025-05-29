# In-Memory-File-System

## Transactional File System

A Python implementation of an in-memory file system with ACI transaction support (Atomicity, Consistency, Isolation). This system provides multi-user concurrent access with configurable isolation levels but does not implement durability; all data is lost when the process terminates.

## Key Features

- **Transactional Operations**: Full rollback support with atomicity guarantees
- **Multiple Isolation Levels**: READ_UNCOMMITTED, READ_COMMITTED, and SNAPSHOT isolation
- **Concurrent Access Control**: Shared/exclusive locking (with some deadlock prevention)
- **Version Management**: Efficient diff-based storage for file changes
- **Interactive Console**: Command-line interface for testing and demonstration

## Core Components

- **FileSystem**: Main interface providing standard file/directory operations (touch, mkdir, rm, mv, etc.)
- **Transaction**: Manages transactional file operations with configurable isolation levels
- **TransactionManager**: Tracks transaction lifecycle (ACTIVE → COMMITTED/ABORTED/ROLLED_BACK/ROLLBACK_FAILED)
- **VersionFileObject**: Handles file versioning using space-efficient diff operations
- **FileLockManager**: Coordinates shared/exclusive file locks 
- **Console**: Interactive command-line interface for system interaction

## Transaction Properties (ACI)

- **Atomicity**: All changes in a transaction succeed or all are rolled back
- **Consistency**: Transactions maintain system invariants and file integrity
- **Isolation**: Concurrent transactions don't interfere with each other
- **Durability**: Changes are lost when the process terminates (in-memory only)

## Usage Examples

### Console (run main.py)

### Create and organize files
```bash
/> mkdir documents
/> cd documents
/documents> touch report.txt
/documents> open report.txt
Opened: report.txt
/documents> write report.txt Project Status: Complete
Content written
/documents> read report.txt
Project Status: Complete
/documents> cd ..
/> mv documents/report.txt final_report.txt
/> ls
documents
final_report.txt
```

### Start transaction and modify files
```bash
# Start a transaction and modify a file
/> touch data.txt
/> open data.txt
Opened: data.txt
/> txn_start
Transaction started: txn-123
/> write data.txt Hello World --txn txn-123
Content written
/> read data.txt --txn txn-123
Hello World
/> read data.txt
(empty file)
/> txn_commit txn-123
Transaction committed: txn-123
/> read data.txt
Hello World
```

### Start two concurrent transactions
```bash
# Two transactions with different isolation levels
/> touch shared.txt
/> open shared.txt
Opened: shared.txt
/> write shared.txt Version1
Content written

# Transaction 1: SNAPSHOT (sees Version 1)
/> txn_start SNAPSHOT
Transaction started: txn-123

# Transaction 2: READ_COMMITTED  
/> txn_start READ_COMMITTED
Transaction started: txn-456

# Modify file outside transactions
/> write shared.txt Version2
Content written

# SNAPSHOT still sees old version
/> read shared.txt --txn txn-123
Version1

# READ_COMMITTED sees new version
/> read shared.txt --txn txn-456
Version 2
```
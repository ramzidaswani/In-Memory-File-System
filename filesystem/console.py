from typing import Dict
from filesystem.file_system import FileSystem, File
from transaction import Transaction, IsolationLevel
from filesystem.file_system import FileSystem, File

class Console:
    def __init__(self):
        self.file_system = FileSystem()
        self.transactions: Dict[str, Transaction] = {}
        self.open_files: Dict[str, File] = {}
        
    def run(self):
        print("FileSystem Console - Type 'help' for commands")
        while True:
            try:
                prompt = f"{self.file_system.pwd()}> "
                command = input(prompt).strip()
                
                if not command:
                    continue
                    
                parts = command.split()
                cmd = parts[0].lower()
                args = parts[1:]
                
                if cmd == "exit":
                    break
                elif cmd == "help":
                    self._show_help()
                elif cmd == "pwd":
                    print(self.file_system.pwd())
                elif cmd == "ls":
                    items = self.file_system.ls()
                    for item in items:
                        print(item)
                elif cmd == "cd":
                    if len(args) != 1:
                        print("Usage: cd <path>")
                    else:
                        self.file_system.cd(args[0])
                elif cmd == "mkdir":
                    if len(args) != 1:
                        print("Usage: mkdir <name>")
                    else:
                        self.file_system.mkdir(args[0])
                elif cmd == "rmdir":
                    if len(args) != 1:
                        print("Usage: rmdir <name>")
                    else:
                        self.file_system.rmdir(args[0])
                elif cmd == "touch":
                    if len(args) != 1:
                        print("Usage: touch <filename>")
                    else:
                        self.file_system.touch(args[0])
                elif cmd == "rm":
                    if len(args) != 1:
                        print("Usage: rm <filename>")
                    else:
                        self.file_system.rm(args[0])
                elif cmd == "mv":
                    if len(args) != 2:
                        print("Usage: mv <source> <destination>")
                    else:
                        self.file_system.mv(args[0], args[1])
                elif cmd == "find":
                    if len(args) != 1:
                        print("Usage: find <name>")
                    else:
                        results = self.file_system.find(args[0])
                        for result in results:
                            print(result)
                elif cmd == "open":
                    if len(args) != 1:
                        print("Usage: open <filename>")
                    else:
                        file = self.file_system.open_file(args[0])
                        self.open_files[args[0]] = file
                        print(f"Opened: {args[0]}")
                elif cmd == "close":
                    if len(args) < 1:
                        print("Usage: close <filename> [--txn <txn_id>]")
                    else:
                        filename = args[0]
                        if filename in self.open_files:
                            txn = None
                            if "--txn" in args[1:]:
                                txn_index = args[1:].index("--txn") + 1
                                if txn_index + 1 < len(args):
                                    txn_id = args[txn_index + 1]
                                    if txn_id in self.transactions:
                                        txn = self.transactions[txn_id]
                                    else:
                                        print(f"Error: Transaction '{txn_id}' not found")
                                        continue
                                else:
                                    print("Error: --txn requires a transaction ID")
                                    continue
                            
                            self.open_files[filename].close(txn)
                            del self.open_files[filename]
                            print(f"Closed: {filename}")
                        else:
                            print(f"File not open: {filename}")
                elif cmd == "read":
                    if len(args) < 1:
                        print("Usage: read <filename> [--txn <txn_id>]")
                    else:
                        filename = args[0]
                        if filename not in self.open_files:
                            print(f"File not open: {filename}")
                        else:
                            txn = None
                            if "--txn" in args[1:]:
                                txn_index = args[1:].index("--txn") + 1
                                if txn_index + 1 < len(args):
                                    txn_id = args[txn_index + 1]
                                    if txn_id in self.transactions:
                                        txn = self.transactions[txn_id]
                                    else:
                                        print(f"Error: Transaction '{txn_id}' not found")
                                        continue
                                else:
                                    print("Error: --txn requires a transaction ID")
                                    continue
                            
                            content = self.open_files[filename].read(txn)
                            print(content if content else "(empty file)")
                elif cmd == "write":
                    if len(args) < 2:
                        print("Usage: write <filename> <content> [--txn <txn_id>]")
                    else:
                        filename = args[0]
                        if filename not in self.open_files:
                            print(f"File not open: {filename}")
                        else:
                            txn = None
                            content_args = args[1:]
                            
                            if "--txn" in content_args:
                                txn_index = content_args.index("--txn")
                                if txn_index + 1 < len(content_args):
                                    txn_id = content_args[txn_index + 1]
                                    if txn_id in self.transactions:
                                        txn = self.transactions[txn_id]
                                    else:
                                        print(f"Error: Transaction '{txn_id}' not found")
                                        continue
                                    content_args = content_args[:txn_index] + content_args[txn_index + 2:]
                                else:
                                    print("Error: --txn requires a transaction ID")
                                    continue
                            
                            content = " ".join(content_args)
                            self.open_files[filename].write(content, txn)
                            print("Content written")
                elif cmd == "txn_start":
                    isolation = IsolationLevel.SNAPSHOT  # default
                    if len(args) > 0:
                        if args[0].upper() == "READ_COMMITTED":
                            isolation = IsolationLevel.READ_COMMITTED
                        elif args[0].upper() == "SNAPSHOT":
                            isolation = IsolationLevel.SNAPSHOT
                        elif args[0].upper() == "READ_UNCOMMITTED":
                            isolation = IsolationLevel.READ_UNCOMMITTED
                    txn = self.file_system.start_transaction(isolation)
                    self.transactions[txn.txn_id] = txn
                    print(f"Transaction started: {txn.txn_id}")
                elif cmd == "txn_commit":
                    if len(args) != 1:
                        print("Usage: txn_commit <txn_id>")
                    else:
                        txn_id = args[0]
                        if txn_id in self.transactions:
                            self.file_system.commit_transaction(self.transactions[txn_id])
                            del self.transactions[txn_id]
                            print(f"Transaction committed: {txn_id}")
                        else:
                            print(f"Transaction not found: {txn_id}")
                elif cmd == "txn_status":
                    if len(args) != 1:
                        print("Usage: txn_status <txn_id>")
                    else:
                        status = self.file_system.get_transaction_status(args[0])
                        end_info = f", End: {status.end_time}" if status.end_time else ""
                        print(f"Status: {status.status.value}, Start: {status.start_time}{end_info}")
                elif cmd == "txn_list":
                    if not self.transactions:
                        print("No active transactions")
                    else:
                        for txn_id in self.transactions:
                            print(f"  {txn_id}")
                else:
                    print(f"Unknown command: {cmd}")
                    
            except Exception as e:
                print(f"Error: {e}")
    
    def _show_help(self):
        commands = [
            ("help", "Show this help message"),
            ("exit", "Exit the console"),
            ("", ""),
            ("# Directory operations:", ""),
            ("pwd", "Print working directory"),
            ("ls", "List directory contents"),
            ("cd <path>", "Change directory"),
            ("mkdir <name>", "Create directory"),
            ("rmdir <name>", "Remove empty directory"),
            ("", ""),
            ("# File operations:", ""),
            ("touch <filename>", "Create empty file"),
            ("rm <filename>", "Remove file"),
            ("mv <source> <dest>", "Move file"),
            ("find <name>", "Find files/directories by name"),
            ("", ""),
            ("# File I/O operations:", ""),
            ("open <filename>", "Open file for reading/writing"),
            ("close <filename> [--txn <txn_id>]", "Close file"),
            ("read <filename> [--txn <txn_id>]", "Read file contents"),
            ("write <filename> <content> [--txn <txn_id>]", "Write content to file"),
            ("", ""),
            ("# Transaction operations:", ""),
            ("txn_start [READ_COMMITTED|SNAPSHOT]", "Start new transaction"),
            ("txn_commit <txn_id>", "Commit transaction"),
            ("txn_status <txn_id>", "Get transaction status"),
            ("txn_list", "List active transactions"),
            ("", "")
        ]
        
        for cmd, desc in commands:
            if desc:
                print(f"  {cmd:<35} {desc}")
            else:
                print(cmd)
    
    def _execute_command(self, command: str):
        parts = command.split()
        if not parts:
            return
            
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd == "pwd":
            print(self.file_system.pwd())
        elif cmd == "ls":
            items = self.file_system.ls()
            for item in items:
                print(item)
        elif cmd == "cd" and len(args) == 1:
            self.file_system.cd(args[0])
        elif cmd == "mkdir" and len(args) == 1:
            self.file_system.mkdir(args[0])
        elif cmd == "touch" and len(args) == 1:
            self.file_system.touch(args[0])
        elif cmd == "open" and len(args) == 1:
            file = self.file_system.open_file(args[0])
            self.open_files[args[0]] = file

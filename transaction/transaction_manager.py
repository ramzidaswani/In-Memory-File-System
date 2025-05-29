
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

class TransactionStatus(Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED",
    FAILED = "FAILED" 
    ROLLED_BACK = "ROLLED_BACK" # failure occurred after write commit
    ROLLBACK_FAILED = "ROLLBACK_FAILED" # rollback failed, files are in an inconsistent state 

@dataclass 
class TransactionData:
    start_time: datetime
    end_time: None | datetime 
    status: TransactionStatus 

class TransactionManager:
    def __init__(self):
        self.transactions: Dict[str, TransactionData] = {}
    
    def create_transaction_metadata(self, txn_id: str, start_time: datetime):
        self.transactions[txn_id] = TransactionData(
            start_time=start_time, 
            status = TransactionStatus.ACTIVE,
            end_time = None
        )


    # for async logging 
    def update_transaction_metadata(self, txn_id: str, status:TransactionStatus, end_time: datetime | None = None) -> None:
        transaction_data = self.transactions[txn_id]
        self.transactions[txn_id] = TransactionData(
            start_time=transaction_data.start_time, 
            status = status, 
            end_time = end_time if end_time else transaction_data.end_time

        )

    def get_transaction_status(self, transaction_id: str) -> TransactionData:
        return self.transactions[transaction_id]
    




        

    
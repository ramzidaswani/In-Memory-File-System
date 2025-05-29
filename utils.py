from typing import List, Literal, Union, TypedDict
import difflib

class ReplaceOperation(TypedDict):
    type: Literal['replace']
    start: int
    end: int
    data: str

class DeleteOperation(TypedDict):
    type: Literal['delete']
    start: int
    end: int

class InsertOperation(TypedDict):
    type: Literal['insert']
    start: int
    data: str

DiffOperation = Union[ReplaceOperation, DeleteOperation, InsertOperation]
DiffOperations = List[DiffOperation]

# TODO: chunk large operations to reduce high memory usage

def get_diff_operations(old: str, new: str) -> DiffOperations:
    if old == new:
        return [] 
    
    operations: DiffOperations = []
    matcher = difflib.SequenceMatcher(None, old, new)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            operations.append({
                'type': 'replace',
                'start': i1,
                'end': i2,
                'data': new[j1:j2]
            })
        elif tag == 'delete':
            operations.append({
                'type': 'delete',
                'start': i1,
                'end': i2
            })
        elif tag == 'insert':
            operations.append({
                'type': 'insert',
                'start': i1,
                'data': new[j1:j2]
            })
    
    return operations


def apply_diff_operations(content: str, operations: DiffOperations) -> str:
    validate_operations(content, operations)
    
    # Apply changes in reverse order to prevent index shifting issues
    sorted_operations = sorted(operations, key=lambda op: op['start'], reverse=True)
    
    result = content
    for operation in sorted_operations:
        if operation['type'] == 'replace':
            result = result[:operation['start']] + operation['data'] + result[operation['end']:]
        elif operation['type'] == 'insert':
            result = result[:operation['start']] + operation['data'] + result[operation['start']:]
        elif operation['type'] == 'delete':
            result = result[:operation['start']] + result[operation['end']:]
    
    return result 


def validate_operations(content: str, operations: DiffOperations):
    content_len = len(content)
    for operation in operations:
        start = operation.get('start', 0)
        end = operation.get('end', start)
        
        if start < 0 or start > content_len:
            raise ValueError(f"Invalid start index: {start}")
        if end < start or end > content_len:
            raise ValueError(f"Invalid end index: {end}")
        

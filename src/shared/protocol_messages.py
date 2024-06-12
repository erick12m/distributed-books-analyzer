import csv
from enum import Enum
import io


DELIM = "|||"
class QueryMessageType(Enum):
    EOF_B = 1
    EOF_R = 2
    DATA = 3
    DATA_ACK = 4
    WAIT_FOR_SV = 5

class QueryMessage:
    def __init__(self, msg_type: Enum, client_id: int, payload: str = ""):
        self.msg_type = msg_type
        self.client_id = client_id
        self.payload = payload

    def encode_to_str(self) -> str:
        return f"{self.msg_type.value}{DELIM}{self.client_id}{DELIM}{self.payload}"
    
    @classmethod
    def decode_from_str(cls, msg: str):
        msg_type, client_id, payload = msg.split(f"{DELIM}")
        return cls(QueryMessageType(int(msg_type)), int(client_id), payload)
    


# ========================================================================================================
 


class SystemMessageType(Enum):
    EOF_B = 1
    EOF_R = 2
    DATA = 3
    HEALTH_CHECK = 4
    ALIVE = 5

class SystemMessage:
    def __init__(self, msg_type: Enum, client_id: int, controller_name: str, controller_seq_num: int, payload: str = ""):
        self.msg_type = msg_type
        self.client_id = client_id
        self.controller_name = controller_name
        self.controller_seq_num = controller_seq_num
        self.payload = payload

    def encode_to_str(self) -> str:
        return f"{self.msg_type.value}{DELIM}{self.client_id}{DELIM}{self.controller_name}{DELIM}{self.controller_seq_num}{DELIM}{self.payload}"
    
    @classmethod
    def decode_from_bytes(cls, raw_msg_body: bytes):
        msg = raw_msg_body.decode()
        msg_type, client_id, controller_name, controller_seq_num, payload = msg.split(f"{DELIM}")
        return cls(SystemMessageType(int(msg_type)), int(client_id), controller_name, int(controller_seq_num), payload)
    
    def get_batch_iter_from_payload(self):
        if self.msg_type == SystemMessageType.DATA:
            return csv.reader(io.StringIO(self.payload), delimiter=',', quotechar='"')
        else:
            return None
    
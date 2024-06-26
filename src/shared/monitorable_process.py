import signal
import socket
import time
from shared.protocol_messages import SystemMessage, SystemMessageType
from shared.socket_connection_handler import SocketConnectionHandler
import logging
from multiprocessing import Process
from shared.mq_connection_handler import MQConnectionHandler
from typing import Any, Optional, TypeAlias
import json
from shared.atomic_writer import AtomicWriter


HEALTH_CHECK_PORT = 5000

ClientID_t: TypeAlias = int
BufferName_t: TypeAlias = str
ControllerName_t: TypeAlias = str
ControllerSeqNum_t: TypeAlias = int
BufferContent_t: TypeAlias = dict[ControllerName_t, ControllerSeqNum_t] | Any

class MonitorableProcess:
    def __init__(self, controller_name: str):
        self.controller_name = controller_name
        self.health_check_connection_handler: Optional[SocketConnectionHandler] = None
        self.mq_connection_handler: Optional[MQConnectionHandler] = None
        self.joinable_processes: list[Process] = []
        self.state_file_path = f"{controller_name}_state.json"
        self.state: dict[ClientID_t, dict[BufferName_t, BufferContent_t]] = self.__load_state_file()
        p = Process(target=self.__accept_incoming_health_checks)
        self.joinable_processes.append(p)
        p.start()
        signal.signal(signal.SIGTERM, self.__handle_shutdown)
        
    def __handle_shutdown(self, signum, frame):
        if self.health_check_connection_handler:
            self.health_check_connection_handler.close()
        if self.mq_connection_handler:
            self.mq_connection_handler.close_connection()
        for process in self.joinable_processes:
            process.terminate()       


    def __accept_incoming_health_checks(self):
        logging.info("[MONITORABLE] Starting to receive health checks")
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        self.listening_socket.bind((self.controller_name, HEALTH_CHECK_PORT))
        self.listening_socket.listen()
        while True:
            client_socket, _ = self.listening_socket.accept()
            self.health_check_connection_handler = SocketConnectionHandler.create_from_socket(client_socket)
            message = SystemMessage.decode_from_bytes(self.health_check_connection_handler.read_message_raw())

            if message.type == SystemMessageType.HEALTH_CHECK:
                alive_msg = SystemMessage(msg_type=SystemMessageType.ALIVE, client_id=0, controller_name=self.controller_name, controller_seq_num=0).encode_to_str()
                self.health_check_connection_handler.send_message(alive_msg)
            self.health_check_connection_handler.close()
            

    def __load_state_file(self) -> dict:
        try:
            with open(self.state_file_path, 'r') as f:
                state_json = json.load(f)
                return {int(k): v for k, v in state_json.items()}
        except FileNotFoundError:
            return {}
        
    def save_state_file(self):
        writer = AtomicWriter(self.state_file_path)
        writer.write(json.dumps(self.state, default=self.__serialize_sets))
        
    def state_handler_callback(self, ch, method, properties, body, inner_processor):
        """
        IMPORTANT: The state of any buffer apart from the latest_message_per_controller should be handled by the inner callback if needed as it is specific to each controller. This applies, for example, to the LOCAL seq number to send.

        The inner callback should not ack messages as it is handled here
        """
        received_msg = SystemMessage.decode_from_bytes(body)
        if received_msg.client_id not in self.state:
            self.state[received_msg.client_id] = {}

        latest_seq_num_from_controller = self.state.get(received_msg.client_id, {}).get("latest_message_per_controller", {}).get(received_msg.controller_name, 0)
            
        if received_msg.controller_seq_num <= latest_seq_num_from_controller:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            if received_msg.type != SystemMessageType.ABORT:
                logging.info(f"[DUPLICATE DETECTED]: client: {received_msg.client_id} controller: {received_msg.controller_name} seq num: {received_msg.controller_seq_num}")
        else:
            inner_processor(received_msg)
            logging.debug(f"[PROCESSED MESSAGE]: type {received_msg.type} from client {received_msg.client_id} with received seq num {received_msg.controller_seq_num}")
            self.__update_seq_num_state(received_msg.client_id, received_msg.controller_name, received_msg.controller_seq_num)
            self.save_state_file()
            logging.debug(f"[STATE SAVED]: {self.state}")
            ch.basic_ack(delivery_tag=method.delivery_tag)    
            logging.debug(f"[ACKNOWLEDGED]: client: {received_msg.client_id} controller: {received_msg.controller_name} seq num: {received_msg.controller_seq_num}")
            

    def get_seq_num_to_send(self, client_id: int, controller_name: str) -> int:
        last_message_seq_num = self.state.get(client_id, {}).get("latest_message_per_controller", {}).get(controller_name, 0)
        return last_message_seq_num + 1
    
    def update_self_seq_number(self, client_id: int, seq_num: int):
        self.__update_seq_num_state(client_id, self.controller_name, seq_num)
        
    def __update_seq_num_state(self, client_id, controller_name, seq_num):
        if client_id in self.state:
            if "latest_message_per_controller" in self.state[client_id]:
                self.state[client_id]["latest_message_per_controller"][controller_name] = seq_num
            else:
                self.state[client_id]["latest_message_per_controller"] = {controller_name: seq_num}
        else:
            self.state[client_id] = {"latest_message_per_controller": {controller_name: seq_num}}
            
    def __serialize_sets(self, obj):
        if isinstance(obj, set):
            return list(obj)

        return obj

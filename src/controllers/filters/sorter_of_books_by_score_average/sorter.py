from shared.mq_connection_handler import MQConnectionHandler
from shared import constants
import csv
import io
import logging
from shared.monitorable_process import MonitorableProcess
from shared.protocol_messages import SystemMessage, SystemMessageType

TITLE_IDX = 0
SCORES_IDX = 1

class Sorter(MonitorableProcess):
    def __init__(self, 
                 input_exchange: str, 
                 output_exchange: str, 
                 input_queue: str, 
                 output_queue: str, 
                 required_top_of_books: int,
                 controller_name: str):
        super().__init__(controller_name)
        self.input_exchange = input_exchange
        self.output_exchange = output_exchange
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.required_top_of_books = required_top_of_books
        self.mq_connection_handler = MQConnectionHandler(output_exchange_name=self.output_exchange, 
                                                         output_queues_to_bind={self.output_queue: [self.output_queue]},
                                                         input_exchange_name=self.input_exchange,
                                                         input_queues_to_recv_from=[self.input_queue])
        
    def start(self):
        self.mq_connection_handler.setup_callbacks_for_input_queue(self.input_queue, self.state_handler_callback, self.__sort_books)
        self.mq_connection_handler.start_consuming()
        
    def __sort_books(self, body: SystemMessage):
        """
        The body is a csv line with the following format in the line: "title,[scores]"
        """
        if body.type == SystemMessageType.EOF_R:
            logging.info(f"Received EOF_R from [ client_{body.client_id} ]")
            next_seq_num = self.get_seq_num_to_send(body.client_id, self.controller_name)
            best_books = self.state[body.client_id].get("best_books", [])
            if len(best_books) != 0:
                self.mq_connection_handler.send_message(self.output_queue, SystemMessage(SystemMessageType.DATA, body.client_id, self.controller_name, next_seq_num, f"\"{best_books}\"").encode_to_str())
                self.update_self_seq_number(body.client_id, next_seq_num)
                next_seq_num = self.get_seq_num_to_send(body.client_id, self.controller_name)
            self.mq_connection_handler.send_message(self.output_queue, SystemMessage(SystemMessageType.EOF_R, body.client_id, self.controller_name, next_seq_num).encode_to_str())
            self.state[body.client_id]["best_books"] = []
        elif body.type == SystemMessageType.ABORT:
            logging.info(f"[ABORT RECEIVED]: client: {body.client_id}")
            seq_num_to_send = self.get_seq_num_to_send(body.client_id, self.controller_name)
            self.mq_connection_handler.send_message(self.output_queue, SystemMessage(SystemMessageType.ABORT, body.client_id, self.controller_name, seq_num_to_send).encode_to_str())
            self.state[body.client_id] = {}
        else:
            books = body.get_batch_iter_from_payload()
            for book in books:
                scores = eval(book[SCORES_IDX])
                scores = list(map(int, scores))
                avg_score = sum(scores) / len(scores)
                if len(self.state[body.client_id].get("best_books",[])) < self.required_top_of_books:
                    best_books = self.state[body.client_id].get("best_books", [])
                    best_books.append((book[TITLE_IDX], avg_score))
                    best_books.sort(key=lambda x: x[SCORES_IDX], reverse=True)
                    self.state[body.client_id].update({"best_books": best_books})
                else:
                    if avg_score > self.state[body.client_id].get("best_books",[])[-1][SCORES_IDX]:
                        best_books = self.state[body.client_id].get("best_books", [])
                        best_books.append((book[TITLE_IDX], avg_score))
                        best_books.sort(key=lambda x: x[SCORES_IDX], reverse=True)
                        best_books.pop()
                        self.state[body.client_id].update({"best_books": best_books})


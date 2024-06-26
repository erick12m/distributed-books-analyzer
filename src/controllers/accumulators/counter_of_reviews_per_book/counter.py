import logging
from shared.mq_connection_handler import MQConnectionHandler
from shared import constants
import csv
import io
from shared.monitorable_process import MonitorableProcess
from shared.protocol_messages import SystemMessage, SystemMessageType

TITLE_IDX = 0
AUTHORS_IDX = 1
SCORE_IDX = 2
DECADE_IDX = 3


class CounterOfReviewsPerBook(MonitorableProcess):
    def __init__(self, 
                 input_exchange_name: str, 
                 output_exchange_name: str, 
                 input_queue_name: str, 
                 output_queue_name: str,
                 batch_size: int,
                 controller_name: str):
        super().__init__(controller_name)
        self.batch_size = batch_size

        self.input_exchange_name = input_exchange_name
        self.output_exchange_name = output_exchange_name
        self.input_queue_name = input_queue_name
        self.output_queue_name = output_queue_name
        self.mq_connection_handler = MQConnectionHandler(output_exchange_name=self.output_exchange_name,
                                                         output_queues_to_bind={self.output_queue_name: [self.output_queue_name]},
                                                         input_exchange_name=self.input_exchange_name,
                                                         input_queues_to_recv_from=[self.input_queue_name])
       
    def start(self):
        self.mq_connection_handler.setup_callbacks_for_input_queue(self.input_queue_name, self.state_handler_callback, self.__count_reviews)
        self.mq_connection_handler.channel.start_consuming()
    
    def __count_reviews(self, body: SystemMessage):
        """
        The message should have the following format: title,authors,score,decade
        """
        if body.type == SystemMessageType.EOF_R:
            logging.info(f"Received EOF_R from [ client_{body.client_id} ]. Sending results to output queue.")
            self.__send_results(body)
        elif body.type == SystemMessageType.ABORT:
            logging.info(f"[ABORT RECEIVED]: client: {body.client_id}")
            seq_num_to_send = self.get_seq_num_to_send(body.client_id, self.controller_name)
            self.mq_connection_handler.send_message(self.output_queue_name, SystemMessage(SystemMessageType.ABORT, body.client_id, self.controller_name, seq_num_to_send).encode_to_str())
            self.state[body.client_id] = {}
        else:
            reviews = body.get_batch_iter_from_payload()
            for row in reviews:
                title = row[TITLE_IDX]
                self.state[body.client_id].setdefault("books_reviews", dict()).setdefault(title, [row[TITLE_IDX],row[AUTHORS_IDX],list(),row[DECADE_IDX]])
                self.state[body.client_id]["books_reviews"][title][SCORE_IDX].append(row[SCORE_IDX])  
                    
    
    def __send_results(self, body: SystemMessage):
        payload_current_size = 0
        payload_to_send = ""
        books_reviews = self.state.get(body.client_id, {}).get("books_reviews", {})
        books_reviews_items = list(books_reviews.items())

        for i, (title, review) in enumerate(books_reviews_items):
            payload_to_send += f"{title},\"{review[AUTHORS_IDX]}\",\"{review[SCORE_IDX]}\",{review[DECADE_IDX]},{len(review[SCORE_IDX])}\n"
            payload_current_size += 1
            if (payload_current_size == self.batch_size) or (i == len(books_reviews_items) - 1):
                next_seq_num = self.get_seq_num_to_send(body.client_id, self.controller_name)
                self.mq_connection_handler.send_message(self.output_queue_name, SystemMessage(SystemMessageType.DATA, body.client_id, self.controller_name, next_seq_num, payload_to_send).encode_to_str())
                self.update_self_seq_number(body.client_id, next_seq_num)
                payload_to_send = ""
                payload_current_size = 0

        next_seq_num = self.get_seq_num_to_send(body.client_id, self.controller_name)
        self.mq_connection_handler.send_message(self.output_queue_name, SystemMessage(SystemMessageType.EOF_R, body.client_id, self.controller_name, next_seq_num).encode_to_str())
        self.update_self_seq_number(body.client_id, next_seq_num)
        self.state[body.client_id]["books_reviews"] = {}
        logging.info("Sent EOF message to output queue")

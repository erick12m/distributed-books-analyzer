from shared.mq_connection_handler import MQConnectionHandler
import logging
import io
import csv
from shared import constants
from shared.monitorable_process import MonitorableProcess

TITLE_IDX = 0
AUTHORS_IDX = 1
SCORE_IDX = 2
DECADE_IDX = 3

class FilterOfCompactReviewsByDecade(MonitorableProcess):
    def __init__(self, 
                 input_exchange: str, 
                 output_exchange: str, 
                 input_queue_of_reviews: str, 
                 output_queues: dict[str,str], 
                 decade_to_filter:int, 
                 num_of_input_workers: int,
                 controller_name: str):
        super().__init__(controller_name)
        self.input_exchange = input_exchange
        self.output_exchange = output_exchange
        self.input_queue_of_reviews = input_queue_of_reviews
        self.decade_to_filter = decade_to_filter
        self.num_of_input_workers = num_of_input_workers
        self.output_queues = {}
        for queue_name in output_queues.values():
            self.output_queues[queue_name] = [queue_name]
        self.mq_connection_handler = None
        self.eof_received = 0
        
        
    def start(self):
        self.mq_connection_handler = MQConnectionHandler(output_exchange_name=self.output_exchange,
                                                         output_queues_to_bind=self.output_queues,
                                                         input_exchange_name=self.input_exchange,
                                                         input_queues_to_recv_from=[self.input_queue_of_reviews])
        self.mq_connection_handler.setup_callback_for_input_queue(self.input_queue_of_reviews, self.__filter_reviews)
        self.mq_connection_handler.channel.start_consuming()
            
    def __filter_reviews(self, ch, method, properties, body):
        """
        The message should have the following format: title,authors,score,decade
        """
        msg = body.decode()
        if msg == constants.FINISH_MSG:
            self.eof_received += 1
            if self.eof_received == self.num_of_input_workers:
                for queue_name in self.output_queues:
                    self.mq_connection_handler.send_message(queue_name, constants.FINISH_MSG)
                logging.info("Received all EOFs. Sending to all output queues.")
                self.eof_received = 0
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            review = csv.reader(io.StringIO(msg), delimiter=',', quotechar='"')
            for row in review:
                title = row[TITLE_IDX]
                authors = eval(row[AUTHORS_IDX])
                score = row[SCORE_IDX]
                decade = row[DECADE_IDX]
                if int(decade) == self.decade_to_filter:
                    output_msg = f"{title},\"{authors}\",{score},{decade}"
                    self.mq_connection_handler.send_message(self.__select_queue(title), output_msg)
                else:
                    logging.debug(f"Review {title} was discarded. Decade: {decade} != {self.decade_to_filter}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
                
    def __select_queue(self, title: str) -> str:
        """
        Should return the queue name where the review should be sent to.
        It uses the hash of the title to select a queue on self.output_queues
        """
        
        hash_value = hash(title)
        queue_index = hash_value % len(self.output_queues)
        return list(self.output_queues.keys())[queue_index]    
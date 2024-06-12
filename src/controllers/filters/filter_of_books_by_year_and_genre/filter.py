from shared.mq_connection_handler import MQConnectionHandler
import logging
from shared import constants
import csv
import io
from shared.monitorable_process import MonitorableProcess


TITLE_IDX = 0
AUTHORS_IDX = 1
PUBLISHER_IDX = 2
YEAR_IDX = 3
CATEGORIES_IDX = 4


class FilterByGenreAndYear(MonitorableProcess):
    def __init__(self, 
                 input_exchange_name: str, 
                 output_exchange_name: str, 
                 input_queue_name: str, 
                 output_queue_name: str, 
                 min_year_to_filter: int, 
                 max_year_to_filter: int,
                 genre_to_filter: str,
                 controller_name: str):
        super().__init__(controller_name)
        self.output_queue = output_queue_name
        self.min_year_to_filter = int(min_year_to_filter)
        self.max_year_to_filter = int(max_year_to_filter)
        self.genre_to_filter = genre_to_filter
        self.mq_connection_handler = MQConnectionHandler(
            output_exchange_name=output_exchange_name, 
            output_queues_to_bind={output_queue_name: [output_queue_name]}, 
            input_exchange_name=input_exchange_name, 
            input_queues_to_recv_from=[input_queue_name]
        )
        self.mq_connection_handler.setup_callback_for_input_queue(input_queue_name, self.__filter_books_by_year_and_genre)
        
            
    def __filter_books_by_year_and_genre(self, ch, method, properties, body):
        msg = body.decode()
        if msg == constants.FINISH_MSG:
            self.mq_connection_handler.send_message(self.output_queue, msg)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            batch = csv.reader(io.StringIO(msg), delimiter=',', quotechar='"')
            for row in batch:
                title = row[TITLE_IDX]
                authors = row[AUTHORS_IDX]
                publisher = row[PUBLISHER_IDX]
                year_str = row[YEAR_IDX]
                categories = row[CATEGORIES_IDX]
                if int(year_str) >= self.min_year_to_filter and \
                        int(year_str) <= self.max_year_to_filter and \
                        self.genre_to_filter in categories:
                    msg_to_send = f"{title},\"{authors}\",{publisher},{year_str}" + "\n"            
                    self.mq_connection_handler.send_message(self.output_queue, msg_to_send)
                
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
       
    def start(self):
        self.mq_connection_handler.channel.start_consuming()
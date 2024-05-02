from shared.mq_connection_handler import MQConnectionHandler
import logging
import csv
import io
import signal
from shared import constants

AUTHORS_IDX = 0
DECADE_IDX = 1

class AuthorExpander:
    def __init__(self, input_exchange, output_exchange, input_queue_of_books, output_queues: dict[str,str]):
        self.input_exchange = input_exchange
        self.output_exchange = output_exchange
        self.input_queue_of_books = input_queue_of_books
        self.output_queues = {}
        for queue_name in output_queues.values():
            self.output_queues[queue_name] = [queue_name]
        self.mq_connection_handler = None
        signal.signal(signal.SIGTERM, self.__handle_shutdown)

    def __handle_shutdown(self, signum, frame):
        logging.info("Shutting down AuthorExpander")
        self.mq_connection_handler.close_connection()

        
    def start(self):
        self.mq_connection_handler = MQConnectionHandler(output_exchange_name=self.output_exchange,
                                                         output_queues_to_bind=self.output_queues,
                                                         input_exchange_name=self.input_exchange,
                                                         input_queues_to_recv_from=[self.input_queue_of_books])       
 
        self.mq_connection_handler.setup_callback_for_input_queue(self.input_queue_of_books, self.__expand_authors)
        self.mq_connection_handler.start_consuming()
        
    
    def __expand_authors(self, ch, method, properties, body):
        """ 
        The body is a csv batch with the following format in a line: "['author_1',...,'author_n'], decade" 
        The expansion should create multiple lines, one for each author, with the following format: "author_i, decade"
        """
        msg = body.decode()
        logging.debug(f"Received message from input queue: {msg}")
        if msg == constants.FINISH_MSG:
            for queue_name in self.output_queues:
                self.mq_connection_handler.send_message(queue_name, constants.FINISH_MSG)
            logging.info("Sent EOF message to output queues")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            batch = csv.reader(io.StringIO(msg), delimiter=',', quotechar='"')
            for row in batch:
                authors = eval(row[AUTHORS_IDX])
                decade = row[DECADE_IDX]
                for author in authors:
                    output_msg = f"{author},{decade}"
                    self.mq_connection_handler.send_message(self.__select_queue(author), output_msg)
                    logging.debug(f"Sent message to queue: {output_msg}")

            ch.basic_ack(delivery_tag=method.delivery_tag)
        
    def __select_queue(self, author: str) -> str:
        """
        Should return the queue name where the author should be sent to.
        It uses the hash of the author to select a queue on self.output_queues
        """
        
        hash_value = hash(author)
        queue_index = hash_value % len(self.output_queues)
        return list(self.output_queues.keys())[queue_index]    
            
        
        
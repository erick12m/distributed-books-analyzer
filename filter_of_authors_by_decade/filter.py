from shared.mq_connection_handler  import MQConnectionHandler
import logging

class Filter:
    def __init__(self, 
                 input_exchange_name: str, 
                 output_exchange_name: str, 
                 input_queue_name: str, 
                 output_queue_name: str, 
                 counters_of_decades_per_author: int, 
                 min_decades_to_filter: int
                 ):
        self.input_exchange_name = input_exchange_name
        self.output_exchange_name = output_exchange_name
        self.input_queue_name = input_queue_name
        self.output_queue_name = output_queue_name
        self.counters_of_decades_per_author = counters_of_decades_per_author
        self.min_decades_to_filter = min_decades_to_filter
        self.eof_received = 0
        self.mq_connection_handler = None
        
    def start(self):
        try:
            self.mq_connection_handler = MQConnectionHandler(output_exchange_name=self.output_exchange_name, 
                                                             output_queues_to_bind={self.output_queue_name: [self.output_queue_name]}, 
                                                             input_exchange_name=self.input_exchange_name, 
                                                             input_queues_to_recv_from=[self.input_queue_name])
        except Exception as e:
            logging.error(f"Error while connecting to RabbitMQ: {e}")
        try:
            self.mq_connection_handler.setup_callback_for_input_queue(self.input_queue_name, self.__filter_authors_by_decades_quantity)
            self.mq_connection_handler.channel.start_consuming()
        except Exception as e:
            logging.error(f"Error while consuming from RabbitMQ: {e}")
            
    def __filter_authors_by_decades_quantity(self, ch, method, properties, body):
        msg = body.decode()
        logging.info(f"Received message: {msg}")
        if msg == "EOF":
            self.eof_received += 1
            if int(self.eof_received) == int(self.counters_of_decades_per_author):
                logging.info("All EOF messages received")
                self.mq_connection_handler.send_message(self.output_queue_name, "EOF")
                logging.info("Sent EOF message to output queue")
        else:
            author, decades = msg.split(",")
            if int(decades) >= int(self.min_decades_to_filter):
                self.mq_connection_handler.send_message(self.output_queue_name, msg)
                logging.info(f"Sent message to output queue: {msg}")
            else:
                logging.info(f"Author {author} was filtered out. Decades: {decades} < {self.min_decades_to_filter}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
       
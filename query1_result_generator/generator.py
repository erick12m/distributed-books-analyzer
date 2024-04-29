from shared.mq_connection_handler import MQConnectionHandler
import logging
import signal
from shared import constants

class Generator:
    def __init__(self, input_exchange_name: str, output_exchange_name: str, input_queue_name: str, output_queue_name: str):
        self.output_queue = output_queue_name
        self.response_msg = "Q1 Results: "
        self.mq_connection_handler = MQConnectionHandler(output_exchange_name=output_exchange_name, 
                                                         output_queues_to_bind={self.output_queue: [self.output_queue]}, 
                                                         input_exchange_name=input_exchange_name, 
                                                         input_queues_to_recv_from=[input_queue_name])
        self.mq_connection_handler.setup_callback_for_input_queue(input_queue_name, self.__get_results)
        signal.signal(signal.SIGTERM, self.__handle_shutdown)

    def __handle_shutdown(self, signum, frame):
        logging.info("Shutting down generator")
        self.mq_connection_handler.close_connection()
        
    def start(self):
        self.mq_connection_handler.start_consuming()
        
    def __get_results(self, ch, method, properties, body):
        msg = body.decode()
        if msg == constants.FINISH_MSG:
            logging.info("Received EOF")
            self.mq_connection_handler.send_message(self.output_queue, self.response_msg)
            logging.info(f"Sent response message to output queue: {self.response_msg}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            self.mq_connection_handler.close_connection()
        else: 
            self.response_msg += '\n' + msg 
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        
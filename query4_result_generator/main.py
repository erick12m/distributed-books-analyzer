from shared.initializers import init_configs, init_log
import logging
from generator import Generator

def main():
    config_params = init_configs(["LOGGING_LEVEL", "INPUT_EXCHANGE", "OUTPUT_EXCHANGE", "INPUT_QUEUE_OF_BOOKS", "OUTPUT_QUEUE_OF_QUERY", "WORKER_NAME"])
    init_log(config_params["LOGGING_LEVEL"])
    generator = Generator(config_params["INPUT_EXCHANGE"], 
                          config_params["OUTPUT_EXCHANGE"], 
                          config_params["INPUT_QUEUE_OF_BOOKS"], 
                          config_params["OUTPUT_QUEUE_OF_QUERY"],
                          config_params["WORKER_NAME"])
    logging.info("Starting Generator")
    generator.start()
    
if __name__ == "__main__":
    main()
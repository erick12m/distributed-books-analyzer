import logging
import os
from configparser import ConfigParser

def init_log(logging_level):
    """
    Python custom logging initialization

    Current timestamp is added to be able to identify in docker
    compose logs the date when the log has arrived
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging_level,
        datefmt='%Y-%m-%d %H:%M:%S',
    )

def init_configs(env_vars_to_collect):
    """
    Collects the environment variables and returns them in a dictionary

    :param env_vars_to_collect: list of environment variables to collect
    :return: dictionary with the collected environment variables
    """
    try:
        parser = ConfigParser(os.environ)
        config_params = {}
        for env_var in env_vars_to_collect:
            config_params[env_var] = parser["DEFAULT"][env_var]
    except KeyError as e:
        raise KeyError("Key was not found. Error: {}".format(e))
    except ValueError as e:
        raise ValueError("Key could not be parsed. Error: {}".format(e))
    return config_params

def init_dyn_configs(config_params, num_of_dyn_output_queues, prefix):
    """
    Dynamically collects the environment variables related to dynamic output queues

    :param config_params: dictionary with the previously collected environment variables
    :param num_of_dyn_output_queues: number of dynamic output queues to collect
    :return: dictionary with the collected environment variables
    """
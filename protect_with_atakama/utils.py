import logging


LOG_FILE = "protect_with_atakama/logs/log.txt"


def init_logging():
    log_formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(process)d:%(thread)d [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y%m%d.%H%M%S"
    )

    log_file = logging.FileHandler(LOG_FILE)
    log_file.setFormatter(log_formatter)

    log_stream = logging.StreamHandler()
    log_stream.setFormatter(log_formatter)

    logging.root.addHandler(log_file)
    logging.root.addHandler(log_stream)
    logging.root.setLevel(logging.DEBUG)

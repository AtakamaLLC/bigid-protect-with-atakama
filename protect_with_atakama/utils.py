import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = "protect_with_atakama/logs"
LOG_FILE = f"{LOG_DIR}/log.txt"


def init_logging():
    """
    Init File and Stream log handlers
    """
    log_formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)-8s %(process)d:%(thread)d [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y%m%d.%H%M%S",
    )

    log_file = RotatingFileHandler(
        LOG_FILE, maxBytes=5000000, backupCount=5, encoding="utf-8"
    )
    log_file.setFormatter(log_formatter)

    log_stream = logging.StreamHandler()
    log_stream.setFormatter(log_formatter)

    logging.root.addHandler(log_file)
    logging.root.addHandler(log_stream)
    logging.root.setLevel(logging.DEBUG)


class ExecutionError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__()
        self.status = status
        self.message = message

    def __repr__(self):
        return f"{self.status} - {self.message}"


class DataSourceError(ExecutionError):
    pass


class ScanResultsError(ExecutionError):
    pass

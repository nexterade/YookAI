"""Minimal YookAI logger."""
import logging

class _TimeFormatter(logging.Formatter):
    def format(self, record):
        timestamp=self.formatTime(record, "%H:%M:%S")
        return f"[{timestamp}] {record.levelname}: {record.getMessage()}"

def setup_logger(name):
    logger=logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate=False
    if not logger.handlers:
        handler=logging.StreamHandler()
        handler.setFormatter(_TimeFormatter())
        logger.addHandler(handler)
    return logger

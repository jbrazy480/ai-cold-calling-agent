"""Small JSON log formatter for operational events without credentials or lead data."""
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname, "event": record.getMessage(), "logger": record.name}
        for key in ("code", "error_type"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure():
    logger = logging.getLogger("coldcaller")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

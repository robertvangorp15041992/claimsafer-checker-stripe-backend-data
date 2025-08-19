import logging
import json
import re
import sys
from datetime import datetime

SECRET_RE = re.compile(r"(authorization|api[_-]?key|password|token)[\"':= ]+([^,\\s]+)", re.I)

def redact_secrets(msg):
    return SECRET_RE.sub(r"\1=***", msg)

class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_secrets(str(record.getMessage())),
        }
        if hasattr(record, "request_id"):
            log["request_id"] = record.request_id
        if hasattr(record, "path"):
            log["path"] = record.path
        if hasattr(record, "method"):
            log["method"] = record.method
        if hasattr(record, "status"):
            log["status"] = record.status
        if hasattr(record, "latency_ms"):
            log["latency_ms"] = record.latency_ms
        if hasattr(record, "user_email"):
            log["user_email"] = record.user_email
        return json.dumps(log)

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

def get_logger(name="app"):
    return logging.getLogger(name)

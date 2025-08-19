from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from functools import wraps
import time

http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
webhook_events_total = Counter(
    "webhook_events_total", "Webhook events processed", ["type", "outcome"]
)
emails_sent_total = Counter(
    "emails_sent_total", "Emails sent", ["template"]
)

def instrument_route(path_template):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            method = request.method if request else "UNKNOWN"
            start = time.time()
            try:
                resp = await func(*args, **kwargs)
                status = getattr(resp, "status_code", 200)
            except Exception:
                status = 500
                raise
            finally:
                http_requests_total.labels(method, path_template, status).inc()
                http_request_duration_seconds.labels(method, path_template).observe(time.time() - start)
            return resp
        return wrapper
    return decorator

def increment_webhook_event(event_type, outcome):
    webhook_events_total.labels(event_type, outcome).inc()

def increment_email_sent(template):
    emails_sent_total.labels(template).inc()

def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

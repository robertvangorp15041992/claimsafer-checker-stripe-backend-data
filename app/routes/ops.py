from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from app.db import get_db
from sqlalchemy.orm import Session
from app.models import WebhookEvent
from app.dependencies import require_role
from app.metrics import metrics_endpoint
import os
import socket
import stripe
from datetime import datetime

router = APIRouter()

start_time = datetime.utcnow()

@router.get("/healthz")
def healthz():
    uptime = (datetime.utcnow() - start_time).total_seconds()
    return {"status": "ok", "uptime_seconds": uptime}

@router.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    checks = {}
    # DB check
    try:
        db.execute("SELECT 1")
        checks["db"] = True
    except Exception:
        checks["db"] = False
    # SMTP check
    try:
        host = os.getenv("SMTP_HOST", "localhost")
        port = int(os.getenv("SMTP_PORT", 587))
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        checks["smtp"] = True
    except Exception:
        checks["smtp"] = False
    # Stripe check
    stripe_ok = None
    if os.getenv("READINESS_STRIPE_CHECK", "true").lower() == "true" and os.getenv("STRIPE_API_KEY"):
        try:
            stripe.Balance.retrieve(timeout=2)
            stripe_ok = True
        except Exception:
            stripe_ok = False
    else:
        stripe_ok = "skipped"
    checks["stripe"] = stripe_ok
    checks["ok"] = all(v is True or v == "skipped" for v in checks.values())
    return checks

@router.get("/metrics")
def metrics():
    return metrics_endpoint()

@router.post("/internal/replay-webhook")
def replay_webhook(request: Request, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    data = request.json() if request.headers.get("content-type") == "application/json" else request.form()
    event_id = data.get("stripe_event_id")
    event = db.query(WebhookEvent).filter_by(stripe_event_id=event_id).first()
    if not event:
        return JSONResponse({"error": "Event not found"}, status_code=404)
    # Reconstruct event dict and call handler
    from app.main import stripe_webhook
    import json
    event_dict = json.loads(event.payload)
    # Call the handler (simulate request)
    # You may need to adapt this to your actual handler signature
    result = stripe_webhook(event_dict, db)
    return {"status": "replayed", "result": result}

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.dependencies import require_role, get_current_user
from app.db import get_db
from app.services.usage import get_usage_for_date, get_user_usage_days
from app.models import User
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin/usage", response_class=HTMLResponse)
def admin_usage(
    request: Request,
    date: str = Query(None),
    db: Session = Depends(get_db),
    admin = Depends(require_role("admin"))
):
    if not date:
        date = datetime.utcnow().date().isoformat()
    rows = get_usage_for_date(db, date)
    return templates.TemplateResponse("admin_usage.html", {
        "request": request,
        "rows": rows,
        "date": date
    })

@router.get("/admin/users/{email}/usage")
def user_usage_history(
    email: str,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    admin = Depends(require_role("admin"))
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return JSONResponse({"detail": "User not found"}, status_code=404)
    usage = get_user_usage_days(db, user.id, days)
    return usage

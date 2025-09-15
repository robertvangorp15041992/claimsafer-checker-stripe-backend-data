import uuid
import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.logging_config import get_logger
import os

logger = get_logger("app")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class TimingAccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = None
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            status = 500
            raise
        finally:
            latency = int((time.time() - start) * 1000)
            logger.info(
                "",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "path": request.url.path,
                    "method": request.method,
                    "status": status,
                    "latency_ms": latency,
                }
            )
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if os.getenv("ENABLE_HSTS", "true").lower() == "true":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        csp = os.getenv("CSP", "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'")
        response.headers["Content-Security-Policy"] = csp
        return response

class ErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            import traceback
            from fastapi import HTTPException
            request_id = getattr(request.state, "request_id", None)
            if isinstance(exc, HTTPException):
                code = {
                    404: "NOT_FOUND",
                    401: "UNAUTHORIZED",
                    403: "FORBIDDEN",
                    400: "BAD_REQUEST"
                }.get(exc.status_code, "HTTP_ERROR")
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error": {"message": exc.detail, "code": code, "request_id": request_id}}
                )
            logger.error(f"Unhandled error: {exc} {traceback.format_exc()}", extra={"request_id": request_id})
            return JSONResponse(
                status_code=500,
                content={"error": {"message": "Internal server error", "code": "INTERNAL_SERVER_ERROR", "request_id": request_id}}
            )

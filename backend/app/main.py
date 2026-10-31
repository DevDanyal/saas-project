from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router
from app.api.routes.emails import router as emails_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.preferences import router as preferences_router
from app.api.routes.reports import router as reports_router
from app.api.routes.teams import router as teams_router
from app.api.routes.unsubscribe import router as unsubscribe_router
from app.api.routes.users import router as users_router
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Inbox Assistant API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
    max_age=600,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.frontend_url != "*":
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: https:; "
            f"font-src 'self' data:; "
            f"connect-src 'self' {settings.frontend_url} https://api.stripe.com; "
            f"frame-src https://js.stripe.com https://hooks.stripe.com;"
        )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response


app.include_router(auth_router)
app.include_router(emails_router)
app.include_router(notifications_router)
app.include_router(preferences_router)
app.include_router(users_router)
app.include_router(billing_router)
app.include_router(teams_router)
app.include_router(reports_router)
app.include_router(unsubscribe_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    return {"status": "ready"}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}
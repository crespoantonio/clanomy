import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Response, Request, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, text
from src.db.session import get_session, init_db, run_migrations
from src.core.config import settings
from src.core.http_client import HTTPClientManager
from src.core.security import verify_origin_secret
from src.api.routes.telegram import router as telegram_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database & run pending migrations
    try:
        run_migrations()
    except Exception as e:
        from src.core.security import sanitize_exception_message
        sanitized_msg = sanitize_exception_message(e, settings.DATABASE_URL)
        logger.critical(f"Database initialization/migration failed: {sanitized_msg}")
        raise RuntimeError(f"Startup aborted: database migration failed: {sanitized_msg}") from None
        
    # Initialize HTTP client pool
    HTTPClientManager().init()
    
    # Start background daily trial lifecycle notification scheduler
    from src.services.notification_scheduler import start_notification_scheduler, stop_notification_scheduler
    try:
        start_notification_scheduler()
    except Exception as e:
        logger.warning(f"Failed to start notification scheduler: {e}", exc_info=True)

    yield
    
    # Stop notification scheduler
    try:
        await stop_notification_scheduler()
    except Exception as e:
        logger.warning(f"Error stopping notification scheduler: {e}", exc_info=True)

    # Close HTTP client pool
    await HTTPClientManager().close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

@app.middleware("http")
async def security_and_origin_middleware(request: Request, call_next):
    # 1. Cloudflare Origin Shield Verification (if CLOUDFLARE_ORIGIN_SECRET is configured)
    # Allows /health probe pass-through without origin secret for uptime monitoring
    if settings.CLOUDFLARE_ORIGIN_SECRET and request.url.path != "/health":
        origin_header = request.headers.get("X-Origin-Verify-Secret") or request.headers.get("X-Clanomy-Origin-Key")
        if not verify_origin_secret(origin_header):
            logger.warning(f"Direct origin access attempt blocked on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Direct origin access forbidden"}
            )

    # 2. Process Request
    response = await call_next(request)

    # 3. HTTP Security Headers Injection
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if "server" in response.headers:
        del response.headers["server"]

    return response

# Register routers
app.include_router(telegram_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}


@app.get("/health")
async def health_check(response: Response, session: Session = Depends(get_session)):
    try:
        # Check database connectivity
        session.exec(text("SELECT 1")).one()
        return {
            "status": "healthy",
            "database": "connected",
            "project": settings.PROJECT_NAME
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "Database connection failed"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

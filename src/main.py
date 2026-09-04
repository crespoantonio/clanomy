import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Response, Request, status
from fastapi.responses import JSONResponse, FileResponse
from sqlmodel import Session, text
from src.db.session import get_session, init_db, run_migrations
from src.core.config import settings
from src.core.http_client import HTTPClientManager
from src.core.security import verify_origin_secret
from src.api.routes.telegram import router as telegram_router
from src.api.routes.lemonsqueezy import router as lemonsqueezy_router
from src.api.routes.internal_jobs import router as internal_jobs_router
from src.api.routes.simulate import router as simulate_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("clanomy")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation: Fail fast if SaaS mode is configured without Cloud AI credentials in non-test environments
    if settings.ENABLE_SUBSCRIPTIONS and not (settings.AI_API_KEY and settings.AI_API_KEY.strip()):
        import os
        if not os.environ.get("PYTEST_CURRENT_TEST") and not settings.DATABASE_URL.startswith("sqlite"):
            logger.critical("Startup aborted: Commercial SaaS mode (ENABLE_SUBSCRIPTIONS=true) requires AI_API_KEY for cloud inference.")
            raise RuntimeError("Startup aborted: Missing AI_API_KEY for Groq Cloud deployment.")

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
    
    # In SaaS/cloud mode, external triggers (e.g. GCP Cloud Scheduler) invoke /api/internal/jobs/trial-lifecycle.
    # In-process scheduler is only started if explicitly enabled via ENABLE_INTERNAL_SCHEDULER.
    if settings.ENABLE_INTERNAL_SCHEDULER:
        from src.services.notification_scheduler import start_notification_scheduler
        try:
            start_notification_scheduler()
            logger.info("Internal NotificationScheduler started.")
        except Exception as e:
            logger.warning(f"Failed to start notification scheduler: {e}", exc_info=True)
    else:
        logger.info("Internal in-memory scheduler is disabled. Trial lifecycle jobs are managed via /api/internal/jobs/trial-lifecycle.")

    yield
    
    # Graceful shutdown sequence for Render rolling deployments
    logger.info("Shutdown signal received. Initiating graceful task draining...")
    if settings.ENABLE_INTERNAL_SCHEDULER:
        from src.services.notification_scheduler import stop_notification_scheduler
        try:
            await stop_notification_scheduler()
        except Exception as e:
            logger.warning(f"Error stopping notification scheduler: {e}", exc_info=True)

    # Allow in-flight Groq inference & Telegram background webhook tasks to complete
    await asyncio.sleep(3.0)

    # Close HTTP client pool
    await HTTPClientManager().close()

    # Cleanly dispose database engine connection pool
    try:
        from src.db.session import engine
        engine.dispose()
        logger.info("PostgreSQL connection pool disposed cleanly.")
    except Exception as e:
        logger.warning(f"Error disposing database engine: {e}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

@app.middleware("http")
async def security_and_origin_middleware(request: Request, call_next):
    # Log incoming request path (scrubbing query params to prevent sensitive data leakage)
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Incoming HTTP {request.method} {request.url.path} from {client_ip}")

    # 1. Cloudflare Origin Shield Verification (if CLOUDFLARE_ORIGIN_SECRET is configured)
    # Allows /health probe, Telegram webhook, Lemon Squeezy webhook, and internal cron jobs pass-through
    if settings.CLOUDFLARE_ORIGIN_SECRET and request.url.path not in (
        "/health",
        "/api/v1/telegram/webhook",
        "/api/webhooks/lemonsqueezy",
        "/api/internal/jobs/trial-lifecycle"
    ):
        origin_header = request.headers.get("X-Origin-Verify-Secret") or request.headers.get("X-Clanomy-Origin-Key")
        if not verify_origin_secret(origin_header):
            logger.warning(f"Direct origin access attempt blocked on {request.url.path} from {client_ip}")
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

_LANDING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "landing")

# Register routers
app.include_router(telegram_router, prefix="/api/v1")
app.include_router(simulate_router, prefix="/api/v1")
app.include_router(lemonsqueezy_router)
app.include_router(internal_jobs_router)

@app.get("/", include_in_schema=False)
async def root():
    return {
        "status": "online",
        "service": "Clanomy API",
        "version": "1.0.0"
    }

@app.get("/landing", include_in_schema=False)
async def landing_page():
    index_path = os.path.join(_LANDING_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return Response(status_code=404)

@app.get("/styles.css", include_in_schema=False)
async def landing_styles():
    css_path = os.path.join(_LANDING_DIR, "styles.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    return Response(status_code=404)

@app.get("/script.js", include_in_schema=False)
async def landing_script():
    js_path = os.path.join(_LANDING_DIR, "script.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/translations.js", include_in_schema=False)
async def landing_translations():
    trans_path = os.path.join(_LANDING_DIR, "translations.js")
    if os.path.exists(trans_path):
        return FileResponse(trans_path, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/assets/{file_path:path}", include_in_schema=False)
async def landing_assets(file_path: str):
    asset_file = os.path.join(_LANDING_DIR, "assets", file_path)
    if os.path.exists(asset_file) and os.path.isfile(asset_file):
        return FileResponse(asset_file)
    return Response(status_code=404)


@app.get("/health")
async def health_check(response: Response, session: Session = Depends(get_session)):
    health = {
        "status": "healthy",
        "database": "connected",
        "project": settings.PROJECT_NAME
    }
    try:
        # Check database connectivity
        session.exec(text("SELECT 1")).one()
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "Database connection failed"
        }

    # Lightweight probe for self-hosted Ollama backend
    if not settings.AI_API_KEY:
        try:
            from src.core.http_client import get_http_client
            client = get_http_client()
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
            health["ollama"] = "connected" if r.status_code == 200 else "degraded"
        except Exception:
            health["ollama"] = "unreachable"

    return health

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

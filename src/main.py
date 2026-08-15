from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlmodel import Session, text
from src.db.session import get_session, init_db
from src.core.config import settings
from src.api.routes.telegram import router as telegram_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    try:
        init_db()
    except Exception as e:
        print(f"CRITICAL: Database initialization failed: {e}")
        # In a real production app, we might want to retry or exit
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Register routers
app.include_router(telegram_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

@app.get("/health")
async def health_check(session: Session = Depends(get_session)):
    try:
        # Check database connectivity
        session.exec(text("SELECT 1")).one()
        return {
            "status": "healthy",
            "database": "connected",
            "project": settings.PROJECT_NAME
        }
    except Exception:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "Database connection failed"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from src.db.session import get_session
from src.core.security import verify_cron_secret
from src.services.notification_scheduler import run_daily_trial_notifications

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/jobs", tags=["Internal Jobs"])

@router.post("/trial-lifecycle")
async def trigger_trial_lifecycle_job(
    x_job_secret: Optional[str] = Header(default=None, alias="X-Job-Secret"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    session: Session = Depends(get_session)
):
    """
    HTTP endpoint to trigger the daily trial lifecycle job (Day 50 warnings & Day 60 transitions).
    Designed to be invoked reliably once a day by GCP Cloud Scheduler, Supabase pg_cron, or external cron.
    Protected by constant-time verification of X-Job-Secret or Authorization Bearer header.
    """
    token = x_job_secret or authorization
    if not verify_cron_secret(token):
        logger.warning("Unauthorized attempt to trigger trial lifecycle job.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing job secret token."
        )

    logger.info("Executing trial lifecycle job triggered via internal HTTP endpoint...")
    try:
        result = await run_daily_trial_notifications(session=session)
        logger.info(f"Trial lifecycle job completed successfully: {result}")
        return {
            "status": "success",
            "job": "trial-lifecycle",
            "day_50_processed": result.get("day_50_processed", 0),
            "day_60_processed": result.get("day_60_processed", 0),
            "daily_quotas_reset": result.get("daily_quotas_reset", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error executing trial lifecycle job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error while executing trial lifecycle job."
        )

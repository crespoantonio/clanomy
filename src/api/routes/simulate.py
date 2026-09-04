"""
Simulation Route for Clanomy End-to-End Extraction & Response Testing.
Allows testing natural language messages against live AI models (Ollama, Gemini, Groq)
bypassing Telegram Webhook network requirements while strictly enforcing authorization.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.security import verify_simulation_secret
from src.core.llm.factory import get_llm_provider
from src.core.llm.providers.gemini_provider import GeminiProvider
from src.core.llm.providers.ollama_provider import OllamaProvider
from src.core.llm.providers.openai_provider import OpenAICompatibleProvider
from src.services.extraction.service import ExtractionService
from src.services.ai_orchestrator import AIOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["Message Simulation"])


class SimulateMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw message text sent by user")
    default_currency: Optional[str] = Field("USD", description="Default workspace currency (e.g. USD, ARS, EUR)")
    model: Optional[str] = Field(None, description="Optional specific AI model name (e.g. gemini-3.1-flash-lite, llama3)")


class SimulateMessageResponse(BaseModel):
    status: str
    user_message: str
    bot_response: str
    action: Optional[str] = None
    item_count: int = 0
    items: List[Dict[str, Any]] = []
    provider: str
    duration_seconds: float


@router.post("/message", response_model=SimulateMessageResponse)
async def simulate_message(
    payload: SimulateMessageRequest,
    x_simulation_secret: Optional[str] = Header(None, alias="X-Simulation-Secret"),
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-Api-Key"),
    x_ai_api_key: Optional[str] = Header(None, alias="X-AI-Api-Key"),
    x_ai_provider: Optional[str] = Header(None, alias="X-AI-Provider"),
    x_ai_model: Optional[str] = Header(None, alias="X-AI-Model"),
):
    # 1. Secret 1 Validation: Simulation Authorization Token
    if not verify_simulation_secret(x_simulation_secret):
        logger.warning("Simulation endpoint accessed with missing or invalid X-Simulation-Secret.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing simulation secret token."
        )

    # 2. Determine and configure LLM provider
    target_provider = (x_ai_provider or "").lower().strip()
    if not target_provider:
        target_provider = settings.effective_ai_provider

    target_model = payload.model or x_ai_model

    extraction_svc = None
    if target_provider in ("gemini", "google"):
        # Secret 2 Validation: Gemini API Key passed via header (never server env)
        gemini_key = (x_gemini_api_key or x_ai_api_key or "").strip()
        if not gemini_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Header 'X-Gemini-Api-Key' (or 'X-AI-Api-Key') is required when using the Gemini provider."
            )
        provider_instance = GeminiProvider(model=target_model, api_key=gemini_key)
        extraction_svc = ExtractionService(provider=provider_instance)
    elif target_provider == "ollama":
        provider_instance = OllamaProvider(model=target_model)
        extraction_svc = ExtractionService(provider=provider_instance)
    elif target_provider in ("groq", "openai", "openai_compatible", "cloud_ai"):
        # Secret 2 Validation: Cloud API Key passed via header (never server env)
        api_key = (x_ai_api_key or "").strip()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Header 'X-AI-Api-Key' is required when simulating with '{target_provider}'."
            )
        provider_instance = OpenAICompatibleProvider(model=target_model, api_key=api_key)
        extraction_svc = ExtractionService(provider=provider_instance)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported simulation provider: '{target_provider}'. Supported: 'gemini', 'ollama', 'groq', 'openai'."
        )

    # 3. Execute End-to-End Pipeline Simulation (Strictly Read-Only / dry_run=True)
    orchestrator = AIOrchestrator()
    try:
        result = await orchestrator.simulate_message(
            text=payload.text,
            default_currency=(payload.default_currency or "USD").upper(),
            dry_run=True,
            user_id=None,
            family_id=None,
            extraction_service=extraction_svc
        )
        result["provider"] = target_provider
        return result
    except Exception as e:
        logger.error(f"Error executing message simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )

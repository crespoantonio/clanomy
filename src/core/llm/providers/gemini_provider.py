import logging
from typing import Any, Optional, Type
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, retry_if_exception

from src.core.config import settings
from src.core.http_client import get_http_client, make_timeout
from src.core.llm.base import BaseLLMProvider, PayloadTruncatedError
from src.core.llm.retry import is_retryable_provider_error, ProviderRateLimitWait

logger = logging.getLogger(__name__)


def _log_gemini_token_usage(data: dict, model: str) -> None:
    """Logs token consumption and reports cache HIT / MISS status for Gemini requests."""
    usage = data.get("usageMetadata")
    if not isinstance(usage, dict):
        return
    prompt_tokens = usage.get("promptTokenCount", 0)
    candidates_tokens = usage.get("candidatesTokenCount", 0)
    cached_tokens = usage.get("cachedContentTokenCount", 0)

    if cached_tokens > 0:
        logger.info(
            f"[Prompt Cache HIT] {cached_tokens}/{prompt_tokens} tokens served from cache for {model} (output: {candidates_tokens})"
        )
    else:
        logger.info(
            f"[Prompt Cache MISS] 0/{prompt_tokens} cached (full inference run) for {model} (output: {candidates_tokens})"
        )


ALLOWED_GEMINI_FIELDS = {
    "type", "format", "description", "nullable", "enum",
    "maxItems", "minItems", "properties", "required", "minProperties",
    "maxProperties", "minLength", "maxLength", "pattern", "example",
    "anyOf", "propertyOrdering", "items", "minimum", "maximum"
}


def clean_gemini_schema(schema_dict: dict) -> dict:
    """
    Converts Pydantic v2 JSON Schema to Gemini's OpenAPI 3.0 compatible subset.
    - Inlines all definitions from $defs ($ref).
    - Flattens nullable fields from anyOf: [{type: ...}, {type: null}] to {type: ..., nullable: True}.
    - Maps JSON Schema Draft 2020 keywords not supported by Gemini OpenAPI (exclusiveMinimum -> minimum).
    - Removes unsupported metadata (title, default, etc.).
    """
    import copy
    d = copy.deepcopy(schema_dict)
    defs = d.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].split("/")[-1]
                if ref_name in defs:
                    return resolve(copy.deepcopy(defs[ref_name]))

            if "anyOf" in node:
                non_null = [s for s in node["anyOf"] if s.get("type") != "null"]
                if len(non_null) == 1:
                    primary = resolve(non_null[0])
                    node.clear()
                    node.update(primary)
                    node["nullable"] = True

            # Convert JSON Schema exclusiveMinimum to OpenAPI 3.0 minimum
            if "exclusiveMinimum" in node:
                node["minimum"] = node.pop("exclusiveMinimum")
            if "exclusiveMaximum" in node:
                node["maximum"] = node.pop("exclusiveMaximum")

            # Remove unsupported keywords that cause Google API validation errors
            node.pop("title", None)
            node.pop("default", None)

            for k in list(node.keys()):
                node[k] = resolve(node[k])
            return node
        elif isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved = resolve(d)

    # For extraction schemas containing "items", remove redundant root transaction scalars
    # so Gemini's constrained decoding grammar cannot shortcut through single scalars.
    props = resolved.get("properties", {})
    if "items" in props and "action" in props:
        for s in {
            "amount", "concept", "category", "currency", "type",
            "transaction_date", "due_date", "is_scheduled_bill"
        }:
            props.pop(s, None)

    return resolved


DEFAULT_GEMINI_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]


class GeminiProvider(BaseLLMProvider):
    """Native raw HTTP provider for Google Gemini API."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if model:
            self.model = model
        elif settings.AI_MODEL and "gemini" in settings.AI_MODEL.lower():
            self.model = settings.AI_MODEL
        else:
            self.model = "gemini-2.5-flash-lite"
        self.api_key = api_key or settings.AI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=ProviderRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        timeout: float = 30.0,
        max_tokens: int = 2000
    ) -> str:
        client = get_http_client()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }

        raw_schema = schema.model_json_schema()
        gemini_schema = clean_gemini_schema(raw_schema)

        generation_config = {
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema
        }
        if "gemini-3" in self.model.lower():
            thinking_lvl = (getattr(settings, "AI_GEMINI_THINKING_LEVEL", "low") or "low").lower()
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_lvl
            }

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "safetySettings": DEFAULT_GEMINI_SAFETY_SETTINGS,
            "generationConfig": generation_config
        }

        logger.info(f"Calling native Gemini model {self.model}...")
        response = await client.post(url, headers=headers, json=payload, timeout=make_timeout(timeout, default_read=30.0))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error ({e.response.status_code}): {e.response.text}")
            raise e
        data = response.json()

        _log_gemini_token_usage(data, self.model)

        candidates = data.get("candidates", [])
        if not candidates:
            # Check for prompt-level feedback block
            block_reason = data.get("promptFeedback", {}).get("blockReason")
            if block_reason:
                raise ValueError(f"Gemini prompt blocked: {block_reason}")
            raise ValueError("No candidate returned by Gemini API")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason == "MAX_TOKENS":
            raise PayloadTruncatedError("Gemini output exceeded maxOutputTokens and was truncated.")
        elif finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            raise ValueError(f"Gemini candidate blocked by policy: {finish_reason}")

        parts = candidate.get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError("Empty completion payload received from Gemini API")

        return parts[0]["text"].strip()

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=ProviderRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        timeout: float = 30.0
    ) -> str:
        client = get_http_client()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }

        generation_config = {
            "maxOutputTokens": 600
        }
        if "gemini-3" in self.model.lower():
            thinking_lvl = (getattr(settings, "AI_GEMINI_THINKING_LEVEL", "low") or "low").lower()
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_lvl
            }

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "safetySettings": DEFAULT_GEMINI_SAFETY_SETTINGS,
            "generationConfig": generation_config
        }

        logger.info(f"Calling native Gemini model {self.model} for text...")
        response = await client.post(url, headers=headers, json=payload, timeout=make_timeout(timeout, default_read=30.0))
        response.raise_for_status()
        data = response.json()

        _log_gemini_token_usage(data, self.model)

        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
            logger.warning(f"Gemini candidate blocked by policy: {finish_reason}")
            return "I am sorry, but I cannot process this query as it violates safety and usage guidelines."

        parts = candidate.get("content", {}).get("parts", [])
        return parts[0].get("text", "").strip() if parts else ""

    @retry(
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        wait=ProviderRateLimitWait(min_wait=settings.AI_RETRY_BACKOFF_MIN, max_wait=30.0),
        retry=retry_if_exception(is_retryable_provider_error),
        reraise=True
    )
    async def complete_chat_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        tool_declarations: list[dict],
        tool_executor: Any,
        temperature: float = 0.2,
        timeout: float = 30.0,
        max_tokens: int = 1000,
        max_iterations: int = 3
    ) -> tuple[str, list[dict]]:
        """
        Executes a native tool-calling conversation with Gemini v1beta API.
        Iteratively runs tool calls returned by Gemini, feeds back results,
        and returns the final synthesized natural language answer and list of executed calls.
        """
        client = get_http_client()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }

        generation_config = {
            "maxOutputTokens": max_tokens,
            "temperature": temperature
        }
        if "gemini-3" in self.model.lower():
            thinking_lvl = (getattr(settings, "AI_GEMINI_THINKING_LEVEL", "low") or "low").lower()
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_lvl
            }

        contents = [
            {"role": "user", "parts": [{"text": user_prompt}]}
        ]

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents,
            "tools": [
                {"functionDeclarations": tool_declarations}
            ],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "AUTO"
                }
            },
            "safetySettings": DEFAULT_GEMINI_SAFETY_SETTINGS,
            "generationConfig": generation_config
        }

        executed_calls: list[dict] = []

        for iteration in range(max_iterations):
            logger.info(f"Calling native Gemini model {self.model} with {len(tool_declarations)} tools (iter {iteration + 1})...")
            response = await client.post(url, headers=headers, json=payload, timeout=make_timeout(timeout, default_read=30.0))
            response.raise_for_status()
            data = response.json()

            _log_gemini_token_usage(data, self.model)

            candidates = data.get("candidates", [])
            if not candidates:
                return "", executed_calls

            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            if not parts:
                return "", executed_calls

            # Check if Gemini requested a function call
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not function_calls:
                # No tool called -> Gemini returned its direct final response
                final_text = " ".join([p.get("text", "") for p in parts if "text" in p]).strip()
                return final_text, executed_calls

            # Append the model's message (which includes the functionCall) to the conversation
            payload["contents"].append({
                "role": "model",
                "parts": parts
            })

            # Execute all requested function calls
            function_responses = []
            for fc in function_calls:
                fn_name = fc.get("name")
                fn_args = fc.get("args") or {}
                logger.info(f"[Agentic Tool Call] Gemini invoking tool '{fn_name}' with args {fn_args}")

                try:
                    tool_output = await tool_executor(fn_name, fn_args)
                except Exception as ex:
                    logger.error(f"[Agentic Tool Error] Tool '{fn_name}' failed: {ex}")
                    tool_output = {"status": "error", "message": str(ex)}

                executed_calls.append({"name": fn_name, "args": fn_args, "output": tool_output})

                function_responses.append({
                    "functionResponse": {
                        "name": fn_name,
                        "response": tool_output
                    }
                })

            # Append functionResponse turn to conversation
            payload["contents"].append({
                "role": "user",
                "parts": function_responses
            })

        # Fallback if loop exceeded max iterations
        return "I retrieved your financial records, but couldn't finalize the answer.", executed_calls

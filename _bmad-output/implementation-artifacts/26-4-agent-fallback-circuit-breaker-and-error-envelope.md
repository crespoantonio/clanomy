---
story_id: "26.4"
epic_id: "26"
title: "Agent Fallback Circuit Breaker & Structured Tool Error Envelope"
status: "done"
priority: "high"
author: "Winston, Amelia, Murat & Dr. Quinn"
date: "2026-11-14"
---

# Story 26.4: Agent Fallback Circuit Breaker & Structured Tool Error Envelope

## 1. Overview & Context

In the Harness Engineering audit, the engineering team surfaced two critical reliability risks in Clanomy's agent execution runtime:
1. **Unprotected Iteration Exhaustion / Provider Failure:** In `GeminiProvider.complete_chat_with_tools`, if the agent loop hits `max_iterations = 3` without emitting a final synthesis, or if an upstream timeout/API error occurs, `AgentService.run` returns an empty string `""` or bubbles an unhandled exception to the Telegram handler.
2. **Raw String Tool Errors:** In `src/services/agent/tools.py#L388`, when a tool execution encounters an error, it returns `{"error": str(e)}`. Raw Python exception strings entering model context risk exposing internal tracebacks to users and leave the LLM unequipped to formulate semantic recoveries.

This story hardens the agent execution harness:
1. **Structured Tool Error Envelope:** Standardizes all tool returns in `execute_agent_tool` into a typed envelope (`status: "success" | "error"`, `data`, and `error: {code, message, recovery_hint}`).
2. **Fallback Circuit Breaker:** In `AgentService.run`, wraps the agentic tool-calling turn with an automated circuit breaker. If the model loop returns empty/whitespace text, times out, or fails, the harness automatically falls back to `DecoupledQueryPipeline` to generate a verified, deterministic response.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Clanomy User,  
I want the agentic assistant to handle tool errors and execution iteration limits with structured recovery envelopes and deterministic fallbacks,  
So that I never see raw stack traces, technical error jargon, or empty responses if an AI provider or tool call stumbles.

### Acceptance Criteria
- [x] **AC 26.4.1 (Structured Tool Error Envelope):** In `src/services/agent/tools.py`, wrap all tool execution outputs in a structured envelope with `status`, `data` on success, or `error` (`code`, `message`, `recovery_hint`) on failure.
- [x] **AC 26.4.2 (Sanitized Exception Boundaries):** Prevent low-level Python exception traces or internal paths from returning into model context.
- [x] **AC 26.4.3 (Fallback Circuit Breaker):** In `src/services/agent/service.py`, if `complete_chat_with_tools` returns empty/whitespace text or encounters an unhandled provider error, catch the failure and invoke `DecoupledQueryPipeline` to provide a mathematically verified fallback response.
- [x] **AC 26.4.4 (Telemetry Logging):** Log structured warnings when the circuit breaker trips, identifying user ID, family ID, prompt, and failure reason.
- [x] **AC 26.4.5 (Regression Test Verification):** Add unit tests verifying both structured error envelopes and circuit breaker fallback activation.

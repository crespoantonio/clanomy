---
story_id: "26.2"
epic_id: "26"
title: "Agentic Multi-Turn Sliding-Window Memory & Reference Resolution"
status: "done"
priority: "high"
author: "Winston, Amelia, Sally & John"
date: "2026-11-14"
---

# Story 26.2: Agentic Multi-Turn Sliding-Window Memory & Reference Resolution

## 1. Overview & Context

In `src/services/agent/service.py`, `AgentService.run()` currently operates in a completely stateless manner:
- `user_prompt` receives only `text: str`.
- Follow-up conversational inquiries (e.g. *"And how much of that was dining out?"* or *"What about last week?"*) fail because previous turns and referenced entities are not preserved in the context window.
- In `GeminiProvider.complete_chat_with_tools`, `contents` was hardcoded to a single user turn: `[{"role": "user", "parts": [{"text": user_prompt}]}]`.

This story implements bounded sliding-window conversation memory:
1. **Bounded Session Store:** Implements an in-memory, thread-safe LRU session cache (`_BoundedAgentSessionStore`) storing the last 3 turns (up to 6 messages: user + assistant) per `(family_id, user_id)`.
2. **Multi-Turn Context Injection:** Extends `GeminiProvider.complete_chat_with_tools` and `AgentService.run` to accept and pass bounded conversation history into the model's chat content structure.
3. **Reference Resolution & State Retention:** Updates dialogue state post-turn, with LRU eviction to prevent memory leaks and a `clear_session()` interface for explicit resets.

---

## 2. User Story & Acceptance Criteria

### User Story
As a Clanomy User,  
I want the conversational agent to retain recent conversation context during my active chat session,  
So that I can ask follow-up questions and drill down into financial details naturally without re-specifying the full query context every turn.

### Acceptance Criteria
- [x] **AC 26.2.1 (Bounded Session Store):** Implement `_BoundedAgentSessionStore` with a hard limit on maximum sessions (default 1,000) and an LRU eviction strategy.
- [x] **AC 26.2.2 (Sliding-Window Bounding):** Bounded history per session retains at most 3 past turns (max 6 message objects) to prevent context drift and token explosion.
- [x] **AC 26.2.3 (Gemini Multi-Turn Tool Calling):** Support `chat_history: Optional[list[dict]] = None` in `GeminiProvider.complete_chat_with_tools` to prepend past conversation turns before the latest user message.
- [x] **AC 26.2.4 (Session Lifecycle Management):** Add `clear_session(user_id, family_id)` on `AgentService` to allow atomic clearing of session state.
- [x] **AC 26.2.5 (Session Inactivity TTL):** Automatically expire session context if idle time exceeds 15 minutes (900s), ensuring subsequent messages hours later start with a clean slate.
- [x] **AC 26.2.6 (Automated Test Verification):** Ensure follow-up query test cases pass without regressions in tool selection or execution.

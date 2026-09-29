"""
Evaluation CLI Runner for Clanomy Real-World Extraction Dataset.
Executes test cases from tests/data/llm_extraction_dataset.py against live models
(Ollama, Gemini, Groq, OpenAI) either in-process or via the HTTP simulation endpoint.
"""

import os
import sys
import time
import argparse
import asyncio
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set fallback development encryption key dynamically if missing or placeholder
if os.environ.get("ENCRYPTION_KEY") in (None, "", "your_fernet_encryption_key_here"):
    import base64
    import secrets
    os.environ["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

from src.core.config import settings
from src.core.llm.providers.gemini_provider import GeminiProvider
from src.core.llm.providers.ollama_provider import OllamaProvider
from src.core.llm.providers.openai_provider import OpenAICompatibleProvider
from src.services.extraction.service import ExtractionService
from src.services.ai_orchestrator import AIOrchestrator
from tests.data.llm_extraction_dataset import DATASET


def match_items_with_types(
    expected_amounts: List[float],
    expected_types: List[str],
    extracted_amounts: List[float],
    extracted_types: List[str],
    tolerance: float = 0.5
) -> tuple[bool, bool, bool]:
    """
    Evaluates:
      1. count_match: len(expected) == len(extracted)
      2. amount_match: all amounts match within tolerance
      3. type_match: each matched amount corresponds to the correct transaction type (income / expense)
    """
    count_match = (len(expected_amounts) == len(extracted_amounts))
    if not count_match:
        return False, False, False

    sorted_exp = sorted(expected_amounts)
    sorted_ext = sorted(extracted_amounts)
    amount_match = all(abs(e - a) <= tolerance for e, a in zip(sorted_exp, sorted_ext))

    # Match paired (amount, type)
    unmatched_ext = list(zip(extracted_amounts, extracted_types))
    type_match = True
    for exp_amt, exp_tp in zip(expected_amounts, expected_types):
        found_idx = None
        for idx, (ext_amt, ext_tp) in enumerate(unmatched_ext):
            if abs(exp_amt - ext_amt) <= tolerance and ext_tp == exp_tp:
                found_idx = idx
                break
        if found_idx is not None:
            unmatched_ext.pop(found_idx)
        else:
            type_match = False
            break

    return count_match, amount_match, type_match


async def run_evaluation(
    provider_name: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    limit: Optional[int] = None,
    case_id: Optional[str] = None,
    default_currency: str = "USD"
):
    print("=" * 80)
    print(f"CLANOMY LLM EXTRACTION EVALUATION HARNESS")
    print(f"Target Provider: {provider_name.upper()}")
    if model:
        print(f"Target Model:    {model}")
    print(f"Default Currency: {default_currency}")
    print("=" * 80)

    # 1. Initialize Provider
    if provider_name in ("gemini", "google"):
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("AI_API_KEY")
        if not api_key:
            print("❌ ERROR: Gemini API key required! Pass via --api-key or set GEMINI_API_KEY env var.")
            sys.exit(1)
        provider = GeminiProvider(model=model, api_key=api_key)
    elif provider_name == "ollama":
        provider = OllamaProvider(model=model)
    elif provider_name in ("groq", "openai"):
        if not api_key:
            api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings.AI_API_KEY
        provider = OpenAICompatibleProvider(model=model, api_key=api_key)
    else:
        print(f"❌ Unsupported provider: {provider_name}")
        sys.exit(1)

    extraction_service = ExtractionService(provider=provider)
    orchestrator = AIOrchestrator()

    # 2. Filter cases
    cases = DATASET
    if case_id:
        cases = [c for c in cases if c["id"] == case_id]
        if not cases:
            print(f"❌ Case ID '{case_id}' not found in dataset!")
            sys.exit(1)
    if limit:
        cases = cases[:limit]

    print(f"Evaluating {len(cases)} test case(s)...\n")

    passed = 0
    failed = 0
    count_passed = 0
    amount_passed = 0
    type_passed = 0
    latencies = []

    for i, case in enumerate(cases, 1):
        cid = case["id"]
        text = case["text"]
        exp_count = case["expected_count"]
        exp_amounts = case["expected_amounts"]
        exp_types = case.get("expected_types", [])
        desc = case.get("description", "")

        t0 = time.time()
        try:
            result = await orchestrator.simulate_message(
                text=text,
                default_currency=default_currency,
                dry_run=True,
                extraction_service=extraction_service
            )
            elapsed = time.time() - t0
            latencies.append(elapsed)

            items = result.get("items", [])
            ext_count = len(items)
            ext_amounts = [float(it.get("amount", 0.0)) for it in items if it.get("amount") is not None]
            ext_types = [it.get("type", "expense") for it in items]
            bot_reply = result.get("bot_response", "")

            # Strict Verification: count, amount, and type
            count_match, amount_match, type_match = match_items_with_types(
                expected_amounts=exp_amounts,
                expected_types=exp_types,
                extracted_amounts=ext_amounts,
                extracted_types=ext_types
            )

            if count_match:
                count_passed += 1
            if amount_match:
                amount_passed += 1
            if type_match:
                type_passed += 1

            success = count_match and amount_match and type_match
            if success:
                passed += 1
                status_badge = "[PASS]"
            else:
                failed += 1
                status_badge = "[FAIL]"

            preview = (text[:60] + "...") if len(text) > 60 else text
            print(f"[{i:02d}/{len(cases):02d}] {cid}: {status_badge} ({elapsed:.2f}s)")
            print(f"     Prompt: \"{preview}\"")
            print(f"     Expected: count={exp_count}, amounts={exp_amounts}, types={exp_types}")
            print(f"     Received: count={ext_count}, amounts={ext_amounts}, types={ext_types}")
            if not success:
                if not count_match:
                    print(f"     [!] Count mismatch: expected {exp_count}, got {ext_count}")
                if not amount_match:
                    print(f"     [!] Amount mismatch: expected {exp_amounts}, got {ext_amounts}")
                if not type_match:
                    print(f"     [!] Type mismatch: expected {exp_types}, got {ext_types}")
                print(f"     [!] Bot Reply:\n{bot_reply}")
            print("-" * 80)

        except Exception as e:
            elapsed = time.time() - t0
            failed += 1
            print(f"[{i:02d}/{len(cases):02d}] {cid}: [EXCEPTION] ({elapsed:.2f}s): {e}")
            print("-" * 80)

    # Summary Report
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    accuracy = (passed / len(cases)) * 100 if cases else 0.0
    type_acc = (type_passed / len(cases)) * 100 if cases else 0.0
    amount_acc = (amount_passed / len(cases)) * 100 if cases else 0.0

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY REPORT")
    print("=" * 80)
    print(f"Total Cases Evaluated: {len(cases)}")
    print(f"Count Accuracy:        {count_passed}/{len(cases)} ({(count_passed/len(cases))*100:.1f}%)")
    print(f"Amount Accuracy:       {amount_passed}/{len(cases)} ({amount_acc:.1f}%)")
    print(f"Type (Income/Expense): {type_passed}/{len(cases)} ({type_acc:.1f}%)")
    print(f"Overall Perfect:       {passed}/{len(cases)} ({accuracy:.1f}%)")
    print(f"Failed:                {failed}")
    print(f"Average Latency:       {avg_latency:.2f}s per query")
    print("=" * 80)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Evaluate Clanomy extraction on 55 real-world scenarios")
    parser.add_argument("--provider", choices=["ollama", "gemini", "groq", "openai"], default="ollama", help="LLM Provider to test")
    parser.add_argument("--model", help="Specific model name (e.g. gemini-3.1-flash-lite, gemini-3.6-flash, llama3:latest)")
    parser.add_argument("--api-key", help="API Key for Gemini, Groq, or OpenAI")
    parser.add_argument("--limit", type=int, help="Maximum number of test cases to evaluate")
    parser.add_argument("--case-id", help="Evaluate a single case ID (e.g. case_11)")
    parser.add_argument("--currency", default="USD", help="Default currency to simulate (USD, ARS, EUR)")
    args = parser.parse_args()

    asyncio.run(run_evaluation(
        provider_name=args.provider,
        api_key=args.api_key,
        model=args.model,
        limit=args.limit,
        case_id=args.case_id,
        default_currency=args.currency
    ))


if __name__ == "__main__":
    main()

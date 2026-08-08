"""LLM second-stage judge for top candidates.

Only evaluates the top ~20-40 candidates after deterministic scoring.
Blends LLM score with deterministic score (default 70/30).
Falls back to deterministic scoring if LLM fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from src.config import Config
from src.models import Classification, Domain, IntelligenceItem, LLMJudgment

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


def llm_evaluate(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Run LLM second-stage evaluation on top candidates.

    1. Select top K by deterministic score
    2. Send each to LLM for evaluation
    3. Blend LLM score with deterministic (configurable 70/30)
    4. Re-sort and re-classify

    If LLM is disabled or fails, returns items unchanged.
    """
    config = Config.get()

    if not config.llm_enabled:
        logger.info("[LLM] LLM evaluation disabled, using deterministic scores only")
        return items

    if not config.llm_api_key:
        logger.warning("[LLM] No API key configured, falling back to deterministic")
        return items

    blend_config = config.llm_blend
    top_k = int(blend_config.get("top_k_candidates", 30))
    det_weight = float(blend_config.get("deterministic_weight", 0.70))
    llm_weight = float(blend_config.get("llm_weight", 0.30))

    # Sort by deterministic score, take top K
    sorted_items = sorted(items, key=lambda x: x.deterministic_score, reverse=True)
    candidates = sorted_items[:top_k]
    rest = sorted_items[top_k:]

    logger.info(f"[LLM] Evaluating top {len(candidates)} candidates with {config.llm_provider}")

    evaluated = 0
    failed = 0

    for item in candidates:
        try:
            judgment = _call_llm(item, config)
            if judgment:
                item.llm_judgment = judgment
                item.llm_score = judgment.raw_score

                # Blend: 70% deterministic + 30% LLM
                item.final_score = (
                    det_weight * item.deterministic_score
                    + llm_weight * item.llm_score
                )
                item.final_score = max(0.0, min(10.0, item.final_score))

                # Apply LLM noise penalty
                item.final_score -= judgment.noise_penalty

                evaluated += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning(f"[LLM] Error evaluating '{item.title[:50]}': {e}")
            failed += 1

    logger.info(f"[LLM] Evaluated: {evaluated}, Failed: {failed}")

    # Recombine and re-classify
    all_items = candidates + rest
    return all_items


def _call_llm(item: IntelligenceItem, config: Config) -> LLMJudgment | None:
    """Call the configured LLM provider for evaluation."""
    provider = config.llm_provider.lower()

    if provider == "gemini":
        return _call_gemini(item, config)
    elif provider == "openai":
        return _call_openai(item, config)
    else:
        logger.warning(f"[LLM] Unknown provider: {provider}")
        return None


def _build_prompt(item: IntelligenceItem) -> str:
    """Build the evaluation prompt for the LLM."""
    domain_label = item.domain.value.replace("_", " ").title()

    return f"""You are an intelligence analyst evaluating whether a news/research item deserves attention in a daily briefing.

DOMAIN: {domain_label}
TITLE: {item.title}
SOURCE: {item.source}
SUMMARY: {item.summary or 'N/A'}
CATEGORIES: {', '.join(item.categories)}
DETERMINISTIC SCORE: {item.deterministic_score:.1f}/10

Evaluate this item. Be STRICT. Most items should score 5-7. Only genuinely significant items score 8+.

Ask yourself:
- Is this genuinely important or just routine?
- Does this represent a MATERIAL CHANGE or just incremental news?
- Would a busy executive need to know this?
- Is this mostly marketing/hype or substance?

Respond with ONLY valid JSON:
{{
  "importance": <0-10>,
  "novelty": <0-10>,
  "noise_penalty": <0-2, higher if clickbait/marketing/gossip>,
  "decision": "<must_read|worth_knowing|discard>",
  "reason": "<1 sentence>"
}}"""


def _call_gemini(item: IntelligenceItem, config: Config) -> LLMJudgment | None:
    """Call Google Gemini API."""
    prompt = _build_prompt(item)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.llm_model}:generateContent"
        resp = requests.post(
            url,
            params={"key": config.llm_api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 300,
                },
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.warning(f"[LLM] Gemini API returned {resp.status_code}")
            return None

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_llm_response(text)

    except Exception as e:
        logger.warning(f"[LLM] Gemini API error: {e}")
        return None


def _call_openai(item: IntelligenceItem, config: Config) -> LLMJudgment | None:
    """Call OpenAI API."""
    prompt = _build_prompt(item)

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code != 200:
            logger.warning(f"[LLM] OpenAI API returned {resp.status_code}")
            return None

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_llm_response(text)

    except Exception as e:
        logger.warning(f"[LLM] OpenAI API error: {e}")
        return None


def _parse_llm_response(text: str) -> LLMJudgment | None:
    """Parse the LLM's JSON response into an LLMJudgment."""
    try:
        # Extract JSON from response (may be wrapped in markdown code block)
        json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())

        importance = float(data.get("importance", 5.0))
        novelty = float(data.get("novelty", 5.0))
        noise_penalty = float(data.get("noise_penalty", 0.0))

        # Compute raw LLM score (0-10)
        raw_score = (importance * 0.6 + novelty * 0.4)

        return LLMJudgment(
            importance=importance,
            novelty=novelty,
            noise_penalty=min(2.0, max(0.0, noise_penalty)),
            decision=data.get("decision", "worth_knowing"),
            reason=data.get("reason", ""),
            raw_score=min(10.0, max(0.0, raw_score)),
        )

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"[LLM] Failed to parse response: {e}")
        return None

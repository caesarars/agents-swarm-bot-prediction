"""Async multi-provider LLM client for the prediction swarm.

The module name is kept for compatibility with the rest of the app, but calls
are routed per-agent to DeepSeek, Anthropic Claude, or Gemini.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from ..agents import Agent
from ..config import get_settings

log = logging.getLogger(__name__)


@dataclass
class AgentResult:
    agent_id: int
    agent_name: str
    agent_category: str
    provider: str
    vote: str  # UP / DOWN / ABSTAIN
    confidence: float
    reasoning: str
    error: str | None = None


def _safe_parse(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None


def _normalize(parsed: dict | None) -> tuple[str, float, str]:
    if not parsed:
        return "ABSTAIN", 0.0, "unparseable response"
    pred = str(parsed.get("prediction", "")).upper().strip()
    if pred not in ("UP", "DOWN"):
        return "ABSTAIN", 0.0, str(parsed.get("reasoning") or "no clear direction")
    conf = parsed.get("confidence", 0)
    try:
        conf_f = float(conf)
    except Exception:
        conf_f = 0.0
    conf_f = max(0.0, min(100.0, conf_f))
    reason = str(parsed.get("reasoning", ""))[:400]
    return pred, conf_f, reason


def _user_prompt(snapshot_str: str) -> str:
    return (
        "Market snapshot (JSON):\n"
        f"{snapshot_str}\n\n"
        "Return exactly one valid JSON object and nothing else. "
        "The first character must be { and the last character must be }. "
        'Use this shape: {"prediction":"UP","confidence":51,"reasoning":"short reason"}. '
        "prediction must be either UP or DOWN; confidence must be a number from 0 to 100."
    )


def _missing_key(agent: Agent, key_name: str) -> AgentResult:
    return AgentResult(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_category=agent.category,
        provider=agent.provider,
        vote="ABSTAIN",
        confidence=0.0,
        reasoning="",
        error=f"{key_name} is not configured",
    )


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.6, max=4),
        reraise=True,
    ):
        with attempt:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504):
                body = r.text[:500]
                raise httpx.HTTPStatusError(
                    f"retryable {r.status_code}: {body}", request=r.request, response=r
                )
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = r.text[:500]
                raise httpx.HTTPStatusError(
                    f"{e}: {body}", request=r.request, response=r
                ) from e
            return r.json()
    raise RuntimeError("unreachable retry state")


async def _call_deepseek(client: httpx.AsyncClient, agent: Agent, snapshot_str: str) -> str | AgentResult:
    settings = get_settings()
    if not settings.deepseek_api_key:
        return _missing_key(agent, "DEEPSEEK_API_KEY")

    data = await _post_with_retry(
        client,
        f"{settings.deepseek_base_url}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        payload={
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": _user_prompt(snapshot_str)},
            ],
            "temperature": 0.35,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
            "stream": False,
        },
    )
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def _call_anthropic(client: httpx.AsyncClient, agent: Agent, snapshot_str: str) -> str | AgentResult:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _missing_key(agent, "ANTHROPIC_API_KEY")

    data = await _post_with_retry(
        client,
        f"{settings.anthropic_base_url}/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": settings.anthropic_version,
            "Content-Type": "application/json",
        },
        payload={
            "model": settings.anthropic_model,
            "system": agent.system_prompt,
            "messages": [{"role": "user", "content": _user_prompt(snapshot_str)}],
            "temperature": 0.35,
            "max_tokens": 200,
        },
    )
    blocks = data.get("content") or []
    return "".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict))


async def _call_gemini(client: httpx.AsyncClient, agent: Agent, snapshot_str: str) -> str | AgentResult:
    settings = get_settings()
    if not settings.gemini_api_key:
        return _missing_key(agent, "GEMINI_API_KEY")

    data = await _post_with_retry(
        client,
        f"{settings.gemini_base_url}/v1beta/models/{settings.gemini_model}:generateContent",
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        payload={
            "systemInstruction": {"parts": [{"text": agent.system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": _user_prompt(snapshot_str)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 512,
                "thinkingConfig": {"thinkingBudget": 0},
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "prediction": {"type": "STRING", "enum": ["UP", "DOWN"]},
                        "confidence": {"type": "NUMBER"},
                        "reasoning": {"type": "STRING"},
                    },
                    "required": ["prediction", "confidence", "reasoning"],
                },
            },
        },
    )
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    return "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


async def _call_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    agent: Agent,
    snapshot_str: str,
) -> AgentResult:
    async with semaphore:
        try:
            if agent.provider == "deepseek":
                content = await _call_deepseek(client, agent, snapshot_str)
            elif agent.provider == "anthropic":
                content = await _call_anthropic(client, agent, snapshot_str)
            elif agent.provider == "gemini":
                content = await _call_gemini(client, agent, snapshot_str)
            else:
                content = AgentResult(
                    agent.id,
                    agent.name,
                    agent.category,
                    agent.provider,
                    "ABSTAIN",
                    0.0,
                    "",
                    f"unsupported provider {agent.provider}",
                )

            if isinstance(content, AgentResult):
                return content

            parsed = _safe_parse(content)
            vote, conf, reason = _normalize(parsed)
            return AgentResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_category=agent.category,
                provider=agent.provider,
                vote=vote,
                confidence=conf,
                reasoning=reason,
            )
        except (httpx.HTTPError, RetryError, asyncio.TimeoutError) as e:
            log.warning("agent %s (%s) failed: %s", agent.id, agent.provider, e)
            return AgentResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_category=agent.category,
                provider=agent.provider,
                vote="ABSTAIN",
                confidence=0.0,
                reasoning="",
                error=str(e)[:300],
            )
        except Exception as e:
            log.exception("agent %s (%s) crashed", agent.id, agent.provider)
            return AgentResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_category=agent.category,
                provider=agent.provider,
                vote="ABSTAIN",
                confidence=0.0,
                reasoning="",
                error=str(e)[:300],
            )


async def run_swarm(agents: list[Agent], snapshot: dict) -> list[AgentResult]:
    settings = get_settings()
    snapshot_str = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
    timeout = httpx.Timeout(settings.agent_timeout_seconds, connect=10.0)
    limits = httpx.Limits(
        max_connections=settings.agent_concurrency * 2,
        max_keepalive_connections=settings.agent_concurrency,
    )
    semaphore = asyncio.Semaphore(settings.agent_concurrency)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = [_call_one(client, semaphore, agent, snapshot_str) for agent in agents]
        return await asyncio.gather(*tasks)

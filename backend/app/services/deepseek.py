"""Async DeepSeek client with concurrency control and JSON-mode responses."""

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
    vote: str  # UP / DOWN / ABSTAIN
    confidence: float
    reasoning: str
    error: str | None = None


def _safe_parse(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    # Strip ```json fences if present
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # try to find first { ... } block
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


async def _call_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    agent: Agent,
    snapshot_str: str,
) -> AgentResult:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": agent.system_prompt},
            {
                "role": "user",
                "content": (
                    "Market snapshot (JSON):\n"
                    f"{snapshot_str}\n\n"
                    "Respond with strict JSON: "
                    '{"prediction":"UP"|"DOWN","confidence":0-100,"reasoning":"..."}'
                ),
            },
        ],
        "temperature": 0.7,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
        "stream": False,
    }

    async with semaphore:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.6, max=4),
                reraise=True,
            ):
                with attempt:
                    r = await client.post(
                        f"{settings.deepseek_base_url}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if r.status_code in (429, 500, 502, 503, 504):
                        raise httpx.HTTPStatusError(
                            f"retryable {r.status_code}", request=r.request, response=r
                        )
                    r.raise_for_status()
                    data = r.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    parsed = _safe_parse(content)
                    vote, conf, reason = _normalize(parsed)
                    return AgentResult(
                        agent_id=agent.id,
                        agent_name=agent.name,
                        agent_category=agent.category,
                        vote=vote,
                        confidence=conf,
                        reasoning=reason,
                    )
        except (httpx.HTTPError, RetryError, asyncio.TimeoutError) as e:
            log.warning("agent %s failed: %s", agent.id, e)
            return AgentResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_category=agent.category,
                vote="ABSTAIN",
                confidence=0.0,
                reasoning="",
                error=str(e)[:300],
            )
        except Exception as e:
            log.exception("agent %s crashed", agent.id)
            return AgentResult(
                agent_id=agent.id,
                agent_name=agent.name,
                agent_category=agent.category,
                vote="ABSTAIN",
                confidence=0.0,
                reasoning="",
                error=str(e)[:300],
            )

    # Should not reach here
    return AgentResult(agent.id, agent.name, agent.category, "ABSTAIN", 0.0, "", "no result")


async def run_swarm(agents: list[Agent], snapshot: dict) -> list[AgentResult]:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    snapshot_str = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False)
    timeout = httpx.Timeout(settings.agent_timeout_seconds, connect=10.0)
    limits = httpx.Limits(max_connections=settings.agent_concurrency * 2, max_keepalive_connections=settings.agent_concurrency)
    semaphore = asyncio.Semaphore(settings.agent_concurrency)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = [_call_one(client, semaphore, agent, snapshot_str) for agent in agents]
        return await asyncio.gather(*tasks)

"""Orchestrator Agent
Receives the user's message and decides which specialist agent answers it
(RAG agent for policies, Sales agent for buying/products).

Uses only what the repo already has (models.py -> Groq + NVIDIA free models),
so it costs nothing extra.

Main function:  orchestrator_agent(question, thread_id=None) -> str
(same shape as rag_agent(question, thread_id) in RAG_Agent.py)
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from langchain.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import groq_model, nvidia_model

log = logging.getLogger("orchestrator")

DEFAULT_AGENT = "rag"   # used when the router cannot decide
MIN_CONFIDENCE = 0.5    # below this, the LLM decision is ignored


## 1. Agent registry: to add a new agent, add ONE function with @register_agent ##

@dataclass
class AgentSpec:
    name: str
    description: str                       # the LLM router reads this to decide
    handler: Callable[[str, str], str]     # (question, thread_id) -> answer
    keywords: tuple[str, ...] = ()         # free fast-path, no LLM call needed


AGENTS: dict[str, AgentSpec] = {}


def register_agent(name: str, description: str, keywords: tuple[str, ...] = ()):
    def decorator(fn):
        AGENTS[name] = AgentSpec(name, description, fn, tuple(k.lower() for k in keywords))
        return fn
    return decorator


# Imports are lazy so the orchestrator can start (and be tested) even if an
# agent file is missing, and so RAG_Agent's PDF/Mongo setup runs only when needed.

@register_agent(
    "rag",
    "Store policies and documents: returns, refunds, shipping, warranty, privacy, "
    "terms, employee/HR policies, employee login (name and passcode).",
    keywords=("policy", "policies", "refund", "return", "shipping policy", "warranty",
              "privacy", "terms", "employee", "hr", "leave", "passcode"),
)
def _call_rag(question: str, thread_id: str) -> str:
    from RAG_Agent import rag_agent
    return rag_agent(question, thread_id)


@register_agent(
    "sales",
    "Buying intent: product search, prices, availability, recommendations, "
    "comparing products, discounts, placing or tracking an order.",
    keywords=("buy", "purchase", "price", "cost", "recommend", "product", "discount",
              "cheaper", "cart", "order", "in stock", "compare"),
)
def _call_sales(question: str, thread_id: str) -> str:
    from Sales_Agent import sales_agent   # <-- change to your teammate's file/function name
    return sales_agent(question, thread_id)


## 2. Shared context + hooks (the place for your 5 future features) ##

@dataclass
class Context:
    question: str
    thread_id: str
    agent: str = ""
    confidence: float = 0.0
    reason: str = ""
    extras: dict = field(default_factory=dict)   # hooks can store anything here


# PRE hook : (ctx) -> str | None   -> return a string to answer immediately and skip the agents
# POST hook: (ctx, reply) -> str   -> return the (possibly changed) reply
PRE_HOOKS: list[Callable[[Context], str | None]] = []
POST_HOOKS: list[Callable[[Context, str], str]] = []


def _log_decision(ctx: Context, reply: str) -> str:
    log.info("thread=%s agent=%s conf=%.2f reason=%s", ctx.thread_id, ctx.agent, ctx.confidence, ctx.reason)
    return reply


POST_HOOKS.append(_log_decision)


## 3. Router: keywords (free) -> sticky follow-up -> LLM classifier -> default ##

class RouteDecision(BaseModel):
    agent: str = Field(description="Name of the agent that should handle the message.")
    confidence: float = Field(ge=0, le=1, description="How sure you are, from 0 to 1.")
    reason: str = Field(description="One short sentence explaining the choice.")


_router = groq_model.with_structured_output(RouteDecision).with_fallbacks(
    [nvidia_model.with_structured_output(RouteDecision)]
)

_last_agent: dict[str, str] = {}   # thread_id -> agent used last turn (for follow-ups)


def _router_prompt(last_agent: str | None) -> str:
    agents = "\n".join(f"- {a.name}: {a.description}" for a in AGENTS.values())
    prompt = (
        "You are a router for a customer-service system. Pick exactly one agent for the "
        f"user's message.\nAvailable agents:\n{agents}\n"
        "Answer with the agent name only from that list."
    )
    if last_agent:
        prompt += (
            f"\nThe previous message in this conversation was handled by '{last_agent}'. "
            "If the new message is a follow-up, a short reply, or looks like an answer to a "
            "question that agent asked (for example a name and passcode), keep the same agent."
        )
    return prompt


def _keyword_route(question: str) -> str | None:
    """Return an agent only if exactly one agent's keywords match (no ambiguity)."""
    q = question.lower()
    hits = [
        a.name for a in AGENTS.values()
        if any(re.search(rf"\b{re.escape(k)}", q) for k in a.keywords)
    ]
    return hits[0] if len(hits) == 1 else None


def route(ctx: Context) -> tuple[str, float, str]:
    last = _last_agent.get(ctx.thread_id)

    hit = _keyword_route(ctx.question)
    if hit:
        return hit, 1.0, "keyword match"

    # Short messages like "yes" or "Mohamed Fathy 123456" belong to the ongoing conversation.
    if last and len(ctx.question.split()) <= 4:
        return last, 0.9, "short follow-up"

    try:
        decision = _router.invoke(
            [SystemMessage(_router_prompt(last)), HumanMessage(ctx.question)]
        )
        if decision and decision.agent in AGENTS and decision.confidence >= MIN_CONFIDENCE:
            return decision.agent, decision.confidence, decision.reason
    except Exception:
        log.exception("LLM router failed, using fallback")

    return last or DEFAULT_AGENT, 0.0, "fallback"


## 4. Take the agent's response and prepare the final answer for the user ##

FALLBACK_REPLY = "Sorry, I could not get an answer right now. Please try again."


def _to_text(raw) -> str:
    """Agents may return a string, or a list of content blocks (LangChain). Make it plain text."""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = [b if isinstance(b, str) else b.get("text", "") for b in raw if b]
        return "\n".join(p for p in parts if p).strip()
    return str(raw or "").strip()


def _call_agent(ctx: Context) -> str:
    """Send the question to the chosen agent and collect its response."""
    try:
        raw = AGENTS[ctx.agent].handler(ctx.question, ctx.thread_id)
    except ImportError as e:
        log.error("Agent '%s' is not available: %s", ctx.agent, e)
        return "Sorry, that part of the assistant is not available right now."
    except Exception:
        log.exception("Agent '%s' failed", ctx.agent)
        return FALLBACK_REPLY
    ctx.extras["raw_reply"] = raw
    return _to_text(raw) or FALLBACK_REPLY


## 5. MAIN FUNCTION ##

def orchestrator_agent(question: str, thread_id: str | None = None, with_details: bool = False):
    """Take the user's message -> choose the agent -> get its response -> return it to the user.
    Pass the same thread_id on every turn of a conversation so the agents keep their memory.
    with_details=True returns {"answer", "agent", "confidence", "reason"} instead of a string."""
    ctx = Context(question=(question or "").strip(), thread_id=thread_id or str(uuid4()))
    if not ctx.question:
        return "Please type your question."

    for hook in PRE_HOOKS:
        early_reply = hook(ctx)
        if early_reply is not None:
            return early_reply

    ctx.agent, ctx.confidence, ctx.reason = route(ctx)      # 1. decide
    _last_agent[ctx.thread_id] = ctx.agent
    reply = _call_agent(ctx)                                 # 2. agent works, orchestrator receives the response

    for hook in POST_HOOKS:                                  # 3. orchestrator can check/change it
        reply = hook(ctx, reply)

    if with_details:                                         # 4. give it back to the user
        return {"answer": reply, "agent": ctx.agent, "confidence": ctx.confidence, "reason": ctx.reason}
    return reply


if __name__ == "__main__":   # quick terminal test: python orchestrator.py
    logging.basicConfig(level=logging.INFO)
    tid = str(uuid4())
    while (msg := input("You: ").strip()).lower() not in {"exit", "quit"}:
        print("Bot:", orchestrator_agent(msg, tid))

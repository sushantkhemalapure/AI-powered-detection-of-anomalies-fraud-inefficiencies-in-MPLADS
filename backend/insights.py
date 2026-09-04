"""
Decision-support briefings for MPLADS Sentinel.

If XAI_API_KEY is set, a SpaceXAI (xAI) Grok model turns the latest
KPIs + top alerts into a Ministry-style situation report or answers a
free-text question. If the key is missing, a deterministic template is
used so the demo still runs fully offline.
"""

import os
from datetime import datetime

DEFAULT_MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
XAI_BASE_URL = "https://api.x.ai/v1"


def _client():
    key = os.environ.get("XAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    return OpenAI(api_key=key, base_url=XAI_BASE_URL)


def build_context_pack(summary, ranking, rule_freq, early_warning, compliance, top_alerts):
    """Compact structured snapshot the LLM (or the template) can reason over."""
    totals = summary.get("totals") or {}
    risk = {r["risk_band"]: r["count"] for r in summary.get("risk_breakdown") or []}
    top_states = (ranking or [])[:5]
    top_rules = (rule_freq or [])[:8]
    warnings = (early_warning or [])[:8]
    alerts = (top_alerts or [])[:8]
    comp = compliance.get("summary") if compliance else {}

    lines = [
        f"As-of: {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        f"Works: {totals.get('total_works', 0)} | Completed: {totals.get('completed_works', 0)} | "
        f"In progress: {totals.get('inprogress_works', 0)} | Delayed: {totals.get('delayed_works', 0)}",
        f"Sanctioned (lakh): {round(totals.get('total_sanctioned_lakh') or 0, 1)} | "
        f"Expenditure (lakh): {round(totals.get('total_expenditure_lakh') or 0, 1)}",
        f"Risk bands — Critical: {risk.get('Critical', 0)}, High: {risk.get('High', 0)}, "
        f"Medium: {risk.get('Medium', 0)}, Low: {risk.get('Low', 0)}",
        f"Open alerts: {summary.get('open_alerts', 0)}",
        "Compliance — "
        f"1-year overdue: {comp.get('one_year_overdue', 0)}, "
        f"Missing UC: {comp.get('missing_uc', 0)}, "
        f"Pending sanction >90d: {comp.get('pending_sanction', 0)}, "
        f"Spend > sanction: {comp.get('expenditure_over_sanction', 0)}, "
        f"Stale progress: {comp.get('stale_progress', 0)}",
        "Highest-risk states: " + ", ".join(
            f"{s['state_name']} (avg {s.get('avg_risk_score')}, high-risk {s.get('high_risk_works')})"
            for s in top_states
        ),
        "Most frequent detection rules: " + ", ".join(
            f"{r['rule']}={r['count']}" for r in top_rules
        ),
        "Early-warning (open works most likely to delay/overrun):",
    ]
    for w in warnings:
        lines.append(
            f"  - #{w['work_id']} {w.get('description','')[:80]} | "
            f"delay {round((w.get('delay_probability') or 0)*100)}% "
            f"overrun {round((w.get('overrun_probability') or 0)*100)}% | "
            f"{w.get('state_name')} / {w.get('mp_name')}"
        )
    lines.append("Top open alerts:")
    for a in alerts:
        lines.append(
            f"  - [{a.get('severity')}] {a.get('category')}: {a.get('message','')[:160]} "
            f"({a.get('state_name')})"
        )
    return "\n".join(lines)


def template_briefing(context: str, role: str = "ministry") -> str:
    audience = {
        "ministry": "the Ministry of Statistics and Programme Implementation",
        "state": "the State Nodal Authority",
        "district": "the District Authority",
        "mp": "the Hon'ble Member of Parliament",
    }.get(role, "concerned authorities")

    return (
        f"MPLADS Sentinel — Situation Report for {audience}\n\n"
        f"{context}\n\n"
        "Recommended focus for the next review cycle:\n"
        "1. Inspect High/Critical works flagged for ghost assets or duplicate descriptions "
        "before any further installment is released.\n"
        "2. Direct District Authorities to close Utilization Certificate gaps on completed works "
        "within 15 days (MPLADS closing requirement).\n"
        "3. Call a review of works open more than one year after sanction — the Scheme guideline "
        "is completion within 12 months.\n"
        "4. Treat early-warning works (high delay/overrun probability, not yet High-risk) as "
        "the preventive queue: request catch-up plans now rather than after they stall.\n"
        "5. Where a single vendor accounts for a disproportionate share of an MP's expenditure, "
        "review tender history and related-party indicators.\n\n"
        "This briefing is generated from the live risk engine (explainable rules + Isolation Forest) "
        "and the early-warning models. It is a decision-support product, not a finding of fraud."
    )


def llm_complete(system: str, user: str) -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        return f"(SpaceXAI call failed: {exc})"


SYSTEM_BRIEFING = (
    "You are MPLADS Sentinel, an official decision-support analyst for India's "
    "Members of Parliament Local Area Development Scheme (MPLADS), serving MoSPI. "
    "Write a concise situation report (300-450 words) for the audience named by the user. "
    "Use only the facts in the context pack. Structure: (1) headline snapshot, "
    "(2) top 4-6 risks with numbers, (3) recommended actions tagged by owner "
    "(Ministry / SNA / District / MP), (4) a one-line caveat that alerts are "
    "risk scores not proven fraud. Plain official English, no markdown tables, "
    "no speculation beyond the data."
)

SYSTEM_ASK = (
    "You are MPLADS Sentinel, an official analyst for the MPLADS scheme. "
    "Answer the user's question using ONLY the supplied context pack. "
    "If the context does not contain the answer, say so and point to the "
    "dashboard page that would. Be specific with numbers. "
    "Never invent works, MPs, or amounts. Alerts are risk flags, not convictions."
)


def generate_briefing(context: str, role: str = "ministry") -> dict:
    templated = template_briefing(context, role)
    llm = llm_complete(
        SYSTEM_BRIEFING,
        f"Audience role: {role}\n\nContext pack:\n{context}",
    )
    if llm and not llm.startswith("(SpaceXAI call failed"):
        return {"source": "spacexai", "model": DEFAULT_MODEL, "text": llm}
    if llm and llm.startswith("(SpaceXAI call failed"):
        return {"source": "template", "model": None, "text": templated, "note": llm}
    return {"source": "template", "model": None, "text": templated}


def answer_question(question: str, context: str) -> dict:
    llm = llm_complete(
        SYSTEM_ASK,
        f"Question: {question}\n\nContext pack:\n{context}",
    )
    if llm and not llm.startswith("(SpaceXAI call failed"):
        return {"source": "spacexai", "model": DEFAULT_MODEL, "answer": llm}
    # Offline extractive fallback: return the context plus a short steer.
    q = (question or "").lower()
    hint = "See the snapshot below for the latest numbers in scope."
    if "ghost" in q:
        hint = "Ghost-asset flags are works with high fund drawdown and very low physical progress. They appear under AI Anomaly Explorer → Ghost Asset."
    elif "delay" in q or "overdue" in q or "stalled" in q:
        hint = "Stalled and one-year-overdue works are listed on Early Warning and Compliance Monitor."
    elif "uc" in q or "utilization" in q:
        hint = "Completed works without a Utilization Certificate are a compliance breach — see Compliance Monitor."
    elif "vendor" in q:
        hint = "Vendor concentration is detected when one contractor takes a disproportionate share of an MP's MPLADS spend."
    elif "duplicate" in q:
        hint = "Duplicate-work flags are near-identical descriptions in the same district and category."
    elif "state" in q or "ranking" in q:
        hint = "State Rankings orders states by average risk score and High/Critical work counts."
    return {
        "source": "template",
        "model": None,
        "answer": f"{hint}\n\nCurrent snapshot:\n{context}",
        "note": llm if llm else "Set XAI_API_KEY to enable SpaceXAI narrative answers.",
    }

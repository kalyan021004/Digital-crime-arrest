"""
PHASE 5: MCP Server
---------------------
Why MCP here: the LangGraph pipeline in agents/graph.py is "our" app's internal
logic. MCP is what lets that same intelligence be called by OTHER systems --
a WhatsApp bot, a bank's fraud-check app, a telecom's call-screening system,
or even a different agent -- as a standardized tool, instead of everyone
re-implementing scam detection themselves.

We expose 3 tools:
  1. check_transcript_chunk  - run one chunk through the RAG + risk pipeline,
                                return a score and matched patterns (stateless,
                                single-chunk version of the graph for simple callers)
  2. analyze_call_session     - run a full multi-chunk session through the
                                LangGraph pipeline (stateful, the "real" pipeline)
  3. generate_citizen_alert   - given a decision + risk categories, produce a
                                plain-language warning message a client app can display

Run this with:  python3 mcp_server/server.py
Then any MCP-compatible client (Claude Desktop, another agent, etc.) can connect
and call these tools by name.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from rag.knowledge_base import ScamPatternKB
from agents.graph import process_call_session
from agents.nodes import SUSPICIOUS_KEYWORDS

mcp = FastMCP("digital-arrest-shield")
_kb = ScamPatternKB()


@mcp.tool()
def check_transcript_chunk(text: str) -> dict:
    """
    Check a single piece of call/chat transcript against known digital-arrest
    scam patterns. Returns a suspicion score and the closest matched patterns.
    Use this for a quick, stateless check of one message (e.g. a single WhatsApp
    message forwarded by a user).
    """
    text_lower = text.lower()
    keyword_score = min(
        sum(w for kw, w in SUSPICIOUS_KEYWORDS.items() if kw in text_lower), 1.0
    )
    matches = _kb.retrieve(text, top_k=3)
    strong_matches = [m for m in matches if m["distance"] < 1.8]

    return {
        "keyword_suspicion_score": round(keyword_score, 2),
        "matched_patterns": strong_matches,
        "recommendation": (
            "High risk -- treat as likely scam" if keyword_score > 0.4 or strong_matches
            else "Low risk based on this message alone -- monitor for more context"
        ),
    }


@mcp.tool()
def analyze_call_session(session_id: str, transcript_chunks: list[str]) -> dict:
    """
    Run a full call transcript (as a list of chunks in chronological order)
    through the complete LangGraph compound-risk-detection pipeline.
    Returns the final suspicion score, decision (monitor/warn/alert),
    detected risk categories, and a citizen-facing alert message if warranted.
    This is the primary tool for integrating with a live call-monitoring system.
    """
    final_state = process_call_session(session_id, transcript_chunks)
    return {
        "session_id": session_id,
        "suspicion_score": round(final_state.get("suspicion_score", 0.0), 2),
        "decision": final_state.get("decision"),
        "risk_categories_seen": final_state.get("risk_categories_seen", []),
        "alert_message": final_state.get("alert_message", ""),
        "incident_report": final_state.get("incident_report", {}),
    }


@mcp.tool()
def generate_citizen_alert(risk_categories: list[str], confidence: float) -> str:
    """
    Generate a plain-language, citizen-facing warning message given a set of
    detected risk categories and a confidence score. Useful for client apps
    (WhatsApp bot, IVR, mobile app) that already have their own scoring but
    want a standardized, well-worded alert message.
    """
    if confidence < 0.45:
        return "No strong scam indicators detected yet. Stay cautious if the caller pressures you for money or secrecy."
    return (
        f"⚠️ Warning: this interaction matches known 'digital arrest' scam patterns "
        f"(confidence: {confidence:.0%}). Detected: {', '.join(risk_categories)}. "
        "Government agencies never arrest people over video call or demand money "
        "transfers to 'verification accounts'. Do not transfer any money. "
        "Hang up and report to the National Cybercrime Helpline: 1930 or cybercrime.gov.in."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")

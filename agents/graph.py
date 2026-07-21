"""
PHASE 4c: Graph Assembly
-------------------------
This is where LangGraph itself is used: we register nodes, wire edges between
them, and compile a runnable graph.

Now updated to support multi-language citizen alerts.
"""

from langgraph.graph import StateGraph, END
from agents.state import ScamDetectionState
from agents.nodes import (
    suspicion_filter,
    rag_retrieval,
    compound_risk_correlator,
    decision_node,
    action_node,
)


def route_after_decision(state: ScamDetectionState) -> str:
    """Conditional edge function."""
    if state.get("decision") in ("warn", "alert"):
        return "action_node"
    return "end"


def build_graph():
    graph = StateGraph(ScamDetectionState)

    graph.add_node("suspicion_filter", suspicion_filter)
    graph.add_node("rag_retrieval", rag_retrieval)
    graph.add_node("compound_risk_correlator", compound_risk_correlator)
    graph.add_node("decision_node", decision_node)
    graph.add_node("action_node", action_node)

    graph.set_entry_point("suspicion_filter")

    graph.add_edge("suspicion_filter", "rag_retrieval")
    graph.add_edge("rag_retrieval", "compound_risk_correlator")
    graph.add_edge("compound_risk_correlator", "decision_node")

    graph.add_conditional_edges(
        "decision_node",
        route_after_decision,
        {
            "action_node": "action_node",
            "end": END,
        },
    )

    graph.add_edge("action_node", END)

    return graph.compile()


def process_call_session(
    session_id: str,
    chunks: list,
    city: str = None,
    latitude: float = None,
    longitude: float = None,
    language: str = "en",
) -> ScamDetectionState:
    """
    Simulates a streaming phone call.

    Parameters
    ----------
    session_id : str
    chunks : list
        Transcript chunks.
    city, latitude, longitude : optional
        Caller location, used only for geospatial hotspot aggregation.
        These default to None because location is genuinely optional -- a
        WhatsApp message check or an IVR call may have no location attached,
        and scam detection must not depend on it.

        (Previously these were REQUIRED positional arguments, which meant every
        caller in the project -- main.py, server/api.py and mcp_server/server.py
        -- raised TypeError on invocation. Nothing could run.)
    language : str
        User's preferred language.
        Supported:
            en
            hi
            ta
            kn
    """

    app = build_graph()

    state: ScamDetectionState = {
        "session_id": session_id,
        "transcript_chunks": [],
        "risk_categories_seen": [],
        "matched_pattern_evidence": [],
        "suspicion_score": 0.0,
        "decision": "monitor",
        "city": city,
        "latitude": latitude,
        "longitude": longitude,
        "language": language,
    }

    for chunk in chunks:

        state["current_chunk"] = chunk
        state["transcript_chunks"] = (
            state["transcript_chunks"] + [chunk]
        )

        result = app.invoke(state)

        state.update(result)

        print(
            f"[{session_id}] "
            f"score={state['suspicion_score']:.2f} "
            f"decision={state['decision']}"
        )

        if state["decision"] == "alert":

            print("\n==============================")
            print("🚨 ALERT GENERATED")
            print("==============================")

            print(f"Language : {state['language']}")
            print(state["alert_message"])

            print()

            break

    return state


if __name__ == "__main__":

    import json
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "sample_transcripts.json",
    )

    with open(path, encoding="utf-8") as f:
        calls = json.load(f)

    for test_call in calls:

      print("\n" + "=" * 60)
      print(f"Processing {test_call['session_id']}")
      print("=" * 60)

      process_call_session(
        session_id=test_call["session_id"],
        chunks=test_call["chunks"],
        city=test_call["city"],
        latitude=test_call["latitude"],
        longitude=test_call["longitude"],
        language="en",
      )

    
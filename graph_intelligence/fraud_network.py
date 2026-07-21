"""
PHASE 8: Fraud Network Graph Intelligence
--------------------------------------------
Gap addressed: "Fraud network detection ... clustering victim reports, scammer
infrastructure ... into actionable intelligence packages."

The idea: one flagged call is an incident. But if 20 different victims all got
calls using the SAME script pattern (same matched pattern IDs, same phrasing),
that's not 20 isolated incidents -- it's evidence of ONE organised fraud
campaign. A single call's alert can't show you that; you need to look across
many incident reports together. That's a graph problem, not a single-session
classification problem, which is why this lives separately from the LangGraph
per-call pipeline.

How it works:
  - Every ALERT-level incident_report (from agents/nodes.py action_node) gets
    added as a node in a graph.
  - Two incident nodes get an edge if they share matched scam pattern IDs
    (the same script fragments were used against both victims).
  - Edge weight = number of shared pattern IDs (stronger shared fingerprint
    = more likely the same operator/script).
  - Connected components with >= 2 incidents are flagged as a "suspected
    campaign" -- the same fraud ring hitting multiple victims.

This is intentionally a simple, explainable graph method (not a black box)
so it produces auditable evidence packages, matching the problem statement's
"auditability of intelligence packages for legal admissibility" requirement.
"""

import networkx as nx
from collections import defaultdict
from typing import List, Dict, Any
import json
from db.mongo import incident_collection



class FraudNetworkGraph:
    def __init__(self):
        self.graph = nx.Graph()
        self.collection = incident_collection



    def build_graph(self):

      self.graph.clear()

      incidents = list(self.collection.find())

      for incident in incidents:
        self.add_incident(incident)



    def add_incident(self, incident_report: Dict[str, Any]):
        """
        Add one ALERT-level incident report as a node, and link it to any
        existing incidents that share matched scam pattern IDs.
        """
        session_id = incident_report["session_id"]
        pattern_ids = set(incident_report.get("matched_pattern_ids", []))

        self.graph.add_node(
            session_id,
            confidence=incident_report.get("confidence", 0.0),
            risk_categories=incident_report.get("risk_categories", []),
            pattern_ids=list(pattern_ids),
        )

        # Compare against every existing node to find shared pattern fingerprints
        for other_id, other_data in self.graph.nodes(data=True):
            if other_id == session_id:
                continue
            other_patterns = set(other_data.get("pattern_ids", []))
            shared = pattern_ids & other_patterns
            if shared:
                self.graph.add_edge(session_id, other_id, shared_patterns=list(shared), weight=len(shared))

    def detect_campaigns(self, min_incidents: int = 2) -> List[Dict[str, Any]]:
        """
        Find connected clusters of incidents (= suspected coordinated campaigns).
        Returns a ranked list of campaign summaries, largest/strongest first.
        """
        campaigns = []
        for component in nx.connected_components(self.graph):
            if len(component) < min_incidents:
                continue  # isolated single incident, not a "campaign" yet

            subgraph = self.graph.subgraph(component)
            shared_pattern_counts = defaultdict(int)
            for _, _, data in subgraph.edges(data=True):
                for p in data.get("shared_patterns", []):
                    shared_pattern_counts[p] += 1

            avg_confidence = sum(
                self.graph.nodes[n]["confidence"] for n in component
            ) / len(component)

            campaigns.append({
                "affected_sessions": sorted(component),
                "victim_count": len(component),
                "common_pattern_ids": sorted(shared_pattern_counts.keys()),
                "avg_confidence": round(avg_confidence, 2),
                "campaign_strength": subgraph.number_of_edges(),  # more shared links = tighter cluster
            })

        campaigns.sort(key=lambda c: (c["victim_count"], c["campaign_strength"]), reverse=True)
        return campaigns



    def summary(self):

      self.build_graph()

      campaigns = self.detect_campaigns()

      return {
        "total_incidents_tracked": self.graph.number_of_nodes(),
        "suspected_campaigns": len(campaigns),
        "campaigns": campaigns,
    }

if __name__ == "__main__":
    # Demo: simulate 4 victims, 3 hit by the same fraud ring (shared SP002+SP003 pattern),
    # 1 hit by an unrelated one-off scam.

    fng = FraudNetworkGraph()

    incidents = incident_collection.find()

    for incident in incidents:
       fng.add_incident(incident)

    print(json.dumps(fng.summary(), indent=2))

# Digital Arrest Scam Shield

AI system that detects "digital arrest" scam calls **while they are happening**,
using RAG (pattern retrieval) + LangGraph (multi-agent reasoning pipeline) +
MCP (tool exposure for other apps to call).

Run the full demo:
```bash
pip install -r requirements.txt
python3 main.py
```

Run the MCP server standalone:
```bash
python3 mcp_server/server.py
```

---

## Phase-wise breakdown (revise in this order)

### Phase 1 — Problem & Data (`data/`)
- `scam_patterns.json`: the **knowledge base** — 8 documented scam patterns
  (authority impersonation, isolation/threat, financial pressure, spoofing),
  each with a description + real example phrases.
- `sample_transcripts.json`: 5 test call transcripts (3 scam, 2 legit), split
  into chunks to simulate a live, streaming call.
- **Concept to revise:** why the data is structured as "pattern + example
  phrases" — this is what RAG will embed and search over.

### Phase 2 — Environment setup
- Installed: `langgraph`, `chromadb`, `mcp`, `scikit-learn`.
- **Concept to revise:** why we did NOT install `sentence-transformers`/`torch`
  — disk/network constraints — and used TF-IDF embeddings instead. This is a
  real engineering skill: knowing how to swap the embedding backend without
  touching the rest of the RAG pipeline.

### Phase 3 — RAG layer (`rag/knowledge_base.py`)
- Builds a **ChromaDB vector store** from `scam_patterns.json`.
- Custom `TfidfEmbeddingFunction`: converts text → vectors offline (no API/network).
- `retrieve(query_text, top_k)`: given any text, returns the closest known
  scam patterns by **cosine distance**.
- **Concept to revise:**
  - Why RAG at all — grounds the LLM/pipeline in real documented patterns
    instead of guessing, and gives you an auditable citation (pattern ID).
  - **The bug we hit and fixed:** Chroma's default distance metric is L2,
    which is wrong for sparse TF-IDF vectors (magnitude-sensitive). We
    explicitly set `metadata={"hnsw:space": "cosine"}`. This is a classic
    RAG debugging lesson — always sanity-check your retrieval on both
    positive and negative examples, not just the happy path.

### Phase 4 — LangGraph pipeline (`agents/`)
Three files, in order of how you should read them:
1. `state.py` — the **shared state schema** (`ScamDetectionState`), a
   `TypedDict` that flows through every node. This is the single most
   important design decision in a LangGraph project.
2. `nodes.py` — 5 plain functions, each `(state) -> partial_state_update`:
   - `suspicion_filter` — cheap keyword heuristic (fast first pass)
   - `rag_retrieval` — calls Phase 3's `retrieve()`
   - `compound_risk_correlator` — **the key multi-signal reasoning step**:
     tracks which risk *categories* have appeared across the whole session
     and rewards co-occurrence (authority impersonation + isolation + money
     request together is far more diagnostic than any one alone)
   - `decision_node` — routes to monitor / warn / alert by score threshold
   - `action_node` — generates the citizen alert + incident report
3. `graph.py` — wires nodes into a `StateGraph`, including a **conditional
   edge** (`route_after_decision`) that only runs `action_node` if the
   decision warrants it. `process_call_session()` feeds chunks in one at a
   time, carrying state forward — simulating a live call.
- **Concept to revise:** the difference between a LangGraph "node" (a plain
  function) and a LangChain "chain" (linear only) — LangGraph exists
  specifically for branching, stateful, multi-step reasoning like this.

### Phase 5 — MCP server (`mcp_server/server.py`)
- Wraps the same logic as 3 callable tools via `FastMCP`:
  - `check_transcript_chunk` — stateless single-message check
  - `analyze_call_session` — full multi-chunk LangGraph pipeline
  - `generate_citizen_alert` — standardized warning message generator
- **Concept to revise:** why MCP matters here — it turns your detection logic
  into a **standardized service** any client (WhatsApp bot, bank app, IVR
  system) can call, instead of everyone re-implementing scam detection.
  Run `python3 mcp_server/server.py` and it speaks MCP over stdio — connect
  it from Claude Desktop or any MCP client to test interactively.

### Phase 6 — Integration + Evaluation (`main.py`)
- Runs all 5 sample calls through the full pipeline chunk-by-chunk.
- Computes **precision, recall, F1, false-positive rate** against known labels
  — directly matching the judging criteria in the problem statement
  ("false positive rate for citizen-facing tools must be very low").
- Current result on the sample set: **Precision 1.00, Recall 1.00, FPR 0.00**
  (5/5 correctly classified) — but this is a *tiny* hand-written test set, so
  say that honestly in your demo, don't oversell it.

### Phase 8 — Fraud Network Graph Intelligence (`graph_intelligence/fraud_network.py`)
- Gap closed: cross-victim fraud ring detection.
- Uses `networkx` to build a graph where each ALERT-level incident is a node,
  and incidents sharing the same matched scam-pattern IDs get an edge.
- `detect_campaigns()` finds connected clusters = the same fraud ring hitting
  multiple victims, not isolated one-off incidents.
- **Concept to revise:** why this is a *separate* module from the LangGraph
  pipeline — LangGraph reasons about ONE call; this reasons ACROSS many calls.
  Different problem shape, different tool (graph algorithms, not agents).

### Phase 9 — Multi-language Alerts (`localization/alerts.py`)
- Gap closed: regional-language citizen advisories (English, Hindi, Tamil,
  Kannada implemented; easy to extend).
- **Concept to revise:** template-based translation for the FIXED safety
  message (reliable, offline, zero cost) vs. a clearly-marked integration
  stub (`translate_freeform_text`) for arbitrary text that needs a real
  translation API. We deliberately don't fake live translation — a wrong
  translation of "do not send money" is a safety failure, not a demo detail.

### Phase 10 — Geospatial Crime Intelligence (`geospatial/crime_intelligence.py`)
- Gap closed: mapping fraud hotspots for patrol/resource prioritization.
- Pure-Python city-level aggregation (`city_hotspots`) and a simple lat/lon
  grid heatmap (`grid_heatmap`) — no heavy GIS dependencies needed for the
  underlying intelligence; a real map frontend (Leaflet/Mapbox) would just
  visualize this same data.

### Phase 11 — Deployment Layer / Client API (`server/api.py`, `Dockerfile`)
- **This is the actual answer to "how do I deploy this on a server."**
- A FastAPI app wraps the existing pipeline in HTTP endpoints:
  - `POST /webhook/message` — single-message check (WhatsApp/SMS bot use case)
  - `POST /webhook/ivr_session` — full call analysis (IVR/call-recording use
    case), also logs into the Phase 8 fraud graph and Phase 10 geo intel
  - `GET /intelligence/campaigns`, `GET /intelligence/hotspots` — law
    enforcement dashboard endpoints
- Run locally: `uvicorn server.api:app --host 0.0.0.0 --port 8000`
- Deploy with Docker: `docker build -t digital-arrest-shield .` then push to
  Render/Railway/Fly.io (easiest) or AWS ECS/Cloud Run (production scale).
- **Concept to revise:** this file adds NO new intelligence — it's a thin
  HTTP wrapper around Phases 3-10. That separation (core logic vs. delivery
  mechanism) is why MCP (Phase 5) and this REST API can coexist: same brain,
  two different doors in.

### Phase 12 — Honest ML Integration Stubs (`integrations/ml_stubs.py`)
- Gaps addressed: live speech-to-text, AI-voice/deepfake detection, CV
  counterfeit currency detection, payment fraud scoring.
- These need real audio/image ML models or paid APIs not available offline
  in a sandbox. Each function is a **correctly-shaped integration point**
  that raises `NotImplementedError` with exact setup instructions, rather
  than faking output. **Concept to revise:** for a safety-critical system,
  a clear "not implemented" is much better than silently-wrong fabricated
  results — this is a real engineering judgment call worth explaining to
  judges directly.

### Phase 13 — Containerized Deployment (`Dockerfile`)
- Packages the FastAPI server (Phase 11) into a deployable container.
- `docker build -t digital-arrest-shield .` → `docker run -p 8000:8000 ...`
- Push the image to any container host (Render, Railway, Fly.io, AWS ECS,
  Google Cloud Run) to get a real public URL for your demo.



## Gap status (updated)

| Requirement | Status | Where |
|---|---|---|
| Digital arrest scam detection | ✅ Done | `agents/`, `rag/` |
| Real-time transcript analysis | ✅ Done | `agents/graph.py` |
| RAG over scam patterns | ✅ Done | `rag/knowledge_base.py` |
| Multi-agent / Agentic AI | ✅ Done | `agents/nodes.py`, `graph.py` |
| Risk scoring | ✅ Done | `agents/nodes.py` |
| Citizen alert generation | ✅ Done | `agents/nodes.py`, `localization/alerts.py` |
| MCP integration | ✅ Done | `mcp_server/server.py` |
| Fraud network graph intelligence | ✅ Done (Phase 8) | `graph_intelligence/fraud_network.py` |
| Multi-language support | ✅ Done (Phase 9) | `localization/alerts.py` |
| Geospatial crime intelligence | ✅ Done (Phase 10) | `geospatial/crime_intelligence.py` |
| WhatsApp / IVR / Mobile integration | ✅ Done (Phase 11) | `server/api.py` (real HTTP webhooks) |
| Deployment | ✅ Done (Phase 11/13) | `Dockerfile`, `server/api.py` |
| Live speech-to-text | ⚠️ Integration stub only | `integrations/ml_stubs.py::transcribe_audio_chunk` — needs a real STT API key |
| AI-voice / deepfake detection | ⚠️ Integration stub only | `integrations/ml_stubs.py::detect_voice_spoofing` — needs a trained audio model |
| CV counterfeit currency detection | ⚠️ Integration stub only | `integrations/ml_stubs.py::detect_counterfeit_currency` — separate CNN model, out of RAG/LangGraph scope |
| Payment fraud detection | ⚠️ Integration stub only | `integrations/ml_stubs.py::score_transaction_pattern` — needs real bank/UPI data |

The four ⚠️ items genuinely require external ML models, trained audio/image
classifiers, or real financial data partnerships that can't be built or
faked offline. Each has a real, correctly-shaped Python function ready to
wire up — say this explicitly in your demo, it reads as engineering maturity
rather than a weakness.

---

## What to build next (natural extensions for your hackathon submission)

1. **Bigger, more realistic dataset** — scrape/collect real reported scam
   call summaries (news articles, cybercrime portal advisories) and more
   varied legit call transcripts, to stress-test false positive rate properly.
2. **Swap TF-IDF for real embeddings** — if you have internet/HF access at
   the hackathon venue, swap `TfidfEmbeddingFunction` for
   `sentence-transformers` (all-MiniLM-L6-v2) for better semantic matching.
3. **Speech-to-text front end** — plug in a live STT API (Whisper, etc.) so
   `transcript_chunks` come from real audio instead of pre-written text.
4. **Multi-language support** — the problem statement asks for regional
   language advisories; add a translation node before `action_node`.
5. **Persist incident reports** — write `incident_report` outputs to a real
   database instead of just returning them, so repeated scam scripts across
   victims can be clustered into "fraud campaigns" (graph intelligence, as
   described in the problem statement's Fraud Network Graph Intelligence idea).
6. **Architecture diagram + demo video** — required deliverables per the
   problem statement; diagram the graph in `agents/graph.py` visually.

---

## File map

```
digital-arrest-shield/
├── data/
│   ├── scam_patterns.json       # Phase 1: RAG knowledge base
│   └── sample_transcripts.json  # Phase 1: test calls (scam + legit)
├── rag/
│   └── knowledge_base.py        # Phase 3: RAG retrieval
├── agents/
│   ├── state.py                 # Phase 4a: shared state schema
│   ├── nodes.py                 # Phase 4b: pipeline node functions
│   └── graph.py                 # Phase 4c: LangGraph wiring
├── mcp_server/
│   └── server.py                # Phase 5: MCP tool exposure
├── graph_intelligence/
│   └── fraud_network.py         # Phase 8: cross-victim campaign detection
├── localization/
│   └── alerts.py                # Phase 9: multi-language alerts
├── geospatial/
│   └── crime_intelligence.py    # Phase 10: hotspot mapping
├── server/
│   └── api.py                   # Phase 11: FastAPI deployment layer
├── integrations/
│   └── ml_stubs.py              # Phase 12: honest STT/voice/CV/payment stubs
├── main.py                      # Phase 6: demo runner + evaluation
├── Dockerfile                   # Phase 13: containerized deployment
├── requirements.txt
└── README.md                    # this file
```
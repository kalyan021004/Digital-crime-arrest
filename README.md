# Digital Arrest Scam Shield

Detects "digital arrest" scam calls **while they are still happening** — the
fraud where callers impersonating CBI, ED or Customs officers hold victims in a
multi-day psychological hostage situation over video call and coerce a transfer.

The pipeline reads a call transcript chunk by chunk, scores it against a
retrieval knowledge base of documented scam patterns, and fires a
regional-language warning to the citizen *before* money moves. Alert-level
incidents are persisted, clustered into suspected campaigns, and mapped to
geographic hotspots for law enforcement.

---

## Quick start

```bash
git clone <your-fork-url>
cd Digital-crime-arrest

pip install -r requirements.txt
cp .env.example .env          # PowerShell: Copy-Item .env.example .env

python main.py                # 5-call demo + precision/recall/FPR
```

That works with **no external services**. With `QDRANT_URL` unset the RAG layer
runs an embedded file-backed Qdrant in `qdrant_data/`, and with MongoDB
unreachable incident storage falls back to memory (you'll see a warning; nothing
is persisted between runs).

First run downloads the `BAAI/bge-small-en-v1.5` embedding model (~130 MB) and
pulls in torch via `sentence-transformers`, so allow a few minutes.

### Running the API and dashboard

Embedded Qdrant takes an **exclusive lock on its data directory**, so only one
process can use it at a time. To run `main.py` and the API together, start a
real Qdrant server:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

and set in `.env`:

```
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

Then:

```bash
uvicorn server.api:app --reload --port 8000     # API on :8000

cd dashboard && python -m http.server 3000      # dashboard on :3000
```

The dashboard fetches `http://localhost:8000` and the API's CORS policy only
allows origin `:3000`, so serve it — opening `index.html` from disk will fail
CORS.

### MCP server

```bash
python mcp_server/server.py
```

Speaks MCP over stdio; connect from Claude Desktop or any MCP client to call
`check_transcript_chunk`, `analyze_call_session` and `generate_citizen_alert`.

### Tests

```bash
python -m pytest tests/ -v      # or: python tests/test_scoring.py
```

These stub the knowledge base, so they need no models, no Qdrant and no Mongo.

---

## Configuration

| Variable | Required | Default | Notes |
|---|---|---|---|
| `QDRANT_URL` | No | *(embedded)* | Unset → file-backed Qdrant in `qdrant_data/`. Set → connects to that server; if unreachable, warns and falls back to embedded rather than crashing. **Leave it commented out unless a server is actually running.** |
| `QDRANT_API_KEY` | No | — | Only for Qdrant Cloud. |
| `MONGODB_URI` | No | `mongodb://localhost:27017` | Unreachable → in-memory fallback, incidents not persisted. |

---

## Architecture

```
transcript chunk
      │
      ▼
┌─────────────────────┐
│ 1 suspicion_filter  │  cheap keyword heuristic (no model call)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2 rag_retrieval     │  bge-small embeddings → Qdrant cosine search
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 3 compound_risk_    │  tracks which risk CATEGORIES have co-occurred
│   correlator        │  across the session; the key reasoning step
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4 decision_node     │  monitor (<0.45) / warn (0.45) / alert (0.75)
└─────────┬───────────┘
          ▼ (conditional edge — only if warn/alert)
┌─────────────────────┐
│ 5 action_node       │  localized citizen alert + incident report → Mongo
└─────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
  fraud_network.py                          crime_intelligence.py
  incidents sharing pattern IDs             city hotspots + lat/lon
  → suspected campaigns                     grid heatmap
```

The insight the design rests on: **no single phrase proves a scam.** "This is
Officer Sharma" is not a crime. But authority impersonation *plus* isolation
and threat *plus* financial pressure, accumulating across one conversation, is
the documented signature of a digital arrest. Node 3 is what scores that
co-occurrence, and it is why this is a stateful graph rather than a classifier.

---

## Layout

```
data/
  scam_patterns.json        8 documented patterns — the RAG knowledge base
  sample_transcripts.json   5 test calls (3 scam, 2 legit), chunked
rag/
  config.py                 env config + embedded-Qdrant path
  embeddings.py             BAAI/bge-small-en-v1.5 wrapper
  vector_store.py           Qdrant client (server or embedded fallback)
  indexer.py                embeds + upserts patterns
  retriever.py              top-k cosine search → matches with scores
  knowledge_base.py         ScamPatternKB facade
agents/
  state.py                  ScamDetectionState (the shared TypedDict)
  nodes.py                  the 5 node functions + shared thresholds
  graph.py                  StateGraph wiring + process_call_session()
localization/alerts.py      EN / HI / TA / KN citizen alert templates
graph_intelligence/         cross-victim campaign clustering (networkx)
geospatial/                 city hotspots + lat/lon grid heatmap
db/mongo.py                 Mongo connection + in-memory fallback
server/api.py               FastAPI: webhooks + intelligence endpoints
mcp_server/server.py        MCP tool exposure
dashboard/index.html        law-enforcement dashboard (serve on :3000)
twilo/dummy_call.py         Twilio voice webhook (answers only, no STT yet)
tests/                      scoring regression tests
main.py                     demo runner + precision/recall/FPR
```

---

## Evaluation

`main.py` reports precision, recall, F1 and false-positive rate against the
labels in `sample_transcripts.json`.

**Read those numbers with care.** The set is 5 hand-written calls — 3 scam,
2 legitimate. With two negatives, false-positive rate can only ever come out as
0%, 50% or 100%; it cannot measure what the problem statement actually asks for
("false positive rate for citizen-facing tools must be very low"). Any headline
figure from this set is not yet meaningful.

The gap that matters most is **hard negatives**: genuine bank KYC calls, real
police verification, courier delivery confirmations, insurance renewals. Those
share vocabulary with scams ("verification", "transfer", "police", "account")
and are exactly what a deployed system would wrongly flag. Precision on 2 easy
negatives says nothing about them.

`RAG_MATCH_THRESHOLD` in `agents/nodes.py` (currently 0.75) is inherited, not
calibrated. bge-small scores unrelated short sentences around 0.6–0.7, so it
sits close to the noise floor and should be tuned against a labelled set before
anyone relies on it.

---

## Status against the problem statement

| Requirement | Status |
|---|---|
| Digital arrest scam detection | Working |
| Real-time chunked transcript analysis | Working |
| RAG over documented scam patterns | Working (Qdrant + bge-small) |
| Agentic multi-step reasoning | Working (LangGraph, 5 nodes) |
| Citizen alerts, regional languages | Working (EN/HI/TA/KN of 12 asked for) |
| MCP tool exposure | Working |
| Fraud network graph intelligence | Working, but links only on shared pattern IDs — with 8 patterns most alerts share one, so clusters over-merge. Needs phone/UPI/device identifiers to be meaningful. |
| Geospatial hotspots | Working |
| HTTP / webhook delivery | Working |
| Law-enforcement dashboard | Working, **no authentication** — do not expose publicly |
| Live speech-to-text | Not built (`faster-whisper` declared, not wired) |
| AI-voice / deepfake detection | Not built |
| Counterfeit currency CV | Not built |
| Evidence auditability | Partial — reports cite pattern IDs, matched chunks and scores, but no timestamp, model version or tamper-evident hash |

Four of the five pillars in the problem statement are addressed to some degree.
**Counterfeit currency detection is not started**, and it is listed first in the
evaluation criteria — either build a module or scope it out explicitly in the
deck rather than leaving it unmentioned.

---

## Known issues

- `dashboard/index.html` calls `/intelligence/*` with no auth; those endpoints
  return victim transcripts and locations.
- Transcripts are stored in Mongo unencrypted and unredacted — worth addressing
  under the DPDP Act 2023 before any real deployment.
- `pyproject.toml` still requires Python `>=3.14`; `chromadb` is still declared
  but no longer imported anywhere after the Qdrant migration.
- Embedded Qdrant is single-process (exclusive lock). Use a server to run
  `main.py` and the API simultaneously.

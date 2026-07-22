# Demo Video Script — Digital Arrest Scam Shield

**Length:** ~90 seconds (hard cap 2:00). Technical, concise, no marketing tone.
Judges trust a tight technical walkthrough more than a pitch.

## Setup before recording
- [ ] `uvicorn server.api:app --port 8000` running (no `--reload`).
- [ ] `cd dashboard && python -m http.server 3000` running.
- [ ] Browser at `http://localhost:3000`, hard-refreshed, zoom ~110%.
- [ ] Do one dry run of "Run scam call" first — confirm the score visibly
      climbs (monitor → warn → alert) with the new transcript.
- [ ] Keep the terminal off-screen (the Mongo/HF warnings look like errors).
- [ ] Record 1080p. If the file exceeds 50MB, upload to Google Drive and paste
      the share link ("anyone with the link") in the form.

---

## 1 · What it is (0:00–0:15)

> "Digital Arrest Scam Shield detects digital-arrest fraud calls in real time.
> Each transcript chunk passes through a five-stage LangGraph pipeline that
> fuses a keyword filter, semantic retrieval over a documented scam-pattern
> knowledge base, and a structural coercion detector into a single cumulative
> suspicion score."

*(Keep it factual. Name the architecture — it signals you built the thing.)*

## 2 · Live detection (0:15–0:55) — core

Click **Run scam call**. Narrate to the animation:

> "The call opens like a routine verification — no scam markers, so the score
> stays in the monitor band."

*(chunks 3–4, score climbs, badge → warn/alert)*
> "As authority impersonation, isolation, and a threat of arrest appear across
> successive chunks, distinct risk categories accumulate and the compound score
> rises. It crosses the alert threshold here —"

*(chunk 6, the transfer demand)*
> "— before the money transfer is even requested. The alert is generated at the
> point of coercion, not after the loss. It's rendered in the citizen's
> language; Hindi, Tamil and Kannada are supported alongside English."

## 3 · No false alarm (0:55–1:10)

Click **Run legit call**.

> "This is a genuine bank fraud-alert. It contains 'fraud', 'suspicious', and
> 'transfer', but there's no coercion structure — and a negation guard discounts
> 'we will never ask for a transfer'. The score stays low, no alert. The system
> keys on structure, not vocabulary, which is what keeps the false-positive rate
> down."

## 4 · Intelligence layer (1:10–1:25)

Scroll to the campaigns / hotspots panel.

> "Alert-level incidents are logged and correlated: calls sharing a scam-pattern
> fingerprint cluster into suspected campaigns, and are aggregated into
> geographic hotspots — exposed over both REST and MCP for law-enforcement
> tooling."

## 5 · Evaluation (1:25–1:45)

Cut to `evaluate.py` output or the before/after slide.

> "We evaluated on a 168-call adversarial set — 40 keyword-trap negatives and
> 16 euphemistic scams — with bootstrap confidence intervals. Retrieval alone
> missed the euphemistic scams; adding the structural detector recovered them,
> reaching precision 1.0, recall 1.0, and a zero false-positive rate. The data
> is synthetic, so we report this as a clean-distribution upper bound, not a
> field measurement."

**Close:**
> "Detection at the point of contact, with the false-positive rate treated as
> the primary constraint. Thank you."

---

## 60-second cut
Keep sections 2, 3, 5. Drop 1 (open straight on the demo) and 4.

## Rules
- Always pair "precision 1.0 / recall 1.0 / FPR 0.0" with "168-call adversarial
  set, synthetic data" — never state the perfect numbers bare.
- Show the working system; don't read architecture off a slide.
- Narrate over every replaying call — no dead air.

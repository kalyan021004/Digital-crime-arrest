"""
soft_signals.py -- structural coercion detector
================================================
Catches digital-arrest scams that deliberately AVOID the obvious keywords
("arrest", "CBI", "warrant") and express the same coercion in soft language --
"security hold", "cooperation amount", "keep this between us".

WHY A SEPARATE SIGNAL
---------------------
The keyword filter and the RAG retriever both key on explicit scam phrasing.
Adversarial evaluation (data/generate_eval_set.py, the adv_* categories)
exposed a clean blind spot: euphemistic scams scored ~0 and were all missed.

WHAT MAKES THIS GENERALISE (not teach-to-the-test)
--------------------------------------------------
It does NOT match specific scam sentences. It detects the STRUCTURE every
digital-arrest scam shares regardless of wording:

    isolation pressure   +   a directed transfer of money to an account the
    (stay on the call,       caller controls (move your balance to the account
     don't tell anyone)      I provide, clearance fee, refundable deposit)

That co-occurrence is the diagnostic fingerprint of the scam and is very rare
in legitimate calls. A legit bank may mention "transfer" or "verification" --
but almost never tells you to stay on the line AND move your money to an
account it dictates.

THE NEGATION GUARD
------------------
Legitimate calls often mention these very concepts in order to REASSURE:
"we will never ask you to transfer money", "we will not ask for an OTP".
Counting those as scam signals would create false positives -- exactly what
the adversarial legit set (adv_fraud_alert, adv_move_own_account, ...) tests.
So a money cue is ignored when it appears in a negated/reassuring context.

HONESTY
-------
This is a lexical heuristic, not semantic understanding. It raises recall on
soft-language scams substantially, but a fully robust solution needs an
LLM-based intent classifier. That limitation is stated in the evaluation doc.
"""

import re

# Isolation / control pressure -- "you may not leave, tell anyone, or hang up".
ISOLATION_CUES = [
    "stay on the call", "stay on the line", "stay with me", "stay on video",
    "do not disconnect", "don't disconnect", "cannot disconnect", "can't disconnect",
    "keep this private", "keep this between us", "keep this conversation private",
    "keep this confidential", "strictly confidential", "confidential matter",
    "confidential investigation",
    "do not discuss", "don't discuss", "do not tell", "don't tell",
    "do not contact your", "don't contact your", "not permitted to speak",
    "do not inform", "don't inform",
    "do not visit the branch", "don't visit the branch",
    "under surveillance", "monitoring you", "on camera", "we can see everything",
    "not allowed to", "you cannot leave", "you can't leave",
]

# Directed money movement to an account/fee the caller controls.
MONEY_CUES = [
    "verification account", "protected account", "recovery account",
    "reactivation account", "safe account", "monitored account",
    "treasury account", "clearance account", "the account i provide",
    "the account i share", "the account i give", "account i am sharing",
    "account we provide",
    "cooperation amount", "clearance fee", "processing fee", "security deposit",
    "security amount", "reactivation fee",
    "move your balance", "move your money", "move your funds",
    "move everything", "transfer everything",
    "send it to the account", "send the amount", "send rs", "deposit rs",
    "transfer rs", "transfer the amount", "pay rs",
    "refundable", "fully refundable",
]

# Institutional-role claims (soft impersonation without naming CBI/police).
INSTITUTION_CUES = [
    "verification cell", "compliance unit", "security desk", "security team",
    "fraud monitoring", "payments support", "central verification",
    "verification department", "security review", "investigation",
    "case officer", "officer", "department", "bureau", "authority",
]

# If a money cue sits in a reassuring/negated context, don't count it.
NEGATION_MARKERS = [
    "will not ask", "won't ask", "will never ask", "never ask",
    "do not need to", "don't need to", "nothing needs to",
    "not ask for", "no payment", "no advance payment", "without asking",
    "we will not", "we will never", "you do not need", "you don't need",
]


def _contains_any(text, cues):
    return [c for c in cues if c in text]


def detect(chunks):
    """
    Scan the accumulated transcript for the soft-coercion structure.

    Returns a dict:
        isolation      : bool  -- isolation/control pressure present
        money          : bool  -- directed money movement present (un-negated)
        institution    : bool  -- soft institutional impersonation present
        soft_scam      : bool  -- isolation AND money both present (the fingerprint)
        categories     : list  -- risk categories to add if soft_scam
        cues           : dict  -- which phrases matched (for auditability)
    """
    # Per-chunk so the negation guard is local to a sentence group.
    isolation_hits, money_hits, inst_hits = [], [], []

    for chunk in chunks:
        t = chunk.lower()
        isolation_hits += _contains_any(t, ISOLATION_CUES)
        inst_hits += _contains_any(t, INSTITUTION_CUES)

        money_here = _contains_any(t, MONEY_CUES)
        if money_here and not any(neg in t for neg in NEGATION_MARKERS):
            money_hits += money_here

    isolation = len(isolation_hits) > 0
    money = len(money_hits) > 0
    institution = len(inst_hits) > 0
    soft_scam = isolation and money

    categories = []
    if soft_scam:
        categories = ["isolation_and_threat", "financial_pressure"]
        if institution:
            categories.append("authority_impersonation")

    return {
        "isolation": isolation,
        "money": money,
        "institution": institution,
        "soft_scam": soft_scam,
        "categories": categories,
        "cues": {
            "isolation": sorted(set(isolation_hits)),
            "money": sorted(set(money_hits)),
            "institution": sorted(set(inst_hits)),
        },
    }

"""
generate_eval_set.py
=====================
Builds a labelled evaluation set of call transcripts for measuring digital
arrest scam detection performance -- specifically precision, recall and the
false-positive rate that the problem statement calls out as critical.

WHY THIS EXISTS
---------------
The original data/sample_transcripts.json has 5 calls (3 scam, 2 legit). With
only two negatives, false-positive rate can only ever be 0%, 50% or 100% -- it
cannot measure what "very low FPR" means. This script produces a balanced set
of ~60 scam and ~60 legitimate calls so the metrics become meaningful.

HONESTY NOTE (say this in your writeup)
---------------------------------------
These transcripts are SYNTHETIC. They are composed from documented digital
arrest scam scripts (I4C / cybercrime.gov.in advisories, MHA press releases,
published news reconstructions) and from realistic legitimate Indian
institutional call scripts. They are NOT transcriptions of real recorded calls
-- no such public labelled dataset exists, because these are voice scams and
victim recordings are not published. Synthetic-but-grounded data is the honest
option here; the alternative (claiming real data you do not have) is worse.

THE NEGATIVES ARE THE POINT
---------------------------
Easy negatives ("your Amazon order shipped") prove nothing -- any keyword
matcher clears them. The value is in HARD negatives: genuine bank KYC calls,
real police callbacks, courier confirmations, insurance renewals. These share
vocabulary with scams ("verification", "account", "police", "transfer") and are
exactly what a deployed system would wrongly flag. FPR on hard negatives is the
number that matters.

Each record carries extra metadata (scam_type / negative_type / difficulty) so
evaluate.py can break performance down by category. main.py ignores the extra
keys.

USAGE
-----
    python data/generate_eval_set.py                 # writes eval_transcripts.json
    python data/generate_eval_set.py --n-scam 80 --n-legit 80
    python data/generate_eval_set.py --out data/eval_transcripts.json --seed 7
"""

import argparse
import json
import os
import random

# ---------------------------------------------------------------------------
# Slot vocabularies -- swapped into templates so no two transcripts are identical
# ---------------------------------------------------------------------------

CITIES = [
    ("Mumbai", 19.0760, 72.8777), ("Delhi", 28.6139, 77.2090),
    ("Bengaluru", 12.9716, 77.5946), ("Hyderabad", 17.3850, 78.4867),
    ("Chennai", 13.0827, 80.2707), ("Kolkata", 22.5726, 88.3639),
    ("Pune", 18.5204, 73.8567), ("Ahmedabad", 23.0225, 72.5714),
    ("Jaipur", 26.9124, 75.7873), ("Lucknow", 26.8467, 80.9462),
    ("Surat", 21.1702, 72.8311), ("Nagpur", 21.1458, 79.0882),
    ("Indore", 22.7196, 75.8577), ("Bhopal", 23.2599, 77.4126),
    ("Patna", 25.5941, 85.1376), ("Kochi", 9.9312, 76.2673),
]

FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sunita", "Vikram", "Anjali", "Rahul",
    "Deepa", "Sanjay", "Kavita", "Arun", "Meena", "Suresh", "Pooja",
    "Manoj", "Neha", "Ravi", "Divya", "Karan", "Shruti",
]

AGENCIES = ["CBI", "Enforcement Directorate", "Narcotics Control Bureau",
            "Cyber Crime Branch", "Mumbai Police Crime Branch"]

COURIERS = ["FedEx", "DHL", "BlueDart", "DTDC", "India Post"]

BANKS = ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank",
         "Kotak Mahindra Bank", "Punjab National Bank"]

AMOUNTS = ["45,000", "50,000", "75,000", "90,000", "1,20,000", "2,00,000",
           "2,50,000", "3,80,000", "5,00,000"]

CONTRABAND = ["500 grams of MDMA", "illegal narcotic substances",
              "5 fake passports", "banned psychotropic drugs",
              "illegal SIM cards and fake documents"]


def _pick(rng, seq):
    return rng.choice(seq)


# ---------------------------------------------------------------------------
# SCAM scenario builders -- each returns a list of transcript chunks.
# Every scam call escalates through the documented arc:
#   authority impersonation -> isolation/threat -> financial pressure.
# ---------------------------------------------------------------------------

def scam_parcel_customs(rng):
    officer, agency = _pick(rng, FIRST_NAMES), _pick(rng, AGENCIES)
    item, amt = _pick(rng, CONTRABAND), _pick(rng, AMOUNTS)
    return [
        f"Hello, I am calling from the Customs department. A parcel booked in your name has been intercepted at the airport.",
        f"On inspection it was found to contain {item}. This is a serious offence under the NDPS Act.",
        f"This is now a confidential investigation. Do not disconnect this call or discuss it with anyone, or you will be arrested immediately.",
        f"I am transferring your case to senior officer {officer} of the {agency}. Please stay on video call for verification.",
        f"To prove your innocence and avoid arrest, transfer Rs {amt} to this RBI verification account. It will be fully refunded after the enquiry.",
    ]


def scam_courier_drugs(rng):
    courier, item, amt = _pick(rng, COURIERS), _pick(rng, CONTRABAND), _pick(rng, AMOUNTS)
    return [
        f"Good morning, this is {courier} courier services. We have a parcel under your Aadhaar number that could not be delivered.",
        f"The package has been flagged by Customs because it contains {item}.",
        f"You must not disconnect. A police officer will now speak to you regarding this criminal matter.",
        f"A non-bailable warrant has been prepared in your name. To place it on hold you must cooperate fully right now.",
        f"Deposit Rs {amt} as a security amount into the government verification account so we can confirm your accounts are clean.",
    ]


def scam_sim_trai(rng):
    officer, amt = _pick(rng, FIRST_NAMES), _pick(rng, AMOUNTS)
    return [
        f"This call is from the Department of Telecommunications. Your mobile number is being used for illegal activities.",
        f"Your SIM card will be permanently blocked within two hours, and an FIR has been registered against you in {_pick(rng, [c[0] for c in CITIES])}.",
        f"Do not cut this call. I am connecting you to officer {officer} at the Cyber Crime Branch for a mandatory verification.",
        f"Your bank accounts are linked to a money laundering case. Keep this strictly confidential or you face immediate arrest.",
        f"For verification, transfer Rs {amt} to the secure account we provide. This is refundable once your identity is cleared.",
    ]


def scam_ed_laundering(rng):
    officer, bank, amt = _pick(rng, FIRST_NAMES), _pick(rng, BANKS), _pick(rng, AMOUNTS)
    return [
        f"This is the Enforcement Directorate. Your PAN card has been linked to a large money laundering investigation.",
        f"A company under investigation has used your identity to open a bank account at {bank}.",
        f"You have only 30 minutes to comply, or a non-bailable warrant will be issued and you will be taken into digital custody.",
        f"Officer {officer} will remain on video call to monitor you. Do not contact your family or lawyer during this period.",
        f"Declare your total bank balance and transfer Rs {amt} to this account for verification. It is fully refundable.",
    ]


def scam_aadhaar_case(rng):
    officer, item, amt = _pick(rng, FIRST_NAMES), _pick(rng, CONTRABAND), _pick(rng, AMOUNTS)
    return [
        f"Namaste, I am calling regarding your Aadhaar card which has been misused in a criminal case.",
        f"A parcel containing {item} was seized and your Aadhaar was used to book it.",
        f"This is a digital arrest. You are under investigation and cannot leave your house or end this call.",
        f"Senior officer {officer} is watching you on camera. Any attempt to inform others will be treated as obstruction.",
        f"To clear your name, move Rs {amt} to the RBI-monitored account immediately. The money is safe and refundable.",
    ]


def scam_court_summons(rng):
    officer, amt = _pick(rng, FIRST_NAMES), _pick(rng, AMOUNTS)
    return [
        f"This is an automated call from the honourable court. A summons has been issued against you for a financial fraud case.",
        f"Press one to speak to the case officer. ... You are now connected to investigating officer {officer}.",
        f"An arrest warrant is active. If you disconnect, police will be sent to your address within the hour.",
        f"This matter is confidential and under digital surveillance. Stay on the line and do not alert anyone.",
        f"To convert the arrest warrant to bail, pay Rs {amt} into the court's verification account now.",
    ]


def scam_bank_fraud(rng):
    officer, bank, amt = _pick(rng, FIRST_NAMES), _pick(rng, BANKS), _pick(rng, AMOUNTS)
    return [
        f"Hello, I am officer {officer} from the Cyber Crime Branch. Your {bank} account is involved in a fraud complaint.",
        f"Several victims have named your account as the one that received stolen money.",
        f"This is now a police matter. Do not hang up or your assets will be frozen and you will be arrested today.",
        f"Stay on video call for interrogation. You are not permitted to speak to anyone else while this is ongoing.",
        f"To prove the funds are legitimate, transfer Rs {amt} to our verification account for a 24-hour check.",
    ]


SCAM_BUILDERS = [
    ("parcel_customs", scam_parcel_customs),
    ("courier_drugs", scam_courier_drugs),
    ("sim_trai", scam_sim_trai),
    ("ed_laundering", scam_ed_laundering),
    ("aadhaar_case", scam_aadhaar_case),
    ("court_summons", scam_court_summons),
    ("bank_fraud", scam_bank_fraud),
]


# ---------------------------------------------------------------------------
# LEGITIMATE (hard-negative) scenario builders.
# These deliberately use overlapping vocabulary (verification, account, police,
# transfer, KYC) but are genuine, non-coercive calls. NONE ask for a transfer
# to a "verification account", none threaten arrest, none demand secrecy.
# ---------------------------------------------------------------------------

def legit_bank_kyc(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} calling from {bank}. Your account KYC is due for a routine update.",
        f"You can complete the verification at any branch, or through our official mobile app at your convenience.",
        f"We will never ask for your OTP, PIN, or a money transfer over the phone.",
        f"Please visit your nearest branch within 30 days. Thank you for banking with us.",
    ]


def legit_credit_card(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hi, this is {agent} from {bank} regarding your recent credit card application.",
        f"I just need to confirm your current mailing address for delivery of the card.",
        f"The card will arrive within 5 to 7 working days by registered post.",
        f"Is there anything else I can help you with today? Thank you.",
    ]


def legit_police_callback(rng):
    officer, city = _pick(rng, FIRST_NAMES), _pick(rng, [c[0] for c in CITIES])
    return [
        f"Good afternoon, this is sub-inspector {officer} from {city} police station.",
        f"You filed a complaint about a lost mobile phone last week. I am calling with an update.",
        f"We have registered your report; please collect a copy of the FIR from the station when convenient.",
        f"If you have any questions you can visit us during working hours. Thank you.",
    ]


def legit_courier_delivery(rng):
    courier, agent = _pick(rng, COURIERS), _pick(rng, FIRST_NAMES)
    return [
        f"Hello, this is {agent} from {courier}. We have a parcel out for delivery to your address today.",
        f"The delivery agent will reach you between 2 and 5 pm. Please keep your phone reachable.",
        f"You can share the OTP with the delivery person only when the parcel is in your hand.",
        f"Thank you for choosing {courier}.",
    ]


def legit_insurance_renewal(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Namaste, this is {agent} from your life insurance company regarding your policy renewal.",
        f"Your premium is due next month. You can pay online through our official portal or at any branch.",
        f"Renewing on time keeps your coverage active. No urgency, you have until the due date.",
        f"Would you like me to email you the renewal link? Thank you for your time.",
    ]


def legit_loan_emi(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} from {bank} loan servicing. This is a reminder that your EMI is due on the 5th.",
        f"You can pay through auto-debit, the mobile app, or at the branch.",
        f"If you have already paid, please ignore this message. There is no penalty yet.",
        f"Feel free to call our official helpline if you have questions. Thank you.",
    ]


def legit_telecom_upgrade(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Hi, this is {agent} from your mobile network's customer care.",
        f"You are eligible for an upgraded data plan at the same monthly price.",
        f"There is no obligation. You can accept the offer through the official app or by replying to our SMS.",
        f"Have a good day, and thank you for staying with us.",
    ]


def legit_tax_refund(rng):
    return [
        f"This is an informational message from the Income Tax Department's official channel.",
        f"Your income tax refund for the assessment year has been processed.",
        f"The amount will be credited to your registered bank account automatically. No action is required from you.",
        f"For details, log in only to the official incometax.gov.in portal. We never ask for payment.",
    ]


def legit_hospital_appointment(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Hello, this is {agent} from the hospital front desk.",
        f"I am calling to confirm your doctor's appointment scheduled for tomorrow morning.",
        f"Please arrive 15 minutes early and bring your previous reports.",
        f"Reply or call back if you need to reschedule. Thank you.",
    ]


def legit_job_interview(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Good morning, this is {agent} from the HR team regarding the position you applied for.",
        f"We would like to schedule your interview for next week. Which day works for you?",
        f"The interview will be held at our office; the address is on your offer email.",
        f"Looking forward to meeting you. Have a great day.",
    ]


def legit_mutual_fund_kyc(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Hello, this is {agent} from your mutual fund distributor.",
        f"Your investment account requires a one-time KYC re-verification as per SEBI norms.",
        f"You can complete it via the official app's video-KYC feature at your convenience.",
        f"We will not ask you to transfer any money for this. Thank you.",
    ]


def legit_delivery_otp(rng):
    return [
        f"Your food order has been picked up and is on the way.",
        f"The delivery partner will arrive in about 20 minutes.",
        f"Please share the four-digit OTP with the partner at the door to confirm delivery.",
        f"Enjoy your meal!",
    ]


def legit_utility_bill(rng):
    return [
        f"This is a reminder from your electricity provider's official service.",
        f"Your monthly bill is generated and due in ten days.",
        f"You can pay through the official app, website, or any authorised centre.",
        f"Ignore this message if you have already paid. Thank you.",
    ]


LEGIT_BUILDERS = [
    ("bank_kyc", legit_bank_kyc, "hard"),
    ("credit_card", legit_credit_card, "hard"),
    ("police_callback", legit_police_callback, "hard"),
    ("courier_delivery", legit_courier_delivery, "hard"),
    ("insurance_renewal", legit_insurance_renewal, "hard"),
    ("loan_emi", legit_loan_emi, "hard"),
    ("telecom_upgrade", legit_telecom_upgrade, "medium"),
    ("tax_refund", legit_tax_refund, "hard"),
    ("hospital_appointment", legit_hospital_appointment, "easy"),
    ("job_interview", legit_job_interview, "easy"),
    ("mutual_fund_kyc", legit_mutual_fund_kyc, "hard"),
    ("delivery_otp", legit_delivery_otp, "easy"),
    ("utility_bill", legit_utility_bill, "easy"),
]


# ---------------------------------------------------------------------------
# ADVERSARIAL LEGITIMATE calls -- "keyword traps".
# These deliberately use the SCARIEST scam-adjacent vocabulary (fraud,
# suspicious transaction, police verification, customs duty, court, arrest,
# KYC deactivation, tax demand) while remaining genuinely legitimate. The
# distinguishing markers of legitimacy are always present: the caller directs
# you to OFFICIAL channels, never demands a transfer to a "verification
# account", never orders secrecy, never threatens on-the-spot arrest, and is
# fine with you calling back. This is the real test of false-positive rate:
# does the model key on fear-words, or on the actual coercion structure?
# ---------------------------------------------------------------------------

def legit_adv_fraud_alert(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} from {bank}'s fraud monitoring team.",
        f"We have blocked a suspicious transaction on your card as a precaution. Your money is safe.",
        f"We will not ask for your PIN, OTP, or any transfer. Please call the number printed on the back of your card to confirm the block.",
        f"You can also review the transaction in your official banking app. Thank you.",
    ]


def legit_adv_passport_police(rng):
    officer, city = _pick(rng, FIRST_NAMES), _pick(rng, [c[0] for c in CITIES])
    return [
        f"Good morning, this is officer {officer} from {city} police, calling for your passport address verification.",
        f"This is a routine check requested by the passport office for your application.",
        f"An officer will visit your address in person; you do not need to pay anything or share bank details.",
        f"If you prefer, you may visit the station with your documents. Thank you for your cooperation.",
    ]


def legit_adv_customs_duty(rng):
    courier, amt = _pick(rng, COURIERS), _pick(rng, ["350", "600", "1,200"])
    return [
        f"Hello, this is {courier}. Your international parcel has a customs duty of Rs {amt} payable on delivery.",
        f"You can pay the delivery agent in cash or by card when the parcel arrives.",
        f"This is a standard import charge; a receipt will be provided. No advance payment is needed.",
        f"The parcel is scheduled for delivery tomorrow. Thank you.",
    ]


def legit_adv_tax_demand(rng):
    return [
        f"This is an informational call from the Income Tax Department's official helpline.",
        f"Our records show a pending tax demand on your account for the last assessment year.",
        f"Please log in to the official incometax.gov.in portal to review and pay it. We never collect payment over the phone.",
        f"If you have already responded, kindly ignore this message. Thank you.",
    ]


def legit_adv_court_date(rng):
    agent = _pick(rng, FIRST_NAMES)
    return [
        f"Hello, this is advocate {agent}'s office calling about your pending civil case.",
        f"Your next court hearing has been scheduled; please note the date and bring your documents.",
        f"There is no payment involved in this call. You can verify the hearing date on the court's official e-portal.",
        f"Please reach the court a little early. Thank you.",
    ]


def legit_adv_sim_kyc(rng):
    return [
        f"This is a service message from your mobile operator regarding SIM re-verification.",
        f"As per regulations, please complete your SIM KYC to avoid interruption of service.",
        f"You can do this free of charge at any authorised store with your ID. We will not ask for an OTP or payment on this call.",
        f"There is no immediate deactivation; you have several weeks. Thank you.",
    ]


def legit_adv_move_own_account(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} from {bank}. We are migrating old accounts to a new IFSC system.",
        f"Your existing account stays yours; nothing needs to be transferred by you.",
        f"If you have questions, please call our official helpline or visit a branch. We will never ask you to move money to another account.",
        f"You will receive a confirmation SMS from our official sender ID. Thank you.",
    ]


def legit_adv_loan_legal_notice(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} from {bank}'s loan recovery department.",
        f"Your loan EMI is overdue by two months, and continued default may lead to legal recovery action.",
        f"You can clear the dues through the official app, netbanking, or at the branch. Please contact us on the official number to discuss a plan.",
        f"We are here to help you regularise the account. Thank you.",
    ]


ADVERSARIAL_LEGIT_BUILDERS = [
    ("adv_fraud_alert", legit_adv_fraud_alert),
    ("adv_passport_police", legit_adv_passport_police),
    ("adv_customs_duty", legit_adv_customs_duty),
    ("adv_tax_demand", legit_adv_tax_demand),
    ("adv_court_date", legit_adv_court_date),
    ("adv_sim_kyc", legit_adv_sim_kyc),
    ("adv_move_own_account", legit_adv_move_own_account),
    ("adv_loan_legal_notice", legit_adv_loan_legal_notice),
]


# ---------------------------------------------------------------------------
# ADVERSARIAL SCAMS -- subtle, euphemistic, low obvious-keyword.
# These are still digital-arrest-style extortion (impersonation -> isolation ->
# money) but avoid the giveaway words ("arrest", "CBI", "warrant"). They use
# soft euphemisms: "security hold" instead of arrest, "cooperation amount"
# instead of transfer, "keep this private" instead of "do not tell anyone".
# The test: does the model catch the coercion STRUCTURE, or only keywords?
# ---------------------------------------------------------------------------

def scam_adv_slowburn(rng):
    agent, amt = _pick(rng, FIRST_NAMES), _pick(rng, AMOUNTS)
    return [
        f"Hi, am I speaking with the account holder? This is {agent} from the central verification cell, nothing to worry about.",
        f"We are just reviewing an issue connected to your identity documents. It should be quick if you cooperate.",
        f"I would request you keep this conversation private for now, and stay on the line so I can guide you.",
        f"There is a small refundable cooperation amount of Rs {amt} needed to close the review from your side.",
        f"Once you send it to the account I share, everything will be cleared and returned to you shortly.",
    ]


def scam_adv_security_hold(rng):
    agent, bank = _pick(rng, FIRST_NAMES), _pick(rng, BANKS)
    return [
        f"Hello, this is {agent} from the {bank} security desk. We have placed a temporary hold on your profile.",
        f"There is an irregularity we must resolve together, and I will need you to stay with me on the call.",
        f"Please don't discuss this with branch staff or family yet; it could interfere with the security review.",
        f"To lift the hold, move your balance to the protected account I provide so it stays safe during the check.",
        f"This is only temporary and the funds return to you once the review completes.",
    ]


def scam_adv_refund_reversal(rng):
    agent, amt = _pick(rng, FIRST_NAMES), _pick(rng, AMOUNTS)
    return [
        f"Good day, this is {agent} from payments support. An amount was mistakenly credited to your account.",
        f"We need your help to reverse it quietly before the audit team flags it against you.",
        f"Please stay on the line and keep this between us so it doesn't become a formal case.",
        f"Send Rs {amt} back to the recovery account I give you and the matter is closed with no record.",
        f"If it is not returned in the next few minutes it will be treated as retained fraudulently.",
    ]


def scam_adv_kyc_expiry(rng):
    agent, amt = _pick(rng, FIRST_NAMES), _pick(rng, AMOUNTS)
    return [
        f"Hello, this is {agent} from the compliance unit. Your verification has lapsed and your account is now restricted.",
        f"I can help you restore it right now, but you will need to follow my steps exactly and stay on the call.",
        f"Kindly do not visit the branch for this, it will only delay things and complicate your file.",
        f"A small clearance fee of Rs {amt} is required to reactivate, which is adjusted back into your account.",
        f"Please transfer it to the reactivation account I am sharing so we can lift the restriction today.",
    ]


ADVERSARIAL_SCAM_BUILDERS = [
    ("adv_slowburn", scam_adv_slowburn),
    ("adv_security_hold", scam_adv_security_hold),
    ("adv_refund_reversal", scam_adv_refund_reversal),
    ("adv_kyc_expiry", scam_adv_kyc_expiry),
]


def build(n_scam, n_legit, seed, n_adv_scam=16, n_adv_legit=24):
    rng = random.Random(seed)
    calls = []

    # --- canonical scams ---
    for i in range(n_scam):
        name, builder = SCAM_BUILDERS[i % len(SCAM_BUILDERS)]
        city, lat, lon = _pick(rng, CITIES)
        calls.append({
            "session_id": f"SCAM_{i+1:03d}",
            "label": "scam",
            "scam_type": name,
            "difficulty": "positive",
            "city": city, "latitude": lat, "longitude": lon,
            "chunks": builder(rng),
        })

    # --- adversarial scams (subtle / euphemistic) ---
    for i in range(n_adv_scam):
        name, builder = ADVERSARIAL_SCAM_BUILDERS[i % len(ADVERSARIAL_SCAM_BUILDERS)]
        city, lat, lon = _pick(rng, CITIES)
        calls.append({
            "session_id": f"SCAM_ADV_{i+1:03d}",
            "label": "scam",
            "scam_type": name,
            "difficulty": "adversarial",
            "city": city, "latitude": lat, "longitude": lon,
            "chunks": builder(rng),
        })

    # --- canonical legitimate ---
    for i in range(n_legit):
        name, builder, difficulty = LEGIT_BUILDERS[i % len(LEGIT_BUILDERS)]
        city, lat, lon = _pick(rng, CITIES)
        calls.append({
            "session_id": f"LEGIT_{i+1:03d}",
            "label": "legit",
            "negative_type": name,
            "difficulty": difficulty,
            "city": city, "latitude": lat, "longitude": lon,
            "chunks": builder(rng),
        })

    # --- adversarial legitimate (keyword traps) ---
    for i in range(n_adv_legit):
        name, builder = ADVERSARIAL_LEGIT_BUILDERS[i % len(ADVERSARIAL_LEGIT_BUILDERS)]
        city, lat, lon = _pick(rng, CITIES)
        calls.append({
            "session_id": f"LEGIT_ADV_{i+1:03d}",
            "label": "legit",
            "negative_type": name,
            "difficulty": "adversarial",
            "city": city, "latitude": lat, "longitude": lon,
            "chunks": builder(rng),
        })

    rng.shuffle(calls)
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-scam", type=int, default=63)
    ap.add_argument("--n-legit", type=int, default=65)
    ap.add_argument("--n-adv-scam", type=int, default=16)
    ap.add_argument("--n-adv-legit", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "eval_transcripts.json"),
    )
    args = ap.parse_args()

    calls = build(args.n_scam, args.n_legit, args.seed,
                  args.n_adv_scam, args.n_adv_legit)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(calls, f, indent=2, ensure_ascii=False)

    n_scam = sum(1 for c in calls if c["label"] == "scam")
    n_legit = len(calls) - n_scam
    hard = sum(1 for c in calls if c.get("difficulty") == "hard")
    adv = sum(1 for c in calls if c.get("difficulty") == "adversarial")
    print(f"Wrote {len(calls)} transcripts -> {args.out}")
    print(f"  scam: {n_scam}   legit: {n_legit}")
    print(f"  hard negatives: {hard}   adversarial (both classes): {adv}")
    print(f"  seed: {args.seed} (reproducible)")


if __name__ == "__main__":
    main()

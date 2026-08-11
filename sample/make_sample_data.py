"""
make_sample_data.py — generates the tracked synthetic bank exports in sample/.

Everything here is invented: merchants, counterparties, amounts, and dates
share nothing with any real export. The output matches the REAL RAW SCHEMA
documented in sources.md (Chase: Details/Posting Date/Description/Amount/Type,
debits negative; Discover: Trans. Date/Post Date/Description/Amount/Category,
purchases positive), so the sample exercises the same two-format reconciliation,
sign normalisation, dedupe, and merchant-canonicalisation work the real data does.

Deliberately included, because a clean sample would understate the pipeline:
  * processor prefixes (SQ *, TST*, PAYPAL *), store/register numbers,
    trailing city/state, "ending in 1234" card tails, ACH WEB IDs
  * the same merchant in several raw spellings that must collapse to one
  * two overlapping pulls per account (the later pull re-exports every earlier
    row and adds a few), which is what cross-pull dedupe has to survive
  * a Balance column and card numbers, so ingest.py's scrub really runs
  * a mid-series regime change (dorm -> off-campus at 2024-08)
  * two genuine high-side anomalies in the final month

Run: .venv/bin/python sample/make_sample_data.py
"""

import csv
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingest import ingest_file  # noqa: E402  (path set above)

OUT = Path(__file__).resolve().parent
SEED = 20260810

# Coverage: Chase opens first, Discover joins ~7 weeks later, both run to the
# same partial final month — the same shape as a real pair of exports.
CHASE_START, DISCOVER_START = date(2023, 2, 14), date(2023, 4, 6)
END = date(2025, 3, 12)
# Regime change: dorm -> apartment. Deliberately placed BEFORE the anomaly
# baseline window (the 12 full months preceding the score month), so the
# baseline describes one spending regime. A regime change inside the baseline
# makes the category distributions bimodal and the detector then flags
# ordinary recurring rent as an outlier.
MOVE_OUT = date(2024, 2, 12)
PULL1_CUTOFF = date(2025, 3, 6)       # first pull stops here; second adds the rest
PULL_DATES = {"chase": ("2025-03-07", "2025-03-13"),
              "discover": ("2025-03-07", "2025-03-13")}

rng = random.Random(SEED)
rows: list[dict] = []


def add(d: date, account: str, desc: str, amount: float, kind: str,
        post_offset: int = 0):
    """amount is ALWAYS spend-positive here; per-account sign conventions are
    applied at write time (Chase flips, Discover keeps)."""
    rows.append({"date": d, "post": d + timedelta(days=post_offset),
                 "account": account, "desc": desc,
                 "amount": round(amount, 2), "kind": kind})


def jitter(base: float, pct: float = 0.28) -> float:
    return max(1.0, base * (1 + rng.uniform(-pct, pct)))


def months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def day(y: int, m: int, dd: int) -> date:
    """Clamp to month length so the 30th works in February."""
    for cand in range(dd, 0, -1):
        try:
            return date(y, m, cand)
        except ValueError:
            continue
    raise AssertionError


# --- merchant vocabularies -------------------------------------------------
# Each entry is a list of raw spellings for ONE merchant; the canonical name
# lives in categories.sample.yaml. Multiple spellings per merchant is the
# point — it is what the collapse report has to prove it can undo.
COFFEE = ["SQ *NIMBUS COFFEE #0421 PORTLAND OR",
          "SQ *NIMBUS COFFEE ROASTERS PORTLAND OR",
          "NIMBUS COFFEE 00421 PORTLAND OR"]
DINER = ["TST* CALDER DINER PORTLAND OR",
         "TST*CALDER DINER - PEARL PORTLAND OR",
         "CALDER DINER PORTLAND OR"]
NOODLE = ["SQ *HALLOW BOWL NOODLE PORTLAND OR",
          "HALLOW BOWL NOODLE BAR 0198 PORTLAND OR"]
GROCERY = ["FERNWOOD MARKET 00812 PORTLAND OR",
           "FERNWOOD MARKET #812 PORTLAND OR",
           "FERNWOOD MARKET PORTLAND OR"]
CAMPUS_DINING = ["RIVERTON U DINING HALL PORTLAND OR",
                 "RIVERTON U DINING 004 PORTLAND OR"]
CONVENIENCE = ["QUICKSTOP 2244 PORTLAND OR", "QUICKSTOP #2244 PORTLAND OR"]
TRANSIT = ["RIVERTON TRANSIT AUTH PORTLAND OR",
           "RIVERTON TRANSIT PASS PORTLAND OR"]
COACH = ["COASTLINE COACH LINES 0042 PORTLAND OR",
         "COASTLINE COACH LINES PORTLAND OR"]
BIKE = ["SQ *SPOKE + SPROCKET PORTLAND OR",
        "SPOKE AND SPROCKET CYCLES PORTLAND OR"]
INTERNET = ["PIONEER FIBER INTERNET PPD ID: 8814772"]
RENTERS_INS = ["HARBORLIGHT RENTERS INS PPD ID: 6620031"]
RIDESHARE = ["ZIPLANE RIDES HELP.ZIPLANE.COM",
             "ZIPLANE *RIDE HELP.ZIPLANE.COM"]
STREAMING = ["PP*QUILLSTREAM QUILLSTREAM.COM",
             "QUILLSTREAM MEMBERSHIP QUILLSTREAM.COM"]
GYM = ["HOLLIS ATHLETIC CO PORTLAND OR",
       "PAYPAL *HOLLISATHLE 4029357733"]
APPAREL = ["SQ *THISTLE + THREAD PORTLAND OR",
           "THISTLE AND THREAD 0067 PORTLAND OR",
           "PAYPAL *THISTLETHR 4029357733"]
BOOKSTORE = ["RIVERTON U BOOKSTORE PORTLAND OR",
             "RIVERTON U BKSTR 0012 PORTLAND OR"]
PHARMACY = ["MERIDIAN PHARMACY 0455 PORTLAND OR",
            "MERIDIAN PHARMACY #455 PORTLAND OR"]
BARBER = ["SQ *ALDER LANE BARBERS PORTLAND OR"]
HARDWARE = ["CASCADE HOME SUPPLY 118 PORTLAND OR"]
CINEMA = ["ORPHEUM SIX CINEMA PORTLAND OR"]
BOARDGAME = ["SQ *KESTREL GAMES PORTLAND OR"]
# Deliberately unknowable — these SHOULD land in Uncategorized.
OPAQUE = ["MARKETPLACE ORDER 88-4412-90 PORTLAND OR",
          "SP KESTREL RESALE STOCKPORT",
          "ATM WITHDRAWAL 004182 PORTLAND OR"]


def pick(bucket: list[str]) -> str:
    return rng.choice(bucket)


# --- income ---------------------------------------------------------------
# Work-study every other Friday; aid disbursements at semester start; a small
# side income stream. All Chase ACH credits.
d = date(2023, 2, 17)
while d <= END:
    if d >= CHASE_START:
        add(d, "chase", f"RIVERTON UNIV PAYROLL PPD ID: 9{rng.randint(100000, 999999)}",
            jitter(438.0, 0.16), "income")
    d += timedelta(days=14)

for aid_day, amt in [(date(2023, 2, 21), 3960.0), (date(2023, 9, 5), 4180.0),
                     (date(2024, 1, 16), 4180.0), (date(2024, 9, 3), 4405.0),
                     (date(2025, 1, 14), 4405.0)]:
    add(aid_day, "chase",
        f"RIVERTON UNIV STUDENT AID ACH WEB ID: 4{rng.randint(10000000, 99999999)}",
        amt, "income")

for y, m in months(date(2023, 6, 1), END):
    if rng.random() < 0.55:
        add(day(y, m, rng.randint(8, 24)), "chase",
            f"PENNYLOOM PAYOUTS ST-{rng.randint(10**7, 10**8):08X} CCD ID: 22{rng.randint(10000, 99999)}",
            jitter(96.0, 0.5), "income")

# --- housing --------------------------------------------------------------
for y, m in months(date(2023, 3, 1), END):
    on = date(y, m, 1)
    if on < MOVE_OUT:
        if m in (1, 2, 3, 4, 9, 10, 11, 12):     # dorm billed in term months
            add(day(y, m, 5), "chase", "RIVERTON U HOUSING ACH WEB ID: 4471902", 742.0, "housing")
    else:
        add(day(y, m, 1), "chase", "BRIAR CREEK APTS RENT ACH WEB ID: 5590213", 1185.0, "housing")
        add(day(y, m, 9), "chase", f"CASCADE POWER + WATER PPD ID: 77{rng.randint(1000, 9999)}",
            jitter(84.0, 0.3), "housing")
        # mid-range housing costs: without them the category is just rent and
        # two tiny bills, and any spread-based model calls the rent an outlier
        add(day(y, m, 14), "chase", pick(INTERNET), jitter(62.0, 0.06), "housing")
        add(day(y, m, 16), "chase", pick(RENTERS_INS), jitter(13.5, 0.05), "housing")
        # Household spending is continuous in real life, not six fixed
        # spikes: without mid-range mass between the small bills and the rent,
        # the category's MAD collapses and the rent scores as an anomaly every
        # single month.
        for _ in range(rng.randint(1, 3)):
            add(day(y, m, rng.randint(6, 26)), rng.choice(["chase", "discover"]),
                pick(HARDWARE), jitter(240.0, 0.9), "housing")
for y, m in months(date(2023, 3, 1), END):
    add(day(y, m, 12), "chase", f"VANTA MOBILE WIRELESS PPD ID: 33{rng.randint(1000, 9999)}",
        jitter(41.0, 0.08), "housing")

# --- education ------------------------------------------------------------
for tuition_day, amt in [(date(2023, 3, 2), 3120.0), (date(2023, 9, 12), 3260.0),
                         (date(2024, 1, 23), 3260.0), (date(2024, 9, 10), 3495.0),
                         (date(2025, 1, 21), 3495.0)]:
    add(tuition_day, "chase", "RIVERTON UNIV TUITION ACH WEB ID: 4471902", amt, "education")
for y, m in [(2023, 3), (2023, 9), (2024, 1), (2024, 9), (2025, 1)]:
    add(day(y, m, rng.randint(14, 26)), "discover", pick(BOOKSTORE),
        jitter(132.0, 0.4), "education")

# --- everyday spending, with the regime change ----------------------------
d = max(CHASE_START, date(2023, 2, 14))
while d <= END:
    pre = d < MOVE_OUT
    disc_ok = d >= DISCOVER_START
    acct = "discover" if disc_ok and rng.random() < 0.52 else "chase"

    if pre:
        # dorm life: meal plan swipes, campus coffee, occasional takeout
        if rng.random() < 0.55:
            add(d, acct, pick(CAMPUS_DINING), jitter(11.4), "food")
        if rng.random() < 0.42:
            add(d, acct, pick(COFFEE), jitter(5.6), "food")
        if rng.random() < 0.20:
            add(d, acct, pick(DINER), jitter(19.5), "food")
        if rng.random() < 0.14:
            add(d, acct, pick(CONVENIENCE), jitter(7.2), "food")
    else:
        # off campus: real groceries, more cooking, fewer dining-hall swipes
        if rng.random() < 0.34:
            add(d, acct, pick(GROCERY), jitter(46.0), "food")
        if rng.random() < 0.30:
            add(d, acct, pick(COFFEE), jitter(6.1), "food")
        if rng.random() < 0.26:
            add(d, acct, pick(NOODLE), jitter(16.8), "food")
        if rng.random() < 0.16:
            add(d, acct, pick(DINER), jitter(23.0), "food")

    # Transportation is pass-first (below); single fares are the occasional
    # out-of-zone trip. Keeping them rare avoids a degenerate one-value
    # category whose MAD collapses and flags every larger fare as an anomaly.
    if rng.random() < 0.04:
        add(d, acct, pick(TRANSIT), jitter(3.1, 0.45), "transport")
    if rng.random() < 0.07:
        add(d, acct, pick(RIDESHARE), jitter(15.5, 0.55), "transport")
    if rng.random() < 0.028:
        add(d, acct, pick(COACH), jitter(38.0, 0.4), "transport")   # trips home
    if rng.random() < 0.022:
        add(d, acct, pick(BIKE), jitter(58.0, 0.6), "transport")    # repairs/parts
    if rng.random() < 0.05:
        add(d, acct, pick(APPAREL), jitter(38.0), "apparel")
    if rng.random() < 0.045:
        add(d, acct, pick(PHARMACY), jitter(18.0), "personal")
    if rng.random() < 0.03:
        add(d, acct, pick(CINEMA), jitter(15.5), "entertainment")
    if rng.random() < 0.025:
        add(d, acct, pick(BOARDGAME), jitter(24.0), "entertainment")
    if rng.random() < 0.02:
        add(d, acct, pick(BARBER), jitter(27.0), "personal")
    if not pre and rng.random() < 0.02:
        add(d, acct, pick(HARDWARE), jitter(31.0), "housing")
    if rng.random() < 0.022:
        add(d, acct, pick(OPAQUE), jitter(35.0), "opaque")
    d += timedelta(days=1)

for y, m in months(date(2023, 3, 1), END):
    add(day(y, m, 18), "discover", pick(STREAMING), 12.99, "entertainment")
    add(day(y, m, 21), "chase", pick(TRANSIT).replace("AUTH", "PASS"),
        jitter(58.0, 0.04), "transport")      # monthly student transit pass
    if date(y, m, 1) >= MOVE_OUT:
        add(day(y, m, 6), "discover", pick(GYM), 29.0, "personal")

# --- peer payments, both directions ---------------------------------------
PEERS_OUT = ["DEVON ASHFORD", "MARISOL QUAY", "TOBIN REEVES"]
PEERS_IN = ["MARISOL QUAY", "PRIYA VANTERPOOL", "DEVON ASHFORD"]
for y, m in months(date(2023, 5, 1), END):
    for _ in range(rng.randint(1, 3)):
        who = rng.choice(PEERS_OUT)
        add(day(y, m, rng.randint(3, 27)), "chase",
            f"Zelle payment to {who} {rng.randint(10**10, 10**11 - 1)}",
            jitter(34.0, 0.6), "peer_out")
    for _ in range(rng.randint(0, 2)):
        who = rng.choice(PEERS_IN)
        add(day(y, m, rng.randint(3, 27)), "chase",
            f"Zelle payment from {who} JPM{rng.randint(10**8, 10**9 - 1)}",
            jitter(41.0, 0.6), "peer_in")
# Rent split from the same housemate every month after the move — the kind of
# row that needs a hand-tag, so it exercises transaction_overrides.
for y, m in months(date(2024, 9, 1), date(2025, 2, 28)):
    add(day(y, m, 3), "chase",
        f"Zelle payment from TOBIN REEVES JPM{rng.randint(10**8, 10**9 - 1)}",
        395.0, "peer_in")

# --- card payments + transfers (must be excluded from spend) --------------
for y, m in months(date(2023, 5, 1), END):
    amt = jitter(190.0, 0.5)
    add(day(y, m, 22), "chase", "DISCOVER E-PAYMENT ACH WEB ID: 5100109", amt, "cardpay_chase")
    add(day(y, m, 23), "discover", "INTERNET PAYMENT - THANK YOU", amt, "cardpay_discover")
for y, m in months(date(2023, 6, 1), END):
    if rng.random() < 0.4:
        add(day(y, m, rng.randint(10, 20)), "chase",
            "Online Transfer to CHK ...4022 transaction#: 91824771", jitter(200.0, 0.6),
            "transfer")

# --- refunds (negative spend that must net, not vanish) -------------------
for y, m in [(2023, 10), (2024, 4), (2024, 11), (2025, 2)]:
    add(day(y, m, rng.randint(8, 22)), "discover", pick(APPAREL), -jitter(42.0, 0.3), "refund")

# --- seeded anomalies: two genuine high-side outliers in the final month --
add(date(2025, 3, 4), "chase", "MERIDIAN DENTAL SURGERY ACH WEB ID: 6620744",
    2940.0, "healthcare_anomaly")
add(date(2025, 3, 10), "discover", "HELIOGRAPH LAPTOPS 0091 PORTLAND OR",
    1815.0, "electronics_anomaly")
# ...and a mundane final month around them, so they stand out against context
for dd in range(1, 13):
    on = date(2025, 3, dd)
    if rng.random() < 0.6:
        add(on, rng.choice(["chase", "discover"]), pick(GROCERY), jitter(44.0), "food")
    if rng.random() < 0.5:
        add(on, rng.choice(["chase", "discover"]), pick(COFFEE), jitter(6.0), "food")
    if rng.random() < 0.3:
        add(on, rng.choice(["chase", "discover"]), pick(NOODLE), jitter(17.0), "food")

# ---------------------------------------------------------------------------
# Writing: apply each bank's own schema, sign convention, and column set.
# ---------------------------------------------------------------------------
CHASE_TYPE = {
    "income": "ACH_CREDIT", "housing": "ACH_DEBIT", "education": "ACH_DEBIT",
    "peer_out": "QUICKPAY_DEBIT", "peer_in": "QUICKPAY_CREDIT",
    "cardpay_chase": "ACH_DEBIT", "transfer": "ACCT_XFER",
    "healthcare_anomaly": "ACH_DEBIT",
}
DISCOVER_CATEGORY = {
    "food": "Restaurants", "transport": "Gasoline", "apparel": "Merchandise",
    "personal": "Services", "entertainment": "Travel/ Entertainment",
    "education": "Education", "opaque": "Merchandise",
    "cardpay_discover": "Payments and Credits", "refund": "Payments and Credits",
    "electronics_anomaly": "Merchandise",
}
CREDIT_KINDS = {"income", "peer_in", "refund"}


def chase_rows(cutoff: date) -> list[list[str]]:
    out = []
    for r in sorted([r for r in rows if r["account"] == "chase"
                     and CHASE_START <= r["date"] <= cutoff],
                    key=lambda r: (r["date"], r["desc"])):
        credit = r["kind"] in CREDIT_KINDS
        signed = r["amount"] if credit else -r["amount"]
        if r["kind"] == "refund":
            signed = abs(r["amount"])
        details = "CREDIT" if signed > 0 else "DEBIT"
        typ = CHASE_TYPE.get(r["kind"], "DEBIT_CARD")
        out.append([details, r["date"].strftime("%m/%d/%Y"), r["desc"],
                    f"{signed:.2f}", typ, f"{rng.uniform(180, 5200):.2f}"])
    return out


def discover_rows(cutoff: date) -> list[list[str]]:
    out = []
    for r in sorted([r for r in rows if r["account"] == "discover"
                     and DISCOVER_START <= r["date"] <= cutoff],
                    key=lambda r: (r["date"], r["desc"])):
        # Discover: purchases POSITIVE, credits/payments NEGATIVE (opposite Chase)
        signed = -abs(r["amount"]) if r["kind"] in ("cardpay_discover",) else r["amount"]
        cat = DISCOVER_CATEGORY.get(r["kind"], "Merchandise")
        out.append([r["date"].strftime("%m/%d/%Y"), r["post"].strftime("%m/%d/%Y"),
                    r["desc"], f"{signed:.2f}", cat])
    return out


CHASE_HEADER = ["Details", "Posting Date", "Description", "Amount", "Type", "Balance"]
DISCOVER_HEADER = ["Trans. Date", "Post Date", "Description", "Amount", "Category"]


def write_pull(header: list[str], body: list[list[str]], source: str, pull_date: str):
    """Write a bank-shaped file, then run it through the project's own
    ingest.py scrub (drops Balance, redacts card tails/WEB IDs) into sample/."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as tmp:
        w = csv.writer(tmp)
        w.writerow(header)
        w.writerows(body)
        tmp_path = Path(tmp.name)
    out = ingest_file(tmp_path, source, out_dir=OUT, pull_date=pull_date)
    tmp_path.unlink()
    return out


def main():
    p1, p2 = PULL_DATES["chase"]
    c1 = chase_rows(PULL1_CUTOFF)
    c2 = chase_rows(END)
    for row in c2[::9]:
        row[2] = row[2] + "APPLE PAY ENDING IN 4417"
    for row in c1[::9]:
        row[2] = row[2] + "APPLE PAY ENDING IN 4417"
    write_pull(CHASE_HEADER, c1, "chase", p1)
    write_pull(CHASE_HEADER, c2, "chase", p2)

    q1, q2 = PULL_DATES["discover"]
    d1 = discover_rows(PULL1_CUTOFF)
    d2 = discover_rows(END)
    write_pull(DISCOVER_HEADER, d1, "discover", q1)
    write_pull(DISCOVER_HEADER, d2, "discover", q2)

    print(f"chase pulls: {len(c1)} then {len(c2)} rows "
          f"({len(c2) - len(c1)} new in the second)")
    print(f"discover pulls: {len(d1)} then {len(d2)} rows "
          f"({len(d2) - len(d1)} new in the second)")
    written = [r for r in rows
               if (r["account"] == "chase" and CHASE_START <= r["date"] <= END)
               or (r["account"] == "discover" and DISCOVER_START <= r["date"] <= END)]
    print(f"total synthetic transactions written: {len(written)}; "
          f"{min(r['date'] for r in written)} .. {max(r['date'] for r in written)}")


if __name__ == "__main__":
    main()

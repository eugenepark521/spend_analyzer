"""
normalize.py — shared merchant normalisation + rule matching for the clean
(task 13, clean.py) and categorise (categorize.py) stages.

Both stages resolve every transaction through resolve(), driven entirely by
categories.yaml, so the canonical merchant used for deduping in clean.py and
the category assigned in categorize.py can never drift apart.

Resolution order (documented in categories.yaml):
  transfers -> income -> transaction overrides -> peer payments
  -> merchant rules -> Discover fallback -> Uncategorized.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).parent / "categories.yaml"

# Junk stripped from descriptions before any matching: processor/reference IDs,
# scrub artifacts, FX conversion tails, trailing MM/DD dates, phone numbers.
_JUNK = [
    re.compile(r"APPLE PAY ENDING IN \[(?:XXXX|REDACTED-NUM)\]", re.I),
    re.compile(r"ENDING IN \[(?:XXXX|REDACTED-NUM)\]", re.I),
    re.compile(r"\[REDACTED-NUM\]"),
    re.compile(r"\d+(?:\.\d+)?\s*@\s*[\d.]+\s*JPY.*", re.I),        # Discover FX tail
    re.compile(r"YEN\s+\d+\s*X\s*[\d.]+\s*\(EXCHG RTE\)", re.I),    # Chase FX tail
    re.compile(r"WEB ID:?\s*\[REDACTED\]\S*", re.I),
    re.compile(r"(?:PPD|CCD) ID:\s*\S+", re.I),
    re.compile(r"CLAIMID:?\s*\S*", re.I),
    re.compile(r"TRANSACTION#:\s*\S+", re.I),
    re.compile(r"\bST-[A-Z0-9]{8,}\b", re.I),                       # Stripe payout refs
    re.compile(r"\b\d{2}/\d{2}[A-Z]*\b"),                           # trailing dates, incl. glued "06/26KATSUSHIK"
    re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),                           # phone numbers
    re.compile(r"\b\d{3}-\d{7}\b"),
    re.compile(r"\b\d{5,}[A-Z]{0,2}\b"),                            # store/register/reference digit runs
]

_PREFIXES = re.compile(
    r"^(REVERSAL:\s*)?(SQ \*|SQ |TST\*\s?|DD \*|PP\*|SP |SPO\*|PY \*|CTLP\*|"
    r"SNACK\*\s?|CASH APP\*|POPPIN\*\s?|PAYPAL \*|ETSY\.COM\*)",
    re.I,
)

# Trailing location tokens for the generic fallback (rule-matched merchants
# never reach this). US states seen in the data + country/ward tokens.
_LOC_TOKENS = {
    "CA", "NY", "TX", "TN", "WA", "PA", "GA", "KS", "NV", "NJ", "IL", "FL",
    "MD", "OH", "MN", "DE", "BC", "CO", "JPN", "KOR", "FRA",
    "GARDEN", "GROVE", "SEAL", "BEACH", "DAVIS", "IRVINE", "WESTMINSTER",
    "SACRAMENTO", "SAN", "FRANCISCO", "FRANCISCOCA", "LOS", "ANGELES",
    "HUNTINGTON", "HUNTINGTN", "BCH", "BCHCA", "BE", "BECA", "BUENA", "PARK",
    "STANTON", "CYPRESS", "WOODLAND", "VACAVILLE", "FULLERTON", "COSTA",
    "MESA", "SANTA", "ANA", "FE", "SPRNCA", "VISALIA", "LEBEC", "CASTROVILLE",
    "MILL", "VALLEY", "AUBURN", "STOCKTON", "BERKELEY", "ARTESIA",
    "VICTORVILLE", "SEGUNDO", "EL", "LONG", "PLAINVIEW", "WILMINGTON", "NEW",
    "YORK", "CITY", "CITYNY", "GROVEPORT", "COLUMBUS", "ADDISON", "AUSTIN",
    "ATLANTA", "STOCKPORT", "COURBEVOIE", "TOKYO", "SEOUL", "VANCOUV", "NORTH",
    "SHIBUYA-KU", "SHINJUKU-KU", "SETAGAYA-KU", "MINATO-KU", "CHIYODA-KU",
    "CHUO-KU", "KATSUSHIKA-KU", "KATSUSHIKA-KUJPN", "ARAKAWA-KU", "ADACHI-KU",
    "URAYASU-SHI", "SUITA-SHI", "MUSASHINO-SHI", "MUSASHINO-SHIJPN",
    "FUJIYOSHIDA-SJPN", "MIHAMA-KU", "CHIJPN", "HIGASHIHIROSHJPN",
    "SHIMOKITAZAWA", "KABUKICHO", "OMOTESANDO", "AOYAMA",
}

_ZELLE = re.compile(r"ZELLE PAYMENT (TO|FROM)\s+(.*)", re.I)


def strip_junk(desc: str) -> str:
    """Uppercased description with IDs/FX/date junk removed. Rule-match target."""
    s = str(desc)
    for pat in _JUNK:
        s = pat.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()


def generic_merchant(cleaned: str) -> str:
    """Fallback canonical merchant for rows no rule matched: strip processor
    prefixes, trailing city/state tokens, stray punctuation."""
    s = _PREFIXES.sub("", cleaned).strip()
    tokens = s.split()
    while len(tokens) > 1 and tokens[-1].strip(".,#*") in _LOC_TOKENS:
        tokens.pop()
    s = " ".join(tokens)
    s = re.sub(r"[#*]+\w*$", "", s).strip(" .,*#-")
    return s or cleaned


@dataclass
class Resolution:
    merchant: str
    category: str          # BLS category, Transfer, Income, or Uncategorized
    is_peer: bool = False
    peer_direction: str = ""   # outgoing / incoming / ambiguous
    counterparty: str = ""
    matched_rule: str = ""     # which yaml section decided it (for audit)


class Resolver:
    def __init__(self, rules_path: Path = RULES_PATH):
        raw = yaml.safe_load(rules_path.read_text())
        # categories.local.yaml (untracked, gitignored) holds personal matching
        # rules — patterns containing real counterparty names and exact
        # (date, amount) hand-tags — so the tracked yaml stays free of
        # identifiable data. Local list sections are appended after the
        # tracked ones; without the file the pipeline still runs, but those
        # rows fall back to the impersonal defaults (peer Miscellaneous).
        local_path = rules_path.with_name("categories.local.yaml")
        if local_path.exists():
            local = yaml.safe_load(local_path.read_text()) or {}
            for key in ("transfer_patterns", "income_patterns",
                        "transaction_overrides", "merchants"):
                if key in local:
                    raw[key] = list(raw.get(key, [])) + list(local[key])
            if "peer" in local:
                raw["peer"]["overrides"] = (
                    list(raw["peer"].get("overrides", []))
                    + list(local["peer"].get("overrides", [])))
        self.bls = list(raw["bls_categories"])
        self.admin = list(raw["admin_categories"])
        self.transfer = [re.compile(p, re.I) for p in raw["transfer_patterns"]]
        self.income = [re.compile(p, re.I) for p in raw["income_patterns"]]
        self.tx_overrides = [
            (str(o["date"]), float(o["amount"]), o["category"])
            for o in raw.get("transaction_overrides", [])
        ]
        self.override_hits = [0] * len(self.tx_overrides)
        peer = raw["peer"]
        self.peer_out = set(peer["chase_types_outgoing"])
        self.peer_in = set(peer["chase_types_incoming"])
        self.peer_desc = [re.compile(p, re.I) for p in peer["description_patterns"]]
        self.peer_default = peer["default_category"]
        self.peer_overrides = [
            (re.compile(o["match"], re.I), o["category"]) for o in peer["overrides"]
        ]
        self.merchants = [
            (re.compile(m["match"], re.I), m["merchant"], m["category"])
            for m in raw["merchants"]
        ]
        self.discover_fallback = dict(raw["discover_fallback"])
        # Every category a rule can assign must be a known BLS/admin category.
        valid = set(self.bls) | set(self.admin)
        for _, m, c in self.merchants:
            assert c in valid, f"rule for {m!r} assigns unknown category {c!r}"
        assert self.peer_default in valid
        assert set(self.discover_fallback.values()) <= valid
        for d, a, c in self.tx_overrides:
            assert c in valid, f"override for ({d}, {a}) assigns unknown category {c!r}"

    def _peer_details(self, description: str, cleaned: str, source: str,
                      source_type: str, raw_amount: float) -> Resolution:
        # Counterparty comes from the RAW description: junk-stripping removes
        # digit runs, which would eat phone-number counterparties and surnames.
        raw_up = re.sub(r"\s+", " ", str(description).upper()).strip()
        m = _ZELLE.search(raw_up)
        if m:
            words = m.group(2).split()
            # drop one trailing bank-reference token (JPM99…, BAC…, WFCT…,
            # 11-digit refs) but keep a lone phone-number counterparty
            if len(words) > 1 and re.fullmatch(
                    r"\d{6,}|[A-Z]*\d[A-Z0-9]{5,}|(?:BAC|JPM|WFC|COF|USB)[A-Z0-9]{6,}",
                    words[-1]):
                words = words[:-1]
            counterparty = " ".join(words)
            desc_dir = "outgoing" if m.group(1).upper() == "TO" else "incoming"
        elif cleaned.startswith("VENMO"):
            counterparty = re.sub(r"^VENMO\s*\*?", "", raw_up)
            counterparty = re.sub(r"VISA DIRECT.*", "", counterparty).strip()
            desc_dir = ""
        elif cleaned.startswith("APPLE CASH"):
            counterparty = "APPLE CASH"
            desc_dir = ""
        elif cleaned.startswith("WISE US INC"):
            counterparty = "WISE"
            desc_dir = ""
        else:
            counterparty, desc_dir = generic_merchant(cleaned), ""

        # Direction: source sign is authoritative, per that source's own
        # convention (Chase raw: negative = money out; Discover raw: positive =
        # money out). Cross-check against the description's to/from when
        # present; a conflict means we do NOT guess.
        money_out = raw_amount < 0 if source == "chase" else raw_amount > 0
        sign_dir = "outgoing" if money_out else "incoming"
        if source == "chase" and source_type in self.peer_out and sign_dir != "outgoing":
            direction = "ambiguous"
        elif source == "chase" and source_type in self.peer_in and sign_dir != "incoming":
            direction = "ambiguous"
        elif desc_dir and desc_dir != sign_dir:
            direction = "ambiguous"
        else:
            direction = sign_dir

        if direction == "ambiguous":
            category = "Uncategorized"
        else:
            category = self.peer_default
            for pat, cat in self.peer_overrides:
                if pat.search(cleaned):
                    category = cat
                    break
        merchant = f"ZELLE {counterparty}" if m else counterparty
        return Resolution(merchant=merchant, category=category, is_peer=True,
                          peer_direction=direction, counterparty=counterparty,
                          matched_rule="peer")

    def resolve(self, description: str, source: str, source_type: str,
                raw_amount: float, date: str) -> Resolution:
        """source: 'chase'|'discover'; source_type: Chase Type / Discover
        Category; raw_amount: amount in the source's own sign convention;
        date: normalised YYYY-MM-DD transaction date."""
        res = self._resolve(description, source, source_type, raw_amount, date)
        if not str(res.merchant).strip():
            # an empty merchant round-trips through CSV as NaN (crashing later
            # string slicing) and degrades the dedupe key
            res.merchant = "(UNKNOWN MERCHANT)"
        return res

    def assert_overrides_hit_once(self):
        """Call after resolving one full pass over the deduped dataset: each
        transaction_override must have matched exactly one row. 0 means the
        override is stale; >1 means (date, |amount|) collided with an
        unrelated row, which was silently force-categorized."""
        for (d, a, c), n in zip(self.tx_overrides, self.override_hits):
            assert n == 1, (f"transaction_override ({d}, {a}, {c}) matched "
                            f"{n} rows — expected exactly 1")

    def _resolve(self, description: str, source: str, source_type: str,
                 raw_amount: float, date: str) -> Resolution:
        cleaned = strip_junk(description)

        for pat in self.transfer:
            if pat.search(cleaned):
                return Resolution(generic_merchant(cleaned), "Transfer",
                                  matched_rule="transfer")
        if source == "chase" and source_type == "ACCT_XFER":
            return Resolution(generic_merchant(cleaned), "Transfer",
                              matched_rule="transfer")

        for pat in self.income:
            if pat.search(cleaned):
                return Resolution(generic_merchant(cleaned), "Income",
                                  matched_rule="income")

        is_peer_row = (source == "chase" and source_type in (self.peer_out | self.peer_in)) or \
            any(p.search(cleaned) for p in self.peer_desc)

        for i, (o_date, o_amount, o_cat) in enumerate(self.tx_overrides):
            if date == o_date and abs(abs(raw_amount) - o_amount) < 0.005:
                self.override_hits[i] += 1
                # Category is forced, but peer rows keep merchant/counterparty
                # so dedupe keys and zelle_review.csv are unaffected.
                if is_peer_row:
                    res = self._peer_details(description, cleaned, source,
                                             source_type, raw_amount)
                    res.category = o_cat
                else:
                    res = Resolution(generic_merchant(cleaned), o_cat)
                res.matched_rule = "transaction_override"
                return res

        if is_peer_row:
            return self._peer_details(description, cleaned, source, source_type,
                                      raw_amount)

        for pat, merchant, category in self.merchants:
            if pat.search(cleaned):
                return Resolution(merchant, category, matched_rule="merchant")

        if source == "discover" and source_type in self.discover_fallback:
            return Resolution(generic_merchant(cleaned),
                              self.discover_fallback[source_type],
                              matched_rule="discover_fallback")

        return Resolution(generic_merchant(cleaned), "Uncategorized",
                          matched_rule="none")

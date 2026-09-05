"""Auto-discovery of ETFs to supplement the hand-curated universe.

`core/universe.py` lists funds by hand. This module widens the net using
yfinance's screener (`yf.screen`, available since ~1.2) to pull the largest US
ETFs, filter out the funds that don't belong in a retirement comparison
(leveraged/inverse, single-stock, tiny), and slot the survivors into the same
asset classes `universe.py` already defines.

Two things make this only *supplement* the curated lists rather than replace
them:

  1. Yahoo's Morningstar-style ``category`` is the classifier, and it's only
     trustworthy for some classes. It can't tell a total-market fund from a
     large-cap one (both are "Large Blend"), and it mislabels treasury maturity
     (it calls the 7-10yr IEF "Long Government"). So the ambiguous style boxes
     are resolved by a name heuristic, and the classes where category is
     unreliable (treasury maturities, T-bills, gold) are left curated-only —
     see ``UNRELIABLE_CLASSES``.

  2. Discovery degrades gracefully: if the screener is unreachable or errors,
     ``discover_etfs`` returns [] and the build proceeds with the curated
     universe alone.

The build pipeline fetches each discovered ticker once (same as a curated one),
reads its ``category`` from the ``info`` it already pulls, and calls
``classify`` to decide which class it joins.
"""

from __future__ import annotations

import logging
import re

import yfinance as yf

log = logging.getLogger("discovery")

# Discovered ETFs below this net-asset floor are dropped — a retirement fund
# finder shouldn't surface micro-cap niche products. Curated funds bypass this.
MIN_AUM = 250_000_000

# yfinance predefined ETF screens to draw candidates from. Each is paginated
# (250/page) and results are unioned + deduped. They overlap heavily; that's
# fine — we keep the largest net-assets figure seen for each symbol.
SCREENS = ("top_etfs_us", "top_performing_etfs", "bond_etfs")

# Names that mark a fund as outside the retirement-comparison remit. Matched
# case-insensitively as whole words where it matters, so "Bull" the word is
# caught but "Bullion" is not, and "2x"/"3x"/"-1x" leverage tags are caught.
# Two groups:
#   - leverage/derivative/hedged sleeves (structurally not a plain long fund);
#   - active/thematic sleeves that Morningstar files under a style box (e.g.
#     ARK Innovation shows as "Mid-Cap Growth") but don't belong beside broad
#     index funds in a retirement comparison.
_EXCLUDE_NAME_RE = re.compile(
    r"\b(leveraged|inverse|ultra(?:pro|short)?|ultra|enhanced|"
    r"[23]x|-?1x|daily|bull|bear|covered\s*call|buffer(?:ed)?|"
    r"managed|target|option\s*income|premium\s*income|hedged\s*equity|"
    r"innovation|disrupt(?:ive|ion)?|thematic|next[-\s]?gen(?:eration)?|"
    r"blockchain|crypto|bitcoin|metaverse|robotics|cannabis|"
    r"artificial\s*intelligence|ipo|spac|ark)\b"
    r"|\b\d(?:\.\d)?x\b",
    re.IGNORECASE,
)

# Funds no name keyword catches but that are miscategorized thematic/active
# sleeves — kept tiny and explicit. (FPX tracks a recent-IPO index yet Yahoo
# files it as "Mid-Cap Growth".)
_DENYLIST = frozenset({"FPX"})

# Yahoo category -> asset-class id, for the categories that map cleanly and
# unambiguously to one of universe.py's classes.
CATEGORY_TO_CLASS: dict[str, str] = {
    "Large Value": "large-cap-value",
    "Mid-Cap Value": "mid-cap-value",
    "Mid-Cap Growth": "mid-cap-growth",
    "Small Value": "small-cap-value",
    "Small Growth": "small-cap-growth",
    "Diversified Emerging Mkts": "emerging-markets",
    "Intermediate Core Bond": "total-bond",
    "Intermediate Core-Plus Bond": "total-bond",
    "Corporate Bond": "corp-bonds",
    "Long-Term Bond": "corp-bonds",
    "Inflation-Protected Bond": "tips",
    "Real Estate": "reit",
    "Global Real Estate": "reit",
}

# Categories that DON'T get auto-classified, and why:
#   - "Large Blend"        -> ambiguous (total-market vs large-cap); handled by
#                             _large_blend_class() name heuristic instead.
#   - "Foreign Large *"    -> developed vs total-international; handled by
#                             _foreign_class() name heuristic instead.
#   - "Large Growth"       -> the tool has no large-cap-growth class by design.
#   - "*Government*"       -> Yahoo mislabels treasury maturity; curated-only.
#   - "Ultrashort/Money*"  -> broader than the T-bill class; curated-only.
#   - "Commodities*"       -> broader than the gold-bullion class; curated-only.
# Anything not mapped and not handled by a heuristic below is simply skipped.

# Classes never auto-populated (category unreliable or class is a narrow subset
# of the category). Kept exactly as hand-listed in universe.py.
UNRELIABLE_CLASSES = frozenset({"lt-treasury", "interm-treasury", "st-tbills", "gold"})

# Name signals that a broad international fund is *total* (developed + emerging)
# rather than developed-only.
_TOTAL_INTL_RE = re.compile(
    r"total\s+international|all[-\s]?world\s+ex|all[-\s]?country\s+world\s+ex|"
    r"acwi\s*ex|world\s+ex[-\s]?u\.?s|ex[-\s]?u\.?s\.?a?\b|"
    r"all\s+international\s+markets|total\s+world\s+ex",
    re.IGNORECASE,
)

# Name signals a US equity fund covers the whole market, not just large caps.
_TOTAL_MARKET_RE = re.compile(
    r"total\s+(?:stock\s+)?market|total\s+us|broad\s+market|whole\s+market|"
    r"total\s+market",
    re.IGNORECASE,
)


def _large_blend_class(name: str) -> str:
    """'Large Blend' -> total-market-us if the name says so, else large-cap-blend."""
    return "total-market-us" if _TOTAL_MARKET_RE.search(name or "") else "large-cap-blend"


def _foreign_class(name: str) -> str:
    """Any 'Foreign Large *' -> total-international if the name signals a
    total (ex-US, all-world) mandate, else intl-developed."""
    return "total-international" if _TOTAL_INTL_RE.search(name or "") else "intl-developed"


def classify(category: str | None, name: str | None) -> str | None:
    """Asset-class id for a discovered ETF, or None to skip it."""
    if not category:
        return None
    cat = category.strip()
    if cat in CATEGORY_TO_CLASS:
        return CATEGORY_TO_CLASS[cat]
    if cat == "Large Blend":
        return _large_blend_class(name or "")
    if cat.startswith("Foreign Large"):
        return _foreign_class(name or "")
    return None


def _keep_candidate(symbol: str, name: str | None, aum: float | None) -> bool:
    if symbol in _DENYLIST:
        return False
    if aum is None or aum < MIN_AUM:
        return False
    if name and _EXCLUDE_NAME_RE.search(name):
        return False
    return True


def discover_etfs(limit: int = 300, delay: float = 0.0) -> list[dict]:
    """Return up to ``limit`` candidate ETFs (largest by net assets) as
    ``[{"symbol", "name", "aum"}]``. Never raises — returns [] on failure so the
    build can proceed with the curated universe alone.
    """
    if limit <= 0:
        return []

    candidates: dict[str, dict] = {}
    for screen in SCREENS:
        offset = 0
        for _page in range(8):  # hard cap: 8 pages * 250 = 2000 per screen
            try:
                res = yf.screen(screen, count=250, offset=offset)
            except Exception as e:
                log.warning("  screen %s (offset %d) failed: %r", screen, offset, e)
                break
            quotes = (res or {}).get("quotes") or []
            if not quotes:
                break
            for q in quotes:
                sym = (q.get("symbol") or "").upper()
                if not sym or (q.get("quoteType") or "").upper() != "ETF":
                    continue
                name = q.get("longName") or q.get("shortName") or sym
                aum = q.get("netAssets")
                if not _keep_candidate(sym, name, aum):
                    continue
                prev = candidates.get(sym)
                if prev is None or (aum or 0) > (prev.get("aum") or 0):
                    candidates[sym] = {"symbol": sym, "name": name, "aum": aum}
            total = (res or {}).get("total") or 0
            offset += 250
            if offset >= total:
                break

    ranked = sorted(candidates.values(), key=lambda c: c.get("aum") or 0, reverse=True)
    return ranked[:limit]

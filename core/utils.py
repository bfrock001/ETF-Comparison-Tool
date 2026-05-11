"""Date and period helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta


PRESET_DAYS = {
    "1Y": 365,
    "3Y": 365 * 3,
    "5Y": 365 * 5,
    "10Y": 365 * 10,
}


def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d").date()


def resolve_period(
    period: str | None,
    custom_start: str | None,
    custom_end: str | None,
) -> tuple[date, date]:
    end = _parse_iso(custom_end) or date.today()
    start = _parse_iso(custom_start)
    if start:
        return start, end

    period_key = (period or "").upper().strip()
    if period_key == "YTD":
        return date(end.year, 1, 1), end
    if period_key in PRESET_DAYS:
        return end - timedelta(days=PRESET_DAYS[period_key]), end

    return end - timedelta(days=365), end


def find_common_start(
    inceptions: dict[str, date],
    requested_start: date,
) -> tuple[date, str | None]:
    if not inceptions:
        return requested_start, None

    latest_inception = max(inceptions.values())
    if latest_inception <= requested_start:
        return requested_start, None

    limiting = [t for t, d in inceptions.items() if d == latest_inception]
    names = ", ".join(limiting)
    warning = (
        f"{names} data starts {latest_inception.isoformat()}, "
        f"limiting period to common start."
    )
    return latest_inception, warning

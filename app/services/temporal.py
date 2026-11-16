from datetime import date, timedelta
import numpy as np

_SERIES_FIELDS = (
    ("ndvi", "mean_ndvi"),
    ("ndwi", "mean_ndwi"),
    ("mndwi", "mean_mndwi"),
    ("ndmi", "mean_ndmi"),
    ("nbr", "mean_nbr"),
    ("bsi", "mean_bsi"),
    ("sar", "mean_sar_cross_ratio"),
)


def parse_iso_interval(date_range: str) -> tuple[date, date]:
    parts = date_range.split("/")
    if len(parts) != 2:
        raise ValueError("Date range must be ISO 8601 interval start/end.")
    return date.fromisoformat(parts[0].strip()), date.fromisoformat(parts[1].strip())


def period_key(day: date, granularity: str) -> str:
    if granularity == "weekly":
        iso = day.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if granularity == "yearly":
        return f"{day.year}"
    return f"{day.year}-{day.month:02d}"


def period_buckets(
    start: date, end: date, granularity: str
) -> list[tuple[date, date, str]]:
    if end < start:
        raise ValueError("Date range end must not precede its start.")
    if granularity == "yearly":
        return [
            (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)), str(year))
            for year in range(start.year, end.year + 1)
        ]
    if granularity == "weekly":
        buckets: list[tuple[date, date, str]] = []
        cursor = start - timedelta(days=start.weekday())
        while cursor <= end:
            close = cursor + timedelta(days=6)
            buckets.append(
                (max(cursor, start), min(close, end), period_key(close, "weekly"))
            )
            cursor = close + timedelta(days=1)
        return buckets
    if granularity != "monthly":
        raise ValueError(f"Unsupported granularity: {granularity}")
    buckets = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
        close = next_month - timedelta(days=1)
        buckets.append(
            (max(cursor, start), min(close, end), period_key(cursor, "monthly"))
        )
        cursor = next_month
    return buckets


def seasonal_window(year: int, composite_season: str) -> tuple[str, str]:
    parts = composite_season.split("/")
    if len(parts) != 2:
        raise ValueError("Composite season must be MM-DD/MM-DD.")
    return f"{year}-{parts[0].strip()}", f"{year}-{parts[1].strip()}"


def aggregate_observations(
    observations: list[dict], granularity: str = "monthly"
) -> list[dict]:
    buckets: dict[str, dict[str, list[float]]] = {}
    for obs in observations:
        raw = obs.get("datetime") or ""
        try:
            day = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        key = period_key(day, granularity)
        bucket = buckets.setdefault(key, {field: [] for field, _ in _SERIES_FIELDS})
        for field, column in _SERIES_FIELDS:
            value = obs.get(column)
            if value is not None:
                bucket[field].append(float(value))

    series: list[dict] = []
    for key in sorted(buckets):
        bucket = buckets[key]
        series.append(
            {
                "period": key,
                **{
                    field: round(float(np.mean(bucket[field])), 4)
                    if bucket[field]
                    else None
                    for field, _ in _SERIES_FIELDS
                },
            }
        )
    return series


def apply_dnbr_baseline(series: list[dict]) -> list[dict]:
    ordered = sorted(series, key=lambda row: row.get("period") or "")
    baseline = next(
        (float(row["nbr"]) for row in ordered if row.get("nbr") is not None), None
    )
    for row in ordered:
        nbr = row.get("nbr")
        row["dnbr"] = (
            None if baseline is None or nbr is None else round(baseline - float(nbr), 4)
        )
    return ordered


def series_from_live(
    observations: list[dict], granularity: str = "monthly"
) -> list[dict]:
    return aggregate_observations(observations, granularity)

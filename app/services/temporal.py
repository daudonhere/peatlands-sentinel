from datetime import date, timedelta
import numpy as np

_GRANULARITY_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


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


def period_start(day: date, granularity: str) -> date:
    if granularity == "weekly":
        return day - timedelta(days=day.weekday())
    if granularity == "yearly":
        return date(day.year, 1, 1)
    return date(day.year, day.month, 1)


def period_sequence(start: date, end: date, granularity: str) -> list[date]:
    cursor = period_start(start, granularity)
    keys: list[date] = []
    seen: set[str] = set()
    step = 7 if granularity == "weekly" else 1
    while cursor <= end:
        key = period_key(cursor, granularity)
        if key not in seen:
            seen.add(key)
            keys.append(cursor)
        if granularity == "monthly":
            cursor = (
                date(cursor.year + 1, 1, 1)
                if cursor.month == 12
                else date(cursor.year, cursor.month + 1, 1)
            )
        else:
            cursor = cursor + timedelta(days=step)
    return keys


def seasonal_factor(day: date) -> float:
    doy = day.timetuple().tm_yday
    return float(np.sin(2 * np.pi * (doy - 105) / 365.0))


def seasonal_window(year: int, composite_season: str) -> tuple[str, str]:
    parts = composite_season.split("/")
    if len(parts) != 2:
        raise ValueError("Composite season must be MM-DD/MM-DD.")
    return f"{year}-{parts[0].strip()}", f"{year}-{parts[1].strip()}"


def aggregate_observations(
    observations: list[dict], granularity: str = "monthly"
) -> list[dict]:
    buckets: dict[str, dict[str, list[float]]] = {}
    order: list[str] = []
    for obs in observations:
        raw = obs.get("datetime") or ""
        try:
            day = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        key = period_key(day, granularity)
        if key not in buckets:
            buckets[key] = {
                "ndvi": [],
                "ndwi": [],
                "ndmi": [],
                "last_datetime": "",
            }
            order.append(key)
        for field, column in (
            ("ndvi", "mean_ndvi"),
            ("ndwi", "mean_ndwi"),
            ("ndmi", "mean_ndmi"),
        ):
            value = obs.get(column)
            if value is not None:
                buckets[key][field].append(float(value))
        buckets[key]["last_datetime"] = str(raw)[:10]

    series: list[dict] = []
    for key in sorted(order):
        bucket = buckets[key]
        series.append(
            {
                "period": key,
                "ndvi": round(float(np.mean(bucket["ndvi"])), 4)
                if bucket["ndvi"]
                else 0.0,
                "ndwi": round(float(np.mean(bucket["ndwi"])), 4)
                if bucket["ndwi"]
                else 0.0,
                "ndmi": round(float(np.mean(bucket["ndmi"])), 4)
                if bucket["ndmi"]
                else 0.0,
            }
        )
    return series


def _anchor_value(anchor: dict, field: str, fallback: float) -> float:
    value = anchor.get(field, anchor.get(f"mean_{field}"))
    return float(value) if value is not None else fallback


def modelled_series(
    start: date,
    end: date,
    pre_anchor: dict,
    post_anchor: dict,
    granularity: str = "monthly",
    seed: str = "peatlands",
) -> list[dict]:
    if end < start:
        return []
    stamps = period_sequence(start, end, granularity)
    if not stamps:
        return []

    rng = np.random.default_rng(abs(hash(seed)) % (2**32))
    span_days = max(1, (end - start).days)
    pre_center = _anchor_value(pre_anchor, "ndvi", 0.7)
    post_center = _anchor_value(post_anchor, "ndvi", 0.35)
    pre_ndmi = _anchor_value(pre_anchor, "ndmi", 0.35)
    post_ndmi = _anchor_value(post_anchor, "ndmi", 0.05)
    pre_ndwi = _anchor_value(pre_anchor, "ndwi", 0.2)
    post_ndwi = _anchor_value(post_anchor, "ndwi", -0.05)

    series: list[dict] = []
    for stamp in stamps:
        progress = min(1.0, max(0.0, (stamp - start).days / span_days))
        weight = progress**1.2
        wave = seasonal_factor(stamp)
        ndvi = (pre_center + (post_center - pre_center) * weight) + wave * 0.05
        ndmi = (pre_ndmi + (post_ndmi - pre_ndmi) * weight) + wave * 0.06
        ndwi = (pre_ndwi + (post_ndwi - pre_ndwi) * weight) + wave * 0.04
        series.append(
            {
                "period": period_key(stamp, granularity),
                "ndvi": round(float(np.clip(ndvi + rng.normal(0, 0.012), -1, 1)), 4),
                "ndwi": round(float(np.clip(ndwi + rng.normal(0, 0.012), -1, 1)), 4),
                "ndmi": round(float(np.clip(ndmi + rng.normal(0, 0.015), -1, 1)), 4),
            }
        )
    return series


def series_from_live(
    observations: list[dict],
    start: date,
    end: date,
    pre_anchor: dict,
    post_anchor: dict,
    granularity: str = "monthly",
    seed: str = "peatlands",
) -> list[dict]:
    observed = aggregate_observations(observations, granularity)
    if len(observed) >= 3:
        return observed
    return modelled_series(
        start, end, pre_anchor, post_anchor, granularity=granularity, seed=seed
    )

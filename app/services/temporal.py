from datetime import date
import numpy as np


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
                "mndwi": [],
                "nbr": [],
                "bsi": [],
                "sar": [],
                "last_datetime": "",
            }
            order.append(key)
        for field, column in (
            ("ndvi", "mean_ndvi"),
            ("ndwi", "mean_ndwi"),
            ("ndmi", "mean_ndmi"),
            ("mndwi", "mean_mndwi"),
            ("nbr", "mean_nbr"),
            ("bsi", "mean_bsi"),
            ("sar", "mean_sar_cross_ratio"),
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
                "mndwi": round(float(np.mean(bucket["mndwi"])), 4)
                if bucket["mndwi"]
                else 0.0,
                "nbr": round(float(np.mean(bucket["nbr"])), 4)
                if bucket["nbr"]
                else 0.0,
                "bsi": round(float(np.mean(bucket["bsi"])), 4)
                if bucket["bsi"]
                else 0.0,
                "sar": round(float(np.mean(bucket["sar"])), 4)
                if bucket["sar"]
                else 0.0,
            }
        )
    return series


def series_from_live(
    observations: list[dict], granularity: str = "monthly"
) -> list[dict]:
    return aggregate_observations(observations, granularity)

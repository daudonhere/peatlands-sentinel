import numpy as np

from app.services.reference_data import CLASS_COLORS, CLASS_NAMES

_SERIES_COLORS = {"ndvi": "#7fb069", "ndwi": "#4aa3df", "ndmi": "#e0c341"}


def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _polyline(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def render_line_chart_svg(
    series: list[dict], width: int = 720, height: int = 320
) -> str:
    left, right, top, bottom = 48, 16, 24, 36
    plot_w = width - left - right
    plot_h = height - top - bottom
    values = [float(p[key]) for p in series for key in _SERIES_COLORS if key in p]
    vmin = min(values) if values else -1.0
    vmax = max(values) if values else 1.0
    if vmax == vmin:
        vmax = vmin + 1.0

    def x_at(index: int) -> float:
        span = max(1, len(series) - 1)
        return left + plot_w * index / span

    def y_at(value: float) -> float:
        return top + plot_h * (1.0 - (value - vmin) / (vmax - vmin))

    grid = []
    for step in range(5):
        y = top + plot_h * step / 4
        grid.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#262626" stroke-width="1"/>'
        )

    paths = []
    for key, color in _SERIES_COLORS.items():
        coords = [
            (x_at(i), y_at(float(point[key])))
            for i, point in enumerate(series)
            if key in point
        ]
        if len(coords) < 2:
            continue
        paths.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{_polyline(coords)}"/>'
        )

    labels = []
    step = max(1, len(series) // 6)
    for index in range(0, len(series), step):
        labels.append(
            f'<text x="{x_at(index):.1f}" y="{height - 10}" fill="#a0a0a0" font-size="10" text-anchor="middle">{_escape(series[index]["period"])}</text>'
        )

    legend = []
    for index, (key, color) in enumerate(_SERIES_COLORS.items()):
        x = left + index * 90
        legend.append(
            f'<rect x="{x}" y="6" width="10" height="10" fill="{color}"/><text x="{x + 14}" y="15" fill="#d4d4d4" font-size="11">{key.upper()}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="#0a0a0a"/>'
        f"{''.join(grid)}{''.join(paths)}{''.join(labels)}{''.join(legend)}</svg>"
    )


def render_transition_chart_svg(
    transitions: list[dict], width: int = 720, height: int = 280
) -> str:
    rows = [row for row in transitions if row.get("from_class") != row.get("to_class")][
        :6
    ]
    if not rows:
        rows = transitions[:6]
    row_h = 36
    chart_h = max(height, 40 + len(rows) * row_h)
    max_area = (
        max((float(row.get("area_hectares", 0.0)) for row in rows), default=1.0) or 1.0
    )
    bars = []
    for index, row in enumerate(rows):
        y = 24 + index * row_h
        width_px = 12 + 420 * float(row.get("area_hectares", 0.0)) / max_area
        label = f"{row.get('from_class', '')} to {row.get('to_class', '')}"
        bars.append(
            f'<text x="16" y="{y + 14}" fill="#d4d4d4" font-size="11">{_escape(label)}</text>'
            f'<rect x="250" y="{y}" width="{width_px:.1f}" height="16" fill="#ffffff"/>'
            f'<text x="{260 + width_px:.1f}" y="{y + 13}" fill="#a0a0a0" font-size="11">{float(row.get("area_hectares", 0.0)):.1f} Ha</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {chart_h}" width="{width}" height="{chart_h}">'
        f'<rect width="{width}" height="{chart_h}" fill="#0a0a0a"/>{"".join(bars)}</svg>'
    )


def render_accuracy_chart_svg(
    accuracy: dict, width: int = 720, height: int = 220
) -> str:
    overall = float(accuracy.get("overall_accuracy", 0.0))
    kappa = float(accuracy.get("kappa", 0.0))
    bars = []
    for index, (label, value) in enumerate(
        (("Overall accuracy", overall), ("Kappa", kappa))
    ):
        y = 48 + index * 70
        width_px = max(4.0, 420 * max(0.0, min(1.0, value)))
        bars.append(
            f'<text x="16" y="{y + 16}" fill="#d4d4d4" font-size="13">{label}</text>'
            f'<rect x="180" y="{y}" width="{width_px:.1f}" height="22" fill="#ffffff"/>'
            f'<text x="{190 + width_px:.1f}" y="{y + 16}" fill="#a0a0a0" font-size="12">{value:.3f}</text>'
        )
    samples = int(accuracy.get("samples", 0))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="#0a0a0a"/>'
        f'<text x="16" y="28" fill="#ffffff" font-size="14">Model accuracy ({samples} samples)</text>'
        f"{''.join(bars)}</svg>"
    )


def colorize_index(
    values: np.ndarray, index: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        zeros = np.zeros(values.shape, dtype=np.uint8)
        return zeros, zeros, zeros
    low, high = np.percentile(finite, [5, 95])
    if high == low:
        high = low + 1.0
    t = np.clip((np.nan_to_num(values, nan=low) - low) / (high - low), 0.0, 1.0)
    if index in ("ndwi", "mndwi"):
        r = ((1.0 - t) * 40).astype(np.uint8)
        g = (t * 150 + 40).astype(np.uint8)
        b = (t * 210 + 30).astype(np.uint8)
    elif index in ("dnbr", "bsi"):
        r = (t * 220 + 20).astype(np.uint8)
        g = ((1.0 - t) * 120 + 20).astype(np.uint8)
        b = np.full(values.shape, 30, dtype=np.uint8)
    else:
        r = np.where(t < 0.5, 220, 220 - (t - 0.5) * 360).astype(np.uint8)
        g = np.where(t < 0.5, t * 360, 180).astype(np.uint8)
        b = np.full(values.shape, 30, dtype=np.uint8)
    return r, g, b


def colorize_landcover(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.zeros((*labels.shape, 3), dtype=np.uint8)
    for code, name in CLASS_NAMES.items():
        color = CLASS_COLORS.get(code, "#7a7a7a").lstrip("#")
        rgb[labels == code] = [int(color[i : i + 2], 16) for i in (0, 2, 4)]
    return rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

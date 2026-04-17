"""Common projections helpers: month math, regression, and scalar utilities."""

from typing import Optional

from services.helpers import serialize_temporal_value


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Return (year, month) after adding delta months."""
    month += delta
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return year, month


def _month_str(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _parse_month(month_str: str) -> tuple[int, int]:
    return int(month_str[:4]), int(month_str[5:7])


def _month_to_index(month_str: str, base_month: str) -> int:
    """0-based index of month_str relative to base_month."""
    y1, m1 = _parse_month(base_month)
    y2, m2 = _parse_month(month_str)
    return (y2 - y1) * 12 + (m2 - m1)


def _months_range(start: str, count: int) -> list[str]:
    """List of `count` month strings starting from `start` (YYYY-MM)."""
    y, m = _parse_month(start)
    result = []
    for offset in range(count):
        y2, m2 = _add_months(y, m, offset)
        result.append(_month_str(y2, m2))
    return result


def _series_start_month(start_date) -> str:
    serialized = serialize_temporal_value(start_date)
    return str(serialized)[:7]


def _linear_regression(points: list[float]) -> tuple[float, float]:
    """OLS on y values where x = 0, 1, 2, ... Returns (slope, intercept)."""
    n = len(points)
    if n < 2:
        return 0.0, (points[0] if points else 0.0)
    x_mean = (n - 1) / 2.0
    y_mean = sum(points) / n
    num = sum((index - x_mean) * (points[index] - y_mean) for index in range(n))
    den = sum((index - x_mean) ** 2 for index in range(n))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _sparse_linear_regression(sparse: list) -> tuple[float, float]:
    """OLS on non-None entries using their actual indices."""
    known = [
        (index, float(value)) for index, value in enumerate(sparse) if value is not None
    ]
    n = len(known)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, known[0][1]
    xs = [point[0] for point in known]
    ys = [point[1] for point in known]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[index] - x_mean) * (ys[index] - y_mean) for index in range(n))
    den = sum((xs[index] - x_mean) ** 2 for index in range(n))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _indexed_linear_regression(points: list[tuple[int, float]]) -> tuple[float, float]:
    """OLS on explicit (index, value) points using actual indices."""
    n = len(points)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, float(points[0][1])
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[index] - x_mean) * (ys[index] - y_mean) for index in range(n))
    den = sum((xs[index] - x_mean) ** 2 for index in range(n))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _project_flow_from_settings(
    sparse: list[float | None],
    history_count: int,
    horizon: int,
    *,
    mode: str = "linear",
    min_val: float | None = None,
    max_val: float | None = None,
    inflation_base: float | None = None,
    inflation_rate: float | None = None,
) -> list[float]:
    """Project a flow metric using the same linear/inflation rules as the frontend."""

    def _fallback_projection() -> list[float]:
        slope, intercept = _sparse_linear_regression(sparse)
        return [
            max(0.0, round(intercept + slope * (history_count + index), 4))
            for index in range(horizon)
        ]

    known = [
        (index, float(value)) for index, value in enumerate(sparse) if value is not None
    ]
    if not known:
        return _fallback_projection()

    if mode == "inflation":
        last_idx, last_val = known[-1]
        base = float(inflation_base) if inflation_base is not None else last_val
        monthly_rate = (
            float(inflation_rate) / 100.0 if inflation_rate is not None else 0.0
        )
        return [
            max(
                0.0,
                round(
                    base * ((1 + monthly_rate) ** ((history_count + index) - last_idx)),
                    4,
                ),
            )
            for index in range(horizon)
        ]

    inliers = [
        point
        for point in known
        if (min_val is None or point[1] >= min_val)
        and (max_val is None or point[1] <= max_val)
    ]
    if not inliers:
        return _fallback_projection()

    slope, intercept = _indexed_linear_regression(inliers)
    return [
        max(0.0, round(intercept + slope * (history_count + index), 4))
        for index in range(horizon)
    ]


def _fill_by_regression(sparse: list) -> list[float]:
    """Fill missing entries in a sparse series using OLS on known positions."""
    n = len(sparse)
    known = [
        (index, float(value)) for index, value in enumerate(sparse) if value is not None
    ]

    if len(known) == 0:
        return [0.0] * n

    if len(known) == 1:
        return [known[0][1]] * n

    xs = [point[0] for point in known]
    ys = [point[1] for point in known]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((xs[index] - x_mean) * (ys[index] - y_mean) for index in range(len(xs)))
    den = sum((xs[index] - x_mean) ** 2 for index in range(len(xs)))
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean

    result = []
    for index, value in enumerate(sparse):
        if value is not None:
            result.append(float(value))
        else:
            result.append(max(0.0, intercept + slope * index))
    return result


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if abs(float(denominator or 0)) < 0.0000001:
        return None
    return numerator / denominator


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _slider_step(min_value: float, max_value: float) -> float:
    span = abs(max_value - min_value)
    if span <= 1:
        return 0.01
    if span <= 10:
        return 0.05
    if span <= 100:
        return 0.5
    if span <= 1000:
        return 1.0
    return 5.0


def _build_slider_config(default_value: float, samples: list[float]) -> dict:
    scale = max([abs(default_value), *(abs(value) for value in samples)] or [0.0])
    scale = max(scale, 1.0)
    has_negative = default_value < 0 or any(value < 0 for value in samples)
    min_value = round(-scale * 1.5, 4) if has_negative else 0.0
    max_value = round(scale * 2.5, 4)
    if max_value <= min_value:
        max_value = round(min_value + 1.0, 4)
    return {
        "min": min_value,
        "max": max_value,
        "step": _slider_step(min_value, max_value),
    }


__all__ = [
    "_add_months",
    "_build_slider_config",
    "_fill_by_regression",
    "_indexed_linear_regression",
    "_linear_regression",
    "_month_str",
    "_month_to_index",
    "_months_range",
    "_parse_month",
    "_project_flow_from_settings",
    "_round_or_none",
    "_safe_ratio",
    "_series_start_month",
    "_slider_step",
    "_sparse_linear_regression",
]

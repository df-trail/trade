from __future__ import annotations

from math import sqrt
from statistics import mean

from ztrade.models import Bar


def sma(values: tuple[float, ...] | list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    return mean(values[-period:])


def ema(values: tuple[float, ...] | list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    result = mean(values[:period])
    for value in values[period:]:
        result = (value - result) * multiplier + result
    return result


def rsi(values: tuple[float, ...] | list[float], period: int = 14) -> float | None:
    if period <= 0 or len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-period - 1 : -1], values[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def vwap(bars: tuple[Bar, ...] | list[Bar], period: int | None = None) -> float | None:
    selected = list(bars[-period:]) if period else list(bars)
    if not selected:
        return None
    total_volume = sum(bar.volume for bar in selected)
    if total_volume <= 0:
        return None
    total_price_volume = sum((bar.vwap or bar.typical_price) * bar.volume for bar in selected)
    return total_price_volume / total_volume


def atr(bars: tuple[Bar, ...] | list[Bar], period: int = 14) -> float | None:
    if period <= 0 or len(bars) <= period:
        return None
    true_ranges: list[float] = []
    selected = bars[-period - 1 :]
    for previous, current in zip(selected[:-1], selected[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return mean(true_ranges)


def percent_change(previous: float, current: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def zscore(values: tuple[float, ...] | list[float]) -> float | None:
    if len(values) < 2:
        return None
    baseline = mean(values)
    variance = sum((value - baseline) ** 2 for value in values) / len(values)
    stddev = sqrt(variance)
    if stddev == 0:
        return 0.0
    return (values[-1] - baseline) / stddev

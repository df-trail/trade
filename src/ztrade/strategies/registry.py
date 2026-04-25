from __future__ import annotations

from ztrade.strategies.base import Strategy
from ztrade.strategies.news_momentum import NewsMomentumStrategy
from ztrade.strategies.options_flow_momentum import OptionsFlowMomentumStrategy
from ztrade.strategies.relative_volume_breakout import RelativeVolumeBreakoutStrategy
from ztrade.strategies.rsi_mean_reversion import RsiMeanReversionStrategy
from ztrade.strategies.vwap_reclaim import VwapReclaimStrategy


def default_strategies() -> tuple[Strategy, ...]:
    return (
        NewsMomentumStrategy(),
        RelativeVolumeBreakoutStrategy(),
        VwapReclaimStrategy(),
        RsiMeanReversionStrategy(),
        OptionsFlowMomentumStrategy(),
    )

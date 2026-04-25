from __future__ import annotations

from ztrade.strategies.base import Strategy
from ztrade.strategies.expanded import (
    AtrBreakoutStrategy,
    BullishEngulfingReversalStrategy,
    EarningsDriftStrategy,
    EmaTrendStrategy,
    GapContinuationStrategy,
    HighTightFlagStrategy,
    IvExpansionStrategy,
    LiquiditySweepReversalStrategy,
    MarketRegimeTrendStrategy,
    MovingAverageBounceStrategy,
    MultiTimeframeMomentumStrategy,
    NewsDipBuyStrategy,
    OpeningRangeBreakoutStrategy,
    PutFlowMomentumStrategy,
    SqueezeBreakoutStrategy,
    SupportBounceStrategy,
    TrendPullbackContinuationStrategy,
    VolumeDryUpBreakoutStrategy,
    VolumeSpikeMomentumStrategy,
    VwapFailurePutStrategy,
    VwapPullbackContinuationStrategy,
)
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
        GapContinuationStrategy(),
        OpeningRangeBreakoutStrategy(),
        EmaTrendStrategy(),
        AtrBreakoutStrategy(),
        SqueezeBreakoutStrategy(),
        SupportBounceStrategy(),
        LiquiditySweepReversalStrategy(),
        EarningsDriftStrategy(),
        MarketRegimeTrendStrategy(),
        IvExpansionStrategy(),
        VolumeSpikeMomentumStrategy(),
        VwapPullbackContinuationStrategy(),
        TrendPullbackContinuationStrategy(),
        HighTightFlagStrategy(),
        VolumeDryUpBreakoutStrategy(),
        BullishEngulfingReversalStrategy(),
        MovingAverageBounceStrategy(),
        MultiTimeframeMomentumStrategy(),
        NewsDipBuyStrategy(),
        PutFlowMomentumStrategy(),
        VwapFailurePutStrategy(),
    )

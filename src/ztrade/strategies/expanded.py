from __future__ import annotations

from ztrade.analysis.indicators import atr, ema, percent_change, rsi, sma, vwap
from ztrade.models import MarketSnapshot, TradeIdea
from ztrade.strategies.base import Strategy
from ztrade.strategies.helpers import directional_long_idea, directional_put_idea


class GapContinuationStrategy(Strategy):
    name = "gap_continuation"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 20:
            return None
        move = percent_change(bars[0].open, bars[-1].close)
        if move < 0.55 or snapshot.quote.relative_volume < 1.25:
            return None
        confidence = round(min(0.88, 0.48 + move / 5 + min(snapshot.quote.relative_volume, 2.5) / 8), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is extending away from its session open on elevated participation.",
            ta_summary=f"Session move {move:.2f}%; RVOL {snapshot.quote.relative_volume:.2f}.",
            prefer_option_threshold=0.68,
        )


class OpeningRangeBreakoutStrategy(Strategy):
    name = "opening_range_breakout"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 15:
            return None
        opening_high = max(bar.high for bar in bars[:5])
        current = bars[-1]
        if current.close <= opening_high or snapshot.quote.relative_volume < 1.2:
            return None
        distance = percent_change(opening_high, current.close)
        confidence = round(min(0.85, 0.50 + distance / 3 + snapshot.quote.relative_volume / 10), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} broke above the opening range with volume confirmation.",
            ta_summary=f"Close {current.close:.2f} > opening high {opening_high:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
            prefer_option_threshold=0.70,
        )


class EmaTrendStrategy(Strategy):
    name = "ema_trend"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        closes = snapshot.recent_closes
        if len(closes) < 22:
            return None
        ema_fast = ema(closes, 8)
        ema_slow = ema(closes, 21)
        if ema_fast is None or ema_slow is None or not (closes[-1] > ema_fast > ema_slow):
            return None
        spread = percent_change(ema_slow, ema_fast)
        confidence = round(min(0.82, 0.52 + spread / 2 + min(snapshot.quote.relative_volume, 2.0) / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is in short-term EMA trend alignment.",
            ta_summary=f"Close {closes[-1]:.2f}; EMA8 {ema_fast:.2f}; EMA21 {ema_slow:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
            prefer_option_threshold=0.72,
        )


class AtrBreakoutStrategy(Strategy):
    name = "atr_breakout"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 20:
            return None
        current_atr = atr(bars, 14)
        if current_atr is None or current_atr <= 0:
            return None
        previous_close = bars[-2].close
        expansion = bars[-1].close - previous_close
        if expansion < current_atr * 0.45 or snapshot.quote.relative_volume < 1.15:
            return None
        confidence = round(min(0.86, 0.50 + (expansion / current_atr) / 3 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is expanding beyond recent ATR-normalized movement.",
            ta_summary=f"Expansion {expansion:.2f}; ATR {current_atr:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
            prefer_option_threshold=0.70,
        )


class SqueezeBreakoutStrategy(Strategy):
    name = "squeeze_breakout"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 30:
            return None
        recent_ranges = [bar.high - bar.low for bar in bars[-20:-1]]
        avg_range = sum(recent_ranges) / len(recent_ranges)
        breakout = bars[-1].close > max(bar.high for bar in bars[-15:-1])
        if not breakout or avg_range <= 0 or snapshot.quote.relative_volume < 1.2:
            return None
        current_range = bars[-1].high - bars[-1].low
        compression_score = min(1.0, current_range / avg_range)
        confidence = round(min(0.84, 0.50 + compression_score / 5 + snapshot.quote.relative_volume / 10), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is breaking out after recent range compression.",
            ta_summary=f"Current range {current_range:.2f}; prior avg range {avg_range:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
        )


class SupportBounceStrategy(Strategy):
    name = "support_bounce"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 20 or len(closes) < 15:
            return None
        current_rsi = rsi(closes, 14)
        recent_low = min(bar.low for bar in bars[-20:])
        current = bars[-1]
        reclaimed = current.low <= recent_low * 1.002 and current.close > current.open
        if current_rsi is None or current_rsi > 48 or not reclaimed:
            return None
        confidence = round(min(0.80, 0.50 + (48 - current_rsi) / 80 + snapshot.quote.relative_volume / 15), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} bounced from recent support with a stronger close.",
            ta_summary=f"RSI {current_rsi:.1f}; recent low {recent_low:.2f}; close {current.close:.2f}.",
            prefer_option_threshold=0.75,
        )


class LiquiditySweepReversalStrategy(Strategy):
    name = "liquidity_sweep_reversal"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 15:
            return None
        prior_low = min(bar.low for bar in bars[-12:-1])
        current = bars[-1]
        swept = current.low < prior_low and current.close > prior_low
        if not swept or snapshot.quote.relative_volume < 1.1:
            return None
        confidence = round(min(0.82, 0.55 + percent_change(prior_low, current.close) / 4 + snapshot.quote.relative_volume / 15), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} swept below recent lows and reclaimed the level.",
            ta_summary=f"Low {current.low:.2f} < prior low {prior_low:.2f}; close {current.close:.2f}.",
            prefer_option_threshold=0.74,
        )


class EarningsDriftStrategy(Strategy):
    name = "earnings_drift"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.latest_news is None:
            return None
        closes = snapshot.recent_closes
        if len(closes) < 20:
            return None
        short_avg = sma(closes, 5)
        long_avg = sma(closes, 20)
        if short_avg is None or long_avg is None or short_avg <= long_avg:
            return None
        news_strength = max(0.0, snapshot.latest_news.sentiment) * snapshot.latest_news.urgency
        if news_strength < 0.45:
            return None
        confidence = round(min(0.86, 0.48 + news_strength / 3 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} has a fresh catalyst and short-term drift confirmation.",
            ta_summary=f"News strength {news_strength:.2f}; 5-bar avg {short_avg:.2f}; 20-bar avg {long_avg:.2f}.",
            prefer_option_threshold=0.69,
        )


class MarketRegimeTrendStrategy(Strategy):
    name = "market_regime_trend"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.market_regime is None or snapshot.market_regime.risk_on_score < 0.60:
            return None
        closes = snapshot.recent_closes
        if len(closes) < 20:
            return None
        short_avg = sma(closes, 5)
        long_avg = sma(closes, 20)
        if short_avg is None or long_avg is None or short_avg <= long_avg:
            return None
        confidence = round(min(0.83, 0.46 + snapshot.market_regime.risk_on_score / 4 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} trend aligns with a supportive broad-market regime.",
            ta_summary=f"Risk-on {snapshot.market_regime.risk_on_score:.2f}; 5-bar avg {short_avg:.2f}; 20-bar avg {long_avg:.2f}.",
            prefer_option_threshold=0.73,
        )


class IvExpansionStrategy(Strategy):
    name = "iv_expansion"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.option_quote is None or snapshot.option_quote.implied_volatility is None:
            return None
        if snapshot.option_quote.implied_volatility < 0.35 or snapshot.quote.relative_volume < 1.2:
            return None
        closes = snapshot.recent_closes
        if len(closes) < 20:
            return None
        current_vwap = vwap(snapshot.recent_bars, 20)
        if current_vwap is None or snapshot.quote.last < current_vwap:
            return None
        confidence = round(min(0.86, 0.48 + snapshot.option_quote.implied_volatility / 3 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} has option IV expansion with price above VWAP.",
            ta_summary=f"IV {snapshot.option_quote.implied_volatility:.2f}; VWAP {current_vwap:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
            prefer_option_threshold=0.55,
        )


class VolumeSpikeMomentumStrategy(Strategy):
    name = "volume_spike_momentum"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 22:
            return None
        current = bars[-1]
        average_volume = sum(bar.volume for bar in bars[-21:-1]) / 20
        prior_high = max(bar.high for bar in bars[-12:-1])
        if average_volume <= 0 or current.volume < average_volume * 1.6 or current.close <= prior_high:
            return None
        volume_ratio = current.volume / average_volume
        confidence = round(min(0.88, 0.50 + volume_ratio / 8 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is breaking through recent highs on a sharp volume spike.",
            ta_summary=f"Volume {volume_ratio:.2f}x 20-bar avg; close {current.close:.2f} > prior high {prior_high:.2f}.",
            prefer_option_threshold=0.69,
        )


class VwapPullbackContinuationStrategy(Strategy):
    name = "vwap_pullback_continuation"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 22 or len(closes) < 22:
            return None
        current_vwap = vwap(bars, 20)
        ema_fast = ema(closes, 8)
        ema_slow = ema(closes, 21)
        current = bars[-1]
        if current_vwap is None or ema_fast is None or ema_slow is None:
            return None
        touched_vwap = current.low <= current_vwap * 1.003
        held_trend = current.close > current_vwap and current.close > current.open and ema_fast > ema_slow
        if not (touched_vwap and held_trend):
            return None
        confidence = round(min(0.84, 0.52 + percent_change(current_vwap, current.close) / 3 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} pulled into VWAP and resumed higher with trend alignment.",
            ta_summary=f"VWAP {current_vwap:.2f}; close {current.close:.2f}; EMA8 {ema_fast:.2f} > EMA21 {ema_slow:.2f}.",
            prefer_option_threshold=0.72,
        )


class TrendPullbackContinuationStrategy(Strategy):
    name = "trend_pullback_continuation"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 22 or len(closes) < 22:
            return None
        ema_fast = ema(closes, 8)
        ema_slow = ema(closes, 21)
        current_rsi = rsi(closes, 14)
        if ema_fast is None or ema_slow is None or current_rsi is None:
            return None
        current = bars[-1]
        prior = bars[-2]
        shallow_pullback = current.low <= ema_fast * 1.005 and prior.close < bars[-3].close
        resuming = current.close > prior.close and current.close > current.open
        if not (ema_fast > ema_slow and 42 <= current_rsi <= 66 and shallow_pullback and resuming):
            return None
        confidence = round(min(0.83, 0.51 + (current_rsi - 42) / 120 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is resuming after a shallow pullback inside an uptrend.",
            ta_summary=f"RSI {current_rsi:.1f}; EMA8 {ema_fast:.2f}; EMA21 {ema_slow:.2f}.",
            prefer_option_threshold=0.74,
        )


class HighTightFlagStrategy(Strategy):
    name = "high_tight_flag"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 25:
            return None
        runup = percent_change(bars[-24].close, bars[-7].close)
        flag_high = max(bar.high for bar in bars[-7:-1])
        flag_low = min(bar.low for bar in bars[-7:-1])
        current = bars[-1]
        flag_range_pct = percent_change(flag_low, flag_high)
        if runup < 1.0 or flag_range_pct > 1.2 or current.close <= flag_high:
            return None
        confidence = round(min(0.86, 0.50 + runup / 8 + snapshot.quote.relative_volume / 10), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is resolving a tight flag after a prior impulse move.",
            ta_summary=f"Runup {runup:.2f}%; flag range {flag_range_pct:.2f}%; close {current.close:.2f} > {flag_high:.2f}.",
            prefer_option_threshold=0.68,
        )


class VolumeDryUpBreakoutStrategy(Strategy):
    name = "volume_dry_up_breakout"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 30:
            return None
        dry_volume = sum(bar.volume for bar in bars[-8:-1]) / 7
        prior_volume = sum(bar.volume for bar in bars[-26:-8]) / 18
        current = bars[-1]
        base_high = max(bar.high for bar in bars[-12:-1])
        if prior_volume <= 0 or dry_volume > prior_volume * 0.9:
            return None
        if current.close <= base_high or current.volume < prior_volume * 1.15:
            return None
        confidence = round(min(0.85, 0.50 + (prior_volume / max(dry_volume, 1)) / 12 + snapshot.quote.relative_volume / 10), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} broke out after a volume dry-up base.",
            ta_summary=f"Dry volume {dry_volume:.0f}; prior avg {prior_volume:.0f}; close {current.close:.2f} > base {base_high:.2f}.",
            prefer_option_threshold=0.71,
        )


class BullishEngulfingReversalStrategy(Strategy):
    name = "bullish_engulfing_reversal"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 15:
            return None
        previous = bars[-2]
        current = bars[-1]
        previous_red = previous.close < previous.open
        current_green = current.close > current.open
        engulfed = current.open <= previous.close and current.close >= previous.open
        if not (previous_red and current_green and engulfed and snapshot.quote.relative_volume >= 1.05):
            return None
        confidence = round(min(0.80, 0.52 + percent_change(current.open, current.close) / 5 + snapshot.quote.relative_volume / 15), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} printed a bullish engulfing reversal with acceptable participation.",
            ta_summary=f"Current body {current.open:.2f}->{current.close:.2f}; prior body {previous.open:.2f}->{previous.close:.2f}.",
            prefer_option_threshold=0.76,
        )


class MovingAverageBounceStrategy(Strategy):
    name = "moving_average_bounce"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 20 or len(closes) < 20:
            return None
        average = sma(closes, 20)
        current = bars[-1]
        if average is None:
            return None
        bounced = current.low <= average * 1.004 and current.close > average and current.close > current.open
        if not bounced:
            return None
        confidence = round(min(0.82, 0.50 + percent_change(average, current.close) / 4 + snapshot.quote.relative_volume / 12), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} bounced from its 20-bar moving average.",
            ta_summary=f"SMA20 {average:.2f}; low {current.low:.2f}; close {current.close:.2f}.",
            prefer_option_threshold=0.75,
        )


class MultiTimeframeMomentumStrategy(Strategy):
    name = "multi_timeframe_momentum"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        closes = snapshot.recent_closes
        if len(closes) < 30:
            return None
        fast = sma(closes, 5)
        medium = sma(closes, 20)
        if fast is None or medium is None:
            return None
        recent_high = max(closes[-10:-1])
        trend_move = percent_change(closes[-30], closes[-1])
        regime_ok = snapshot.market_regime is None or snapshot.market_regime.risk_on_score >= 0.55
        if not (fast > medium and closes[-1] > recent_high and trend_move > 0.8 and regime_ok):
            return None
        confidence = round(min(0.87, 0.48 + trend_move / 8 + snapshot.quote.relative_volume / 10), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} has short and medium timeframe momentum aligned.",
            ta_summary=f"5-bar avg {fast:.2f}; 20-bar avg {medium:.2f}; 30-bar move {trend_move:.2f}%.",
            prefer_option_threshold=0.70,
        )


class NewsDipBuyStrategy(Strategy):
    name = "news_dip_buy"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.latest_news is None:
            return None
        bars = snapshot.recent_bars
        closes = snapshot.recent_closes
        if len(bars) < 15 or len(closes) < 15:
            return None
        current_rsi = rsi(closes, 14)
        current = bars[-1]
        news_strength = max(0.0, snapshot.latest_news.sentiment) * snapshot.latest_news.urgency
        recovery = current.close > current.open and current.close > (current.low + (current.high - current.low) * 0.55)
        if current_rsi is None or news_strength < 0.40 or current_rsi > 58 or not recovery:
            return None
        confidence = round(min(0.84, 0.48 + news_strength / 3 + (58 - current_rsi) / 140), 3)
        return directional_long_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} is recovering after a dip while positive news remains fresh.",
            ta_summary=f"News strength {news_strength:.2f}; RSI {current_rsi:.1f}; close location recovered.",
            prefer_option_threshold=0.72,
        )


class PutFlowMomentumStrategy(Strategy):
    name = "put_flow_momentum"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        if snapshot.option_flow is None:
            return None
        side = snapshot.option_flow.side.lower()
        if "put" not in side:
            return None
        bars = snapshot.recent_bars
        if len(bars) < 10:
            return None
        downside = percent_change(bars[-10].close, bars[-1].close)
        if downside > -0.25 and snapshot.option_flow.sentiment > -0.25:
            return None
        premium_score = min(snapshot.option_flow.premium / 100_000, 1.5)
        confidence = round(min(0.88, 0.52 + abs(snapshot.option_flow.sentiment) / 4 + premium_score / 8), 3)
        return directional_put_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} has bearish put flow aligned with downside price movement.",
            ta_summary=f"Flow {snapshot.option_flow.side}; premium ${snapshot.option_flow.premium:,.0f}; 10-bar move {downside:.2f}%.",
        )


class VwapFailurePutStrategy(Strategy):
    name = "vwap_failure_put"

    def evaluate(self, snapshot: MarketSnapshot) -> TradeIdea | None:
        bars = snapshot.recent_bars
        if len(bars) < 20:
            return None
        current_vwap = vwap(bars, 20)
        if current_vwap is None:
            return None
        previous = bars[-2]
        current = bars[-1]
        failed = previous.close >= current_vwap and current.close < current_vwap and current.close < current.open
        if not failed or snapshot.quote.relative_volume < 1.15:
            return None
        confidence = round(min(0.84, 0.52 + percent_change(current.close, current_vwap) / 6 + snapshot.quote.relative_volume / 12), 3)
        return directional_put_idea(
            snapshot=snapshot,
            strategy=self.name,
            confidence=confidence,
            thesis=f"{snapshot.symbol} failed VWAP on rising participation, favoring a defined-risk put.",
            ta_summary=f"Close {current.close:.2f} < VWAP {current_vwap:.2f}; RVOL {snapshot.quote.relative_volume:.2f}.",
        )

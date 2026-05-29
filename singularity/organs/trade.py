"""TRADE — autonomous economics.

Federates: autonomous-trading-engine (Gate.io edge functions) and tradingboy.
The live engines run as Supabase edge functions; offline, this organ provides a
genuinely useful deterministic strategy core — an SMA-crossover signal and a
mini backtester — so the federation can reason about markets without keys.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan


class TradeOrgan(BaseOrgan):
    id = "trade"
    domain = Domain.ECONOMICS
    title = "TradingCore — autonomous economics"
    vision = "Turn market data into governed, risk-aware autonomous trading decisions."
    capabilities = (
        Capability("trade.signal", "Compute a BUY/SELL/HOLD signal via SMA crossover.",
                   {"prices": "list[float]", "fast": "int?", "slow": "int?"}),
        Capability("trade.backtest", "Backtest the SMA-crossover strategy over a series.",
                   {"prices": "list[float]", "fast": "int?", "slow": "int?", "cash": "float?"}),
        Capability("trade.status", "Report engine/treasury status.", {"symbol": "str?"}),
    )

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "trade.signal":
            prices = _series(payload)
            return self._signal(prices, int(payload.get("fast", 3)), int(payload.get("slow", 8)))
        if intent == "trade.backtest":
            prices = _series(payload)
            return self._backtest(
                prices,
                int(payload.get("fast", 3)),
                int(payload.get("slow", 8)),
                float(payload.get("cash", 1000.0)),
            )
        if intent == "trade.status":
            return {
                "symbol": str(payload.get("symbol", "BTC_USDT")),
                "engine": "idle",
                "open_positions": 0,
                "treasury_usd": 1000.0,
                "mode": "paper",
            }
        raise AssertionError("unreachable")  # pragma: no cover

    def _signal(self, prices: list[float], fast: int, slow: int) -> dict[str, Any]:
        if len(prices) < slow + 1:
            return {"signal": "HOLD", "reason": "insufficient data", "fast": fast, "slow": slow}
        sma_fast_prev = _sma(prices[:-1], fast)
        sma_slow_prev = _sma(prices[:-1], slow)
        sma_fast = _sma(prices, fast)
        sma_slow = _sma(prices, slow)
        signal = "HOLD"
        if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
            signal = "BUY"
        elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
            signal = "SELL"
        return {
            "signal": signal,
            "sma_fast": round(sma_fast, 4),
            "sma_slow": round(sma_slow, 4),
            "fast": fast,
            "slow": slow,
            "_usd": 0.0,
        }

    def _backtest(self, prices: list[float], fast: int, slow: int, cash: float) -> dict[str, Any]:
        start_cash = cash
        units = 0.0
        trades = 0
        for i in range(slow + 1, len(prices) + 1):
            window = prices[:i]
            sig = self._signal(window, fast, slow)["signal"]
            price = window[-1]
            if sig == "BUY" and cash > 0:
                units = cash / price
                cash = 0.0
                trades += 1
            elif sig == "SELL" and units > 0:
                cash = units * price
                units = 0.0
                trades += 1
        final_equity = cash + units * (prices[-1] if prices else 0.0)
        return {
            "start_cash": start_cash,
            "final_equity": round(final_equity, 2),
            "return_pct": round((final_equity / start_cash - 1) * 100, 2) if start_cash else 0.0,
            "trades": trades,
            "fast": fast,
            "slow": slow,
        }


def _series(payload: dict[str, Any]) -> list[float]:
    prices = payload.get("prices")
    if isinstance(prices, list) and prices:
        return [float(p) for p in prices]
    # Deterministic synthetic walk so demos and tests are reproducible.
    seed = payload.get("symbol", "BTC_USDT")
    series: list[float] = []
    price = 100.0
    digest = hashlib.sha256(str(seed).encode()).digest()
    for i in range(40):
        step = (digest[i % len(digest)] - 128) / 64.0
        price = max(1.0, price + step)
        series.append(round(price, 2))
    return series


def _sma(prices: list[float], window: int) -> float:
    window = max(1, window)
    sample = prices[-window:]
    return sum(sample) / len(sample)

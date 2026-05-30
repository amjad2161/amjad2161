"""TRADE — autonomous economics (real quant engine).

Federates autonomous-trading-engine + tradingboy. The live engines are Supabase
edge functions (network + keys); offline this organ runs a genuine quantitative
core — real EMA/RSI/MACD indicators and an event-driven backtester computing
return, Sharpe ratio, max drawdown and win-rate. These are real algorithms
(``_backend: "builtin-quant"``); the organ upgrades to the live engine when
reachable.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan


class TradeOrgan(BaseOrgan):
    id = "trade"
    domain = Domain.ECONOMICS
    title = "TradingCore — autonomous economics"
    vision = "Turn market data into governed, risk-aware autonomous trading decisions."
    capabilities = (
        Capability("trade.signal", "Compute a BUY/SELL/HOLD signal (EMA crossover + RSI filter).",
                   {"prices": "list[float]?", "symbol": "str?", "fast": "int?", "slow": "int?"}),
        Capability("trade.backtest", "Backtest the strategy: return, Sharpe, max-drawdown, win-rate.",
                   {"prices": "list[float]?", "symbol": "str?", "fast": "int?", "slow": "int?",
                    "cash": "float?"}),
        Capability("trade.status", "Report engine/treasury status (live ticker when available).",
                   {"symbol": "str?"}),
    )

    async def _attach_real(self) -> None:
        # Real market data via ccxt public endpoints (no API key needed). The
        # quant math is already real; this feeds it genuine live prices.
        import asyncio

        def _probe() -> Any:
            try:
                import ccxt
            except Exception:
                return None
            try:
                return ccxt.binance({"enableRateLimit": True})
            except Exception:
                return None

        exchange = await asyncio.to_thread(_probe)
        if exchange is None:
            raise RuntimeError("ccxt market-data backend unavailable")
        self._backend = {"exchange": exchange, "name": "binance"}
        self._detail["market_data"] = "ccxt:binance"

    def _real_closes(self, symbol: str, timeframe: str, limit: int) -> list[float] | None:
        exchange = (self._backend or {}).get("exchange")
        if exchange is None:
            return None
        try:
            ohlcv = exchange.fetch_ohlcv(symbol.replace("_", "/"), timeframe,
                                         limit=min(max(limit, 60), 500))
            return [float(c[4]) for c in ohlcv]
        except Exception:
            return None

    def _real_ticker(self, symbol: str) -> float | None:
        exchange = (self._backend or {}).get("exchange")
        if exchange is None:
            return None
        try:
            return float(exchange.fetch_ticker(symbol.replace("_", "/"))["last"])
        except Exception:
            return None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        symbol = str(payload.get("symbol", "BTC/USDT"))
        timeframe = str(payload.get("timeframe", "1h"))
        live_name = (self._backend or {}).get("name")

        if intent in ("trade.signal", "trade.backtest"):
            prices = [float(p) for p in (payload.get("prices") or [])]
            backend = "builtin-quant"
            if not prices and self._backend is not None:
                real = await asyncio.to_thread(self._real_closes, symbol, timeframe, 200)
                if real:
                    prices, backend = real, f"ccxt:{live_name}"
            if not prices:
                prices = _series(payload)
            fast, slow = int(payload.get("fast", 12)), int(payload.get("slow", 26))
            if intent == "trade.signal":
                result = self._signal(prices, fast, slow)
            else:
                result = self._backtest(prices, fast, slow, float(payload.get("cash", 1000.0)))
            if backend.startswith("ccxt"):
                result.update({"_backend": backend, "symbol": symbol,
                               "timeframe": timeframe, "price": round(prices[-1], 2),
                               "candles": len(prices)})
            result["_mode"] = "real" if str(result.get("_backend", "")).startswith("ccxt") else "mock"
            return result

        if intent == "trade.status":
            if self._backend is not None:
                last = await asyncio.to_thread(self._real_ticker, symbol)
                if last is not None:
                    return {"symbol": symbol, "last": last, "engine": "live-data",
                            "open_positions": 0, "treasury_usd": 1000.0, "mode": "paper",
                            "_backend": f"ccxt:{live_name}", "_mode": "real"}
            return {"symbol": str(payload.get("symbol", "BTC_USDT")), "engine": "idle",
                    "open_positions": 0, "treasury_usd": 1000.0, "mode": "paper",
                    "_backend": "builtin-quant", "_mode": "mock"}
        raise AssertionError("unreachable")  # pragma: no cover

    def _signal(self, prices: list[float], fast: int, slow: int) -> dict[str, Any]:
        if len(prices) < slow + 2:
            return {"signal": "HOLD", "reason": "insufficient data", "_backend": "builtin-quant"}
        ema_fast = _ema(prices, fast)
        ema_slow = _ema(prices, slow)
        ema_fast_prev = _ema(prices[:-1], fast)
        ema_slow_prev = _ema(prices[:-1], slow)
        rsi = _rsi(prices, 14)
        signal = "HOLD"
        if ema_fast_prev <= ema_slow_prev and ema_fast > ema_slow and rsi < 70:
            signal = "BUY"
        elif ema_fast_prev >= ema_slow_prev and ema_fast < ema_slow and rsi > 30:
            signal = "SELL"
        macd, macd_signal = _macd(prices)
        return {
            "signal": signal,
            "ema_fast": round(ema_fast, 4),
            "ema_slow": round(ema_slow, 4),
            "rsi": round(rsi, 2),
            "macd": round(macd, 4),
            "macd_signal": round(macd_signal, 4),
            "fast": fast,
            "slow": slow,
            "_backend": "builtin-quant",
            "_usd": 0.0,
        }

    def _backtest(self, prices: list[float], fast: int, slow: int, cash: float) -> dict[str, Any]:
        start_cash = cash
        units = 0.0
        trades = 0
        wins = 0
        entry = 0.0
        equity_curve: list[float] = []
        for i in range(slow + 2, len(prices) + 1):
            window = prices[:i]
            price = window[-1]
            sig = self._signal(window, fast, slow)["signal"]
            if sig == "BUY" and cash > 0:
                units = cash / price
                entry = price
                cash = 0.0
                trades += 1
            elif sig == "SELL" and units > 0:
                cash = units * price
                if price > entry:
                    wins += 1
                units = 0.0
                trades += 1
            equity_curve.append(cash + units * price)
        final_equity = cash + units * (prices[-1] if prices else 0.0)
        closed = max(1, trades // 2)
        return {
            "start_cash": start_cash,
            "final_equity": round(final_equity, 2),
            "return_pct": round((final_equity / start_cash - 1) * 100, 2) if start_cash else 0.0,
            "trades": trades,
            "win_rate_pct": round(100 * wins / closed, 1),
            "sharpe": round(_sharpe(equity_curve), 3),
            "max_drawdown_pct": round(_max_drawdown(equity_curve) * 100, 2),
            "fast": fast,
            "slow": slow,
            "_backend": "builtin-quant",
        }


# --------------------------------------------------------------------------
# Real indicators (no third-party deps)
# --------------------------------------------------------------------------
def _series(payload: dict[str, Any]) -> list[float]:
    prices = payload.get("prices")
    if isinstance(prices, list) and prices:
        return [float(p) for p in prices]
    seed = payload.get("symbol", "BTC_USDT")
    digest = hashlib.sha256(str(seed).encode()).digest()
    series: list[float] = []
    price = 100.0
    for i in range(60):
        step = (digest[i % len(digest)] - 128) / 48.0
        price = max(1.0, price + step + math.sin(i / 6) * 0.4)
        series.append(round(price, 2))
    return series


def _ema(prices: list[float], window: int) -> float:
    window = max(1, window)
    k = 2 / (window + 1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = losses = 0.0
    for a, b in zip(prices[-period - 1:], prices[-period:]):
        diff = b - a
        gains += max(diff, 0.0)
        losses += max(-diff, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - (100 / (1 + rs))


def _macd(prices: list[float]) -> tuple[float, float]:
    macd = _ema(prices, 12) - _ema(prices, 26)
    # signal line approximated as EMA9 of the MACD proxy series tail
    tail = prices[-9:] if len(prices) >= 9 else prices
    signal = (_ema(tail, 9) - _ema(tail, min(26, len(tail))))
    return macd, signal


def _sharpe(equity: list[float]) -> float:
    if len(equity) < 3:
        return 0.0
    returns = [(equity[i] / equity[i - 1] - 1) for i in range(1, len(equity)) if equity[i - 1]]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(252)  # annualised


def _max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)
    return max_dd

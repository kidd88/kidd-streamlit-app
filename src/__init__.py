# src/__init__.py

from .data_loader import load_price_data
from .engine import run_backtest_engine

# 引入各自的策略類別
from .strategies.base import BaseStrategy
from .strategies.sma_cross import SmaCrossStrategy
from .strategies.rsi import RsiStrategy
from .strategies.macd import MacdStrategy
from .strategies.bbands import BbandsStrategy
from .strategies.kd import KdStrategy
from .strategies.candlestick import CandlestickPatternStrategy

# 統一規範的 STRATEGY_MAP
STRATEGY_MAP = {
    "SmaCross": SmaCrossStrategy,
    "Rsi": RsiStrategy,
    "Macd": MacdStrategy,
    "Bbands": BbandsStrategy,
    "Kd": KdStrategy,
    "Candlestick": CandlestickPatternStrategy,
}

__all__ = [
    'load_price_data',
    'run_backtest_engine',
    'BaseStrategy',
    'SmaCrossStrategy',
    'RsiStrategy',
    'MacdStrategy',
    'BbandsStrategy',
    'KdStrategy',
    'CandlestickPatternStrategy',
    'STRATEGY_MAP',
]
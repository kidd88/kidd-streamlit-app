# src/strategies/__init__.py

from .base import BaseStrategy
from .sma_cross import SmaCrossStrategy
from .rsi import RsiStrategy
from .macd import MacdStrategy
from .bbands import BbandsStrategy
from .kd import KdStrategy
from .candlestick import CandlestickPatternStrategy

# 1. 統一規範的 STRATEGY_MAP (Key 採用簡潔大駝峰)
STRATEGY_MAP = {
    "SmaCross": SmaCrossStrategy,
    "Rsi": RsiStrategy,
    "Macd": MacdStrategy,
    "Bbands": BbandsStrategy,
    "Kd": KdStrategy,
    "Candlestick": CandlestickPatternStrategy,
}

# 2. 完整匯出清單
__all__ = [
    "BaseStrategy",
    "SmaCrossStrategy",
    "RsiStrategy",
    "MacdStrategy",
    "BbandsStrategy",
    "KdStrategy",
    "CandlestickPatternStrategy",
    "STRATEGY_MAP",
]
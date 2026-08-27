from .base_strategy import BaseStrategy
from .sma_cross import SMACrossStrategy
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bbands_strategy import BBandsStrategy

# 1. 策略對照字典 (字串對應至策略類別)
STRATEGY_MAP = {
    "SMACross": SMACrossStrategy,
    "RSI": RSIStrategy,
    "MACD": MACDStrategy,
    "BBands": BBandsStrategy,
}

# 2. 完整匯出清單 (確保外部使用 from src import * 或單獨 import 時皆可存取)
__all__ = [
    "BaseStrategy",
    "SMACrossStrategy",
    "RSIStrategy",
    "MACDStrategy",
    "BBandsStrategy",
    "STRATEGY_MAP",
]
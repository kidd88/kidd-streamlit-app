import backtrader as bt
import pandas as pd
from ..utils.candlestick_patterns import identify_pattern_combination
from .base import BaseStrategy


class CandlestickPatternStrategy(BaseStrategy):
  """依據 26 種經典 K 棒組合型態圖譜進行事件驅動回測的策略"""

  params = (
      (
          "bullish_target",
          ["A-啟明之星", "C-紅三兵", "F-旭日東升", "F-曙光初現"],
      ),  # 視為買進訊號的型態清單
      ("bearish_target", ["B-黃昏之星", "F-烏雲蓋頂", "M-黑三兵", "V-三只烏鴉"]),  # 視為賣出訊號的型態清單
  )

  def __init__(self):
    super().__init__()

  def next(self):
    # 1. 檢查風控
    if self.check_risk_and_exit():
      return

    if self.order:
      return

    # 2. 確保資料長度足夠
    if len(self.data) < 5:
      return

    # 3. 擷取最近的 OHLC 序列
    opens = pd.Series(self.data.open.get(size=len(self.data)))
    highs = pd.Series(self.data.high.get(size=len(self.data)))
    lows = pd.Series(self.data.low.get(size=len(self.data)))
    closes = pd.Series(self.data.close.get(size=len(self.data)))

    df_recent = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes}
    )

    # 4. 辨識當前組合型態
    pattern = identify_pattern_combination(df_recent)

    # 5. 執行進出場
    if not self.position:
      if pattern in self.p.bullish_target:
        cash = self.broker.getcash()
        price = self.data.close[0]
        size = int((cash * 0.95) / (price * 1000)) * 1000
        if size > 0:
          self.log(f"🎯 【K棒圖譜買進】 觸發多方型態: {pattern}，買進 {size} 股")
          self.order = self.buy(size=size)
    else:
      if pattern in self.p.bearish_target:
        self.log(f"🚪 【K棒圖譜賣出】 觸發空方型態: {pattern}，全面清倉")
        self.order = self.sell(size=self.position.size)
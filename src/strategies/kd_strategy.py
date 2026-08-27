import backtrader as bt
import pandas as pd
from .base_strategy import BaseStrategy


class KDStrategy(BaseStrategy):
  """KD 隨機指標交叉策略 (事件驅動版)

  - 買進訊號 (Gold Cross): %K 在低檔向上突破 %D
  - 賣出訊號 (Dead Cross): %K在高檔向下跌破 %D
  """

  params = (
      ('k_period', 9),
      ('d_period', 3),
      ('k_oversold', 20),
      ('k_overbought', 80),
  )

  def __init__(self):
    super().__init__()
    # 定義自定義的 %K 與 %D 線條容器
    self.lines.percK = bt.LineBuffer()
    self.lines.percD = bt.LineBuffer()

  def next(self):
    # 1. 優先檢查並執行模組化風控停損
    if self.check_risk_and_exit():
      return

    # 2. 確保訂單正在進行中則不重複下單
    if self.order:
      return

    # 3. 動態計算當前歷史資料的 KD 數值（確保歷史長度足夠）
    length = self.p.k_period + self.p.d_period + 5
    if len(self.data) < length:
      return

    # 擷取 Backtrader 資料序列轉為 Pandas Series 來精確計算 KD
    highs = pd.Series(self.data.high.get(size=len(self.data)))
    lows = pd.Series(self.data.low.get(size=len(self.data)))
    closes = pd.Series(self.data.close.get(size=len(self.data)))

    low_min = lows.rolling(window=self.p.k_period).min()
    high_max = highs.rolling(window=self.p.k_period).max()

    rsv = (closes - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)

    k_series = rsv.rolling(window=self.p.d_period).mean().fillna(50)
    d_series = k_series.rolling(window=self.p.d_period).mean().fillna(50)

    # 取得當日與前一日的數值
    k_now, k_prev = k_series.iloc[-1], k_series.iloc[-2]
    d_now, d_prev = d_series.iloc[-1], d_series.iloc[-2]

    # 4. 判斷黃金交叉與死亡交叉
    gold_cross = (k_prev <= d_prev) and (k_now > d_now)
    dead_cross = (k_prev >= d_prev) and (k_now < d_now)

    # 5. 進出場邏輯結合超賣/超買條件
    buy_cond = gold_cross and (k_now <= self.p.k_oversold + 20)
    sell_cond = dead_cross and (k_now >= self.p.k_overbought - 20)

    # 6. 執行下單（改為根據可用資金計算合適股數，避免預設只買 1 股導致資金無波動）
    if not self.position:
      if buy_cond:
        cash = self.broker.getcash()
        price = self.data.close[0]
        # 台股以 1 張 (1000股) 為單位，保留 5% 現金作為手續費與滑價緩衝
        size = int((cash * 0.95) / (price * 1000)) * 1000
        if size > 0:
          self.log(
              f"🎯 【KD 買進訊號】 全倉買進 {size} 股 (K: {k_now:.2f}, D:"
              f" {d_now:.2f})"
          )
          self.order = self.buy(size=size)
    else:
      if sell_cond:
        self.log(
            f"🚪 【KD 賣出訊號】 全部清倉賣出 (K: {k_now:.2f}, D: {d_now:.2f})"
        )
        self.order = self.sell(size=self.position.size)
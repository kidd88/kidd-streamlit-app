import backtrader as bt
from .base import BaseStrategy


class RsiStrategy(BaseStrategy):
    """
    RSI 相對強弱策略
    - RSI < 超賣門檻 -> 全倉買入 (BUY)
    - RSI > 超買門檻 -> 平倉賣出 (SELL)
    """
    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )

    def __init__(self):
        super().__init__()
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if self.order:
            return

        available_cash = self.broker.getcash() * 0.995

        # 1. 無持倉 -> 超賣買入
        if not self.position:
            if self.rsi[0] < self.p.oversold:
                size = int(available_cash / self.data.close[0])
                if size > 0:
                    self.order = self.buy(size=size)
                    self.log(f"買入訊號 (RSI 超賣: {self.rsi[0]:.2f}) | 收盤價: {self.data.close[0]:.2f}")

        # 2. 有持倉 -> 風控檢查或超買平倉
        else:
            if self.check_risk_and_exit():
                return

            if self.rsi[0] > self.p.overbought:
                self.log(f"賣出訊號 (RSI 超買: {self.rsi[0]:.2f}) | 收盤價: {self.data.close[0]:.2f}")
                self.order = self.close()
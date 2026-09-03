import backtrader as bt
from .base import BaseStrategy


class BbandsStrategy(BaseStrategy):
    """
    布林通道突破/均值回歸策略
    - 價格跌破下軌 (Lower Band) -> 全倉買入 (BUY)
    - 價格突破上軌 (Upper Band) -> 平倉賣出 (SELL)
    """
    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )

    def __init__(self):
        super().__init__()
        self.bbands = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor
        )

    def next(self):
        if self.order:
            return

        available_cash = self.broker.getcash() * 0.995

        # 1. 無持倉 -> 跌破下軌買入
        if not self.position:
            if self.data.close[0] < self.bbands.lines.bot[0]:
                size = int(available_cash / self.data.close[0])
                if size > 0:
                    self.order = self.buy(size=size)
                    self.log(f"買入訊號 (跌破布林下軌: {self.bbands.lines.bot[0]:.2f}) | 收盤價: {self.data.close[0]:.2f}")

        # 2. 有持倉 -> 風控檢查或突破上軌平倉
        else:
            if self.check_risk_and_exit():
                return

            if self.data.close[0] > self.bbands.lines.top[0]:
                self.log(f"賣出訊號 (突破布林上軌: {self.bbands.lines.top[0]:.2f}) | 收盤價: {self.data.close[0]:.2f}")
                self.order = self.close()
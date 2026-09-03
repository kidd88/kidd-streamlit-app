import backtrader as bt
from .base import BaseStrategy


class MacdStrategy(BaseStrategy):
    """
    MACD 柱狀圖/交叉策略
    - MACD 線向上突破 Signal 線 (金叉) -> 全倉買入 (BUY)
    - MACD 線向下跌破 Signal 線 (死叉) -> 平倉賣出 (SELL)
    """
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )

    def __init__(self):
        super().__init__()
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if self.order:
            return

        available_cash = self.broker.getcash() * 0.995

        # 1. 無持倉 -> MACD 金叉買入
        if not self.position:
            if self.crossover > 0:
                size = int(available_cash / self.data.close[0])
                if size > 0:
                    self.order = self.buy(size=size)
                    self.log(f"買入訊號 (MACD 金叉) | 收盤價: {self.data.close[0]:.2f}")

        # 2. 有持倉 -> 風控檢查或 MACD 死叉平倉
        else:
            if self.check_risk_and_exit():
                return

            if self.crossover < 0:
                self.log(f"賣出訊號 (MACD 死叉) | 收盤價: {self.data.close[0]:.2f}")
                self.order = self.close()
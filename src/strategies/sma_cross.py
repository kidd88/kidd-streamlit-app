import backtrader as bt
from .base_strategy import BaseStrategy


class SMACrossStrategy(BaseStrategy):
    """
    雙均線交叉策略 (Dual Moving Average Crossover Strategy)
    - 快線向上突破慢線 (金叉) -> 全倉買入 (BUY)
    - 快線向下跌破慢線 (死叉) -> 平倉賣出 (SELL)
    """
    params = (
        ('fast_period', 10),
        ('slow_period', 50),
    )

    def __init__(self):
        super().__init__()
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def calculate_next_signal_price(self):
        """利用聯立方程推導明日觸發均線交叉的臨界股價"""
        nf = self.p.fast_period
        ns = self.p.slow_period
        
        if len(self.data.close) < ns:
            return None

        sum_fast_prev = sum(self.data.close.get(size=nf - 1))
        sum_slow_prev = sum(self.data.close.get(size=ns - 1))

        term_slow = sum_slow_prev / ns
        term_fast = sum_fast_prev / nf
        crossover_price = (term_slow - term_fast) / ((1.0 / nf) - (1.0 / ns))
        
        return round(crossover_price, 2)

    def next(self):
        if self.order:
            return

        available_cash = self.broker.getcash() * 0.995

        # 1. 無持倉 -> 雙均線金叉買入
        if not self.position:
            if self.crossover > 0:
                size = int(available_cash / self.data.close[0])
                if size > 0:
                    self.order = self.buy(size=size)
                    self.log(f"買入訊號 (SMA 金叉) | 收盤價: {self.data.close[0]:.2f}")

        # 2. 有持倉 -> 進行風控檢查與死叉平倉檢查
        else:
            # (A) 優先執行通用風控檢查
            if self.check_risk_and_exit():
                return

            # (B) 均線死叉策略正常平倉
            if self.crossover < 0:
                self.log(f"賣出訊號 (SMA 死叉) | 收盤價: {self.data.close[0]:.2f}")
                self.order = self.close()

    def stop(self):
        super().stop()
        self.latest_status['next_signal_price'] = self.calculate_next_signal_price()
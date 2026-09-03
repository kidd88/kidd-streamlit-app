import backtrader as bt
from .base import BaseStrategy


class SmaCrossStrategy(BaseStrategy):
    """
    雙均線交叉策略 (Dual Moving Average Crossover Strategy)
    - 快線向上突破慢線 (金叉) + 通過買進量比門檻 -> 全倉買入 (BUY)
    - 快線向下跌破慢線 (死叉) + 通過賣出量比門檻 -> 平倉賣出 (SELL)
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
                # 🛑 檢查當日成交量是否達到設定的買進量比門檻
                if not self.check_volume_ratio_pass(is_buy=True):
                    vr_val = getattr(self.data, 'Volume_Ratio', [0.0])[0]
                    self.log(f"🚫 買進訊號攔截：量比未達門檻 (當前量比: {vr_val:.2f} < 設定門檻: {self.p.buy_volume_ratio_threshold})")
                    return

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
                # 🛑 檢查賣出量比門檻（若設定大於 0 時生效）
                if not self.check_volume_ratio_pass(is_buy=False):
                    vr_val = getattr(self.data, 'Volume_Ratio', [0.0])[0]
                    self.log(f"🚫 賣出訊號攔截：量比未達門檻 (當前量比: {vr_val:.2f} < 設定門檻: {self.p.sell_volume_ratio_threshold})")
                    return

                self.log(f"賣出訊號 (SMA 死叉) | 收盤價: {self.data.close[0]:.2f}")
                self.order = self.close()

    def stop(self):
        super().stop()
        self.latest_status['next_signal_price'] = self.calculate_next_signal_price()
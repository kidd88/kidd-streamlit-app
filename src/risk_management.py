import backtrader as bt


class DynamicStopLossManager:
    """模組化風控管理工具 (通用於 Backtrader 策略)"""
    def __init__(self, stop_type='hard', stop_loss_pct=0.07, atr_multiplier=2.0, trailing_pct=0.05):
        self.stop_type = str(stop_type).lower()
        self.stop_loss_pct = stop_loss_pct
        self.atr_multiplier = atr_multiplier
        self.trailing_pct = trailing_pct

        self.entry_price = None
        self.highest_price = None
        self.stop_price = None

    def reset_position(self, entry_price: float, current_atr: float = 0.0):
        """買入成交後初始化停損價"""
        self.entry_price = entry_price
        self.highest_price = entry_price

        if self.stop_type == 'hard':
            self.stop_price = entry_price * (1.0 - self.stop_loss_pct) if self.stop_loss_pct > 0 else 0.0
        elif self.stop_type == 'trailing':
            self.stop_price = entry_price * (1.0 - self.trailing_pct)
        elif self.stop_type == 'atr':
            self.stop_price = entry_price - (current_atr * self.atr_multiplier)
        else:
            self.stop_price = 0.0

    def update_and_check(self, current_price: float, current_high: float, current_atr: float = 0.0) -> bool:
        """每日更新停損線並檢查是否觸發停損"""
        if not self.stop_price or self.stop_price <= 0:
            return False

        # 1. 移動停損 (Trailing) 邏輯：價格創新高，停損價跟著上調
        if self.stop_type == 'trailing':
            if current_high > self.highest_price:
                self.highest_price = current_high
                new_stop = self.highest_price * (1.0 - self.trailing_pct)
                self.stop_price = max(self.stop_price, new_stop)

        # 2. ATR 動態停損 邏輯：價格創新高，依當前 ATR 上調停損價
        elif self.stop_type == 'atr':
            if current_high > self.highest_price:
                self.highest_price = current_high
                new_stop = self.highest_price - (current_atr * self.atr_multiplier)
                self.stop_price = max(self.stop_price, new_stop)

        # 3. 判斷當前收盤價是否跌破停損線
        return current_price <= self.stop_price
import backtrader as bt
from ..risk_management import DynamicStopLossManager


class BaseStrategy(bt.Strategy):
    """
    策略通用基類 (Base Strategy)
    提供全系統統一的風控參數宣告、DynamicStopLossManager 綁定與日誌功能
    """
    params = (
        ('stop_type', 'none'),     # 風控模式: 'none', 'hard', 'trailing', 'atr'
        ('stop_loss', 0.07),       # 硬停損比例 (如 0.07 代表 7%)
        ('atr_period', 14),        # ATR 計算週期
        ('atr_multiplier', 2.5),   # ATR 倍數
        ('trailing_pct', 0.05),    # 移動停損拉回比例 (預設 5%)
    )

    def __init__(self):
        self.order = None
        self.entry_price = None
        
        # 載入 ATR 指標供風控使用
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

        # 實例化模組化風控工具
        self.risk_mgr = DynamicStopLossManager(
            stop_type=self.p.stop_type,
            stop_loss_pct=self.p.stop_loss,
            atr_multiplier=self.p.atr_multiplier,
            trailing_pct=self.p.trailing_pct
        )

    def log(self, txt, dt=None):
        """通用 Log 輸出函數"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f"[{dt.isoformat()}] {txt}")

    def notify_order(self, order):
        """監聽訂單狀態變更並初始化風控"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            if order.isbuy():
                self.entry_price = order.executed.price
                # 買入成交後，重設風控基準價
                self.risk_mgr.reset_position(
                    entry_price=self.entry_price,
                    current_atr=self.atr[0]
                )
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
            else:
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
                self.entry_price = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order Canceled/Margin/Rejected: Status Code {order.status}")

        self.order = None

    def check_risk_and_exit(self) -> bool:
        """檢查是否觸發風控停損，若觸發則執行平倉"""
        if not self.position:
            return False

        current_price = self.data.close[0]
        current_high = self.data.high[0]

        is_stop_triggered = self.risk_mgr.update_and_check(
            current_price=current_price,
            current_high=current_high,
            current_atr=self.atr[0]
        )

        if is_stop_triggered:
            self.log(
                f"🚨 觸發【{self.p.stop_type.upper()}】停損出場！"
                f"進場價: {self.risk_mgr.entry_price:.2f}, 停損價: {self.risk_mgr.stop_price:.2f}, "
                f"當前收盤價: {current_price:.2f}"
            )
            self.order = self.close()
            return True

        return False

    def stop(self):
        """回測結束時，匯出最後一日的狀態供 Dashboard/Runner 讀取"""
        self.latest_status = {
            'is_holding': bool(self.position),
            'current_position': 'HOLD' if bool(self.position) else 'CASH',
            'entry_price': self.entry_price,
            'current_stop_price': self.risk_mgr.stop_price,
            'last_close': self.data.close[0] if len(self.data.close) > 0 else None
        }
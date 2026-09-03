import backtrader as bt
import pandas as pd
import numpy as np


class TaiwanCommInfo(bt.CommInfoBase):
    """
    台股專用手續費與證券交易稅計算
    """
    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True),
        ('discount', 0.6),
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        comm = value * 0.001425 * self.p.discount
        if size < 0:
            comm += value * 0.003
        return comm


# 💡 定義支援量比與成交金額的自定義 PandasData 餵入源
class PandasDataWithVolumeRatio(bt.feeds.PandasData):
    lines = ('Volume_Ratio', 'Trading_Value')
    params = (
        ('Volume_Ratio', -1),
        ('Trading_Value', -1),
    )


def run_backtest_engine(data, strategy_cls, init_cash=1000000.0, discount=0.6, **kwargs):
    """
    動態事件驅動回測引擎 (正確繪製每日 Equity 與動態計算 KPI)
    """
    cerebro = bt.Cerebro()

    # 1. 載入 K 線數據 (改用帶有 Volume_Ratio 的自定義 Data Feed，讓策略能讀取量比欄位)
    data_feed = PandasDataWithVolumeRatio(dataname=data)
    cerebro.adddata(data_feed)

    # 2. 動態傳入策略與停損等參數 (kwargs 包含量比閥值，會完整帶入)
    cerebro.addstrategy(strategy_cls, **kwargs)

    # 3. 設定初始資金與交易手續費
    cerebro.broker.setcash(init_cash)
    cerebro.broker.addcommissioninfo(TaiwanCommInfo(discount=discount))

    # 4. 載入核心分析器 (Sharpe, DrawDown, TradeAnalyzer)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, riskfreerate=0.01, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')

    # 5. 執行回測
    results = cerebro.run()
    strat = results[0]

    # 📌 抓取策略物件在 stop() 或執行過程中掛載的最新狀態
    latest_status = getattr(strat, 'latest_status', {})
    if not isinstance(latest_status, dict):
        latest_status = {}

    # -------------------------------------------------------------------------
    # 📌 備援邏輯：自動解析最後一日狀態與預估價位
    # -------------------------------------------------------------------------
    pos_size = strat.position.size

    # 相容欄位名稱大小寫 (Close / close)
    if 'close' in data.columns:
        last_close = data['close'].iloc[-1]
    elif 'Close' in data.columns:
        last_close = data['Close'].iloc[-1]
    else:
        last_close = data.iloc[-1, 3]  # 若欄位名稱不同，預設取 OHLCV 中的第 4 欄 (Close)

    current_position = latest_status.get('current_position', 'HOLD' if pos_size > 0 else 'CASH')
    entry_price = latest_status.get('entry_price', strat.position.price if pos_size > 0 else None)
    
    # 優先從 risk_mgr 抓取當前停損價，備援讀取策略屬性
    stop_p = None
    if hasattr(strat, 'risk_mgr') and getattr(strat.risk_mgr, 'stop_price', None):
        stop_p = strat.risk_mgr.stop_price
    elif hasattr(strat, 'stop_price'):
        stop_p = strat.stop_price

    current_stop_loss = latest_status.get('current_stop_loss', stop_p)
    next_buy_price = latest_status.get('next_buy_price', latest_status.get('next_signal_price', None))
    next_sell_price = latest_status.get('next_sell_price', latest_status.get('next_signal_price', None))

    # 安全讀取策略內指標數值的輔助函式
    def get_indicator_value(obj, attr_list):
        for attr in attr_list:
            if hasattr(obj, attr):
                ind = getattr(obj, attr)
                try:
                    if len(ind) > 0 and not np.isnan(ind[0]):
                        return ind[0]
                except Exception:
                    pass
        return None

    slow_ma_val = get_indicator_value(strat, ['slow_ma', 'sma_slow', 'sma2', 'ma_slow'])

    # 若空手 (CASH) 且策略未寫入 next_buy_price，依指標自動推算參考買入價
    if current_position == 'CASH' and next_buy_price is None:
        next_buy_price = slow_ma_val if slow_ma_val is not None else last_close

    # 若持倉 (HOLD) 且策略未寫入 next_sell_price，推算參考賣出價
    if current_position in ['HOLD', 'POSITION', 'LONG'] and next_sell_price is None:
        next_sell_price = slow_ma_val if slow_ma_val is not None else last_close

    # 6. 動態計算績效指標
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - init_cash) / init_cash

    # 計算 CAGR
    days = (data.index[-1] - data.index[0]).days
    cagr = ((final_value / init_cash) ** (365.0 / days) - 1.0) if days > 0 else 0.0

    # 提取動態每日資產價值 (Equity Curve)
    time_returns = strat.analyzers.timereturn.get_analysis()
    returns_series = pd.Series(time_returns)
    equity_series = init_cash * (1 + returns_series).cumprod()
    
    # 填補時間軸 (確保與原 Data 頁面完全對齊)
    equity_df = pd.DataFrame({'Equity': equity_series}, index=data.index)
    equity_df['Equity'] = equity_df['Equity'].ffill().fillna(init_cash)

    # 動態讀取分析器指標
    dd_analysis = strat.analyzers.drawdown.get_analysis()
    mdd = -(dd_analysis.get('max', {}).get('drawdown', 0.0) / 100.0)

    sharpe_analysis = strat.analyzers.sharpe.get_analysis()
    sharpe = sharpe_analysis.get('sharperatio', 0.0)
    sharpe = 0.0 if (sharpe is None or np.isnan(sharpe)) else sharpe

    trade_analysis = strat.analyzers.trades.get_analysis()
    total_trades = trade_analysis.get('total', {}).get('closed', 0)
    won_trades = trade_analysis.get('won', {}).get('total', 0)
    win_rate = (won_trades / total_trades) if total_trades > 0 else 0.0

    # 7. 回傳成果字典 (同時相容 Streamlit app.py 與 batch_runner.py)
    return {
        'total_return': total_return,
        'cagr': cagr,
        'mdd': mdd,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'equity_curve': equity_df,
        'latest_status': latest_status,         # 供 Streamlit app.py 使用
        'current_position': current_position,   # 供 batch_runner.py 使用
        'entry_price': entry_price,            # 供 batch_runner.py 使用
        'current_stop_loss': current_stop_loss, # 供 batch_runner.py 使用
        'next_buy_price': next_buy_price,      # 供 batch_runner.py 使用
        'next_sell_price': next_sell_price,    # 供 batch_runner.py 使用
    }
import sys
import os

# 強制將專案根目錄納入模組搜尋路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from src import load_price_data, run_backtest_engine, STRATEGY_MAP

# --- 股票名稱抓取輔助函式 ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_stock_name(symbol: str) -> str:
    """透過 yfinance 獲取公司名稱/簡稱，抓不到則回傳原代碼"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        name = info.get('shortName') or info.get('longName')
        if name:
            return f"{name} ({symbol})"
    except Exception:
        pass
    return symbol


st.set_page_config(page_title="台股量化回測系統", layout="wide")

st.title("📈 股票策略運行回測 Dashboard (事件驅動版)")

# --- 側邊欄設定 ---
st.sidebar.header("1. 基本回測參數")
ticker = st.sidebar.text_input("股票代碼 (含字尾)", value="2330.TW")
start_date = st.sidebar.date_input("開始日期", pd.to_datetime("2020-01-01"))
end_date = st.sidebar.date_input("結束日期", pd.to_datetime("2026-08-22"))
init_cash = st.sidebar.number_input("初始資金 (TWD)", value=1000000.0, step=100000.0)

st.sidebar.header("2. 交易成本與風控管理")
discount = st.sidebar.slider("券商手續費折扣", min_value=0.1, max_value=1.0, value=0.6, step=0.05)

# 📌 模組化風控模式選擇
stop_type_display = st.sidebar.selectbox(
    "風控停損模式", 
    ["無風控 (None)", "固定百分比停損 (Hard)", "移動停損 (Trailing)", "ATR 動態停損 (ATR)"]
)

# 映射風控模式代碼
stop_type_map = {
    "無風控 (None)": "none",
    "固定百分比停損 (Hard)": "hard",
    "移動停損 (Trailing)": "trailing",
    "ATR 動態停損 (ATR)": "atr"
}
stop_type = stop_type_map[stop_type_display]

# 根據選定的風控模式，動態顯示微調控制項
stop_loss_input = 7.0
atr_multiplier = 2.5
trailing_pct_input = 5.0
atr_period = 14

if stop_type == "hard":
    stop_loss_input = st.sidebar.slider("硬停損比例 (%) [0=不啟用]", min_value=0.0, max_value=20.0, value=7.0, step=0.5)
elif stop_type == "trailing":
    trailing_pct_input = st.sidebar.slider("最高價拉回停損 (%)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
elif stop_type == "atr":
    col_atr1, col_atr2 = st.sidebar.columns(2)
    with col_atr1:
        atr_period = st.number_input("ATR 週期", min_value=5, max_value=50, value=14)
    with col_atr2:
        atr_multiplier = st.number_input("ATR 倍數", min_value=0.5, max_value=5.0, value=2.5, step=0.1)

st.sidebar.header("3. 選擇策略與參數")
strategy_name = st.sidebar.selectbox("策略類型", list(STRATEGY_MAP.keys()))

# 基礎風控參數打包 (對齊全域命名規範)
risk_kwargs = {
    'stop_type': stop_type,
    'stop_loss': stop_loss_input / 100.0,
    'atr_period': int(atr_period),
    'atr_multiplier': float(atr_multiplier),
    'trailing_pct': trailing_pct_input / 100.0
}

# 動態策略參數組裝
strategy_kwargs = {}

if strategy_name == "SMACross":
    fast_period = st.sidebar.number_input("快均線週期", value=10, min_value=2)
    slow_period = st.sidebar.number_input("慢均線週期", value=50, min_value=5)
    strategy_kwargs.update({'fast_period': fast_period, 'slow_period': slow_period})

elif strategy_name == "RSI":
    rsi_period = st.sidebar.number_input("RSI 週期", value=14, min_value=2)
    oversold = st.sidebar.number_input("超賣門檻 (買入)", value=30, min_value=5, max_value=45)
    overbought = st.sidebar.number_input("超買門檻 (賣出)", value=70, min_value=55, max_value=95)
    strategy_kwargs.update({
        'rsi_period': rsi_period, 
        'oversold': oversold, 
        'overbought': overbought
    })

elif strategy_name == "MACD":
    fast_period = st.sidebar.number_input("快線 EMA 週期", value=12, min_value=2)
    slow_period = st.sidebar.number_input("慢線 EMA 週期", value=26, min_value=5)
    signal_period = st.sidebar.number_input("訊號線 週期", value=9, min_value=2)
    strategy_kwargs.update({
        'fast_period': fast_period, 
        'slow_period': slow_period, 
        'signal_period': signal_period
    })

elif strategy_name == "BBands":
    period = st.sidebar.number_input("布林帶週期", value=20, min_value=5)
    devfactor = st.sidebar.number_input("標準差倍數", value=2.0, step=0.1)
    strategy_kwargs.update({
        'period': period, 
        'devfactor': devfactor
    })

# 📌 統一將風控參數注入策略 kwargs
strategy_kwargs.update(risk_kwargs)

run_button = st.sidebar.button("🚀 開始執行回測", type="primary")

if run_button:
    with st.spinner("資料讀取與 Backtrader 事件驅動運算中..."):
        # 1. 讀取數據與股票名稱
        df = load_price_data(ticker, start_date=str(start_date), end_date=str(end_date))
        stock_display_name = get_stock_name(ticker)
        
        if df is None or df.empty:
            st.error(f"無法讀取標的 {ticker} 在選定區間的歷史價格資料，請檢查代碼或日期區間。")
        else:
            # 2. 執行回測引擎
            strategy_cls = STRATEGY_MAP[strategy_name]
            results = run_backtest_engine(
                df,
                strategy_cls,
                init_cash=init_cash,
                discount=discount,
                **strategy_kwargs
            )

            # 3. 🔮 最新交易訊號與預估價位看板 ( Next Trade Outlook )
            latest = results.get('latest_status', results)
            st.subheader("🔮 最新交易訊號與預估價位 (Next Trade Outlook)")
            col_a, col_b, col_c = st.columns(3)

            last_close = df['Close'].iloc[-1]
            
            # 相容位置與價位讀取
            position_status = latest.get('position', latest.get('current_position', 'CASH'))
            is_holding = latest.get('is_holding', position_status in ['HOLD', 'LONG', True])
            
            entry_p = latest.get('entry_price', 0)
            current_stop_p = latest.get('current_stop_price', latest.get('current_stop_loss'))
            next_buy_p = latest.get('next_buy_price', latest.get('next_signal_price'))
            next_sell_p = latest.get('next_sell_price', latest.get('next_signal_price'))

            if is_holding:
                col_a.metric("當前持倉狀態", "持有中 (HOLD)", f"進場成交價: {entry_p:.2f} TWD" if entry_p else "-")
                
                # 顯示當前風控停損價與距離%
                if current_stop_p and isinstance(current_stop_p, (int, float)):
                    dist = ((current_stop_p - last_close) / last_close) * 100
                    col_b.metric("當前動態停損價", f"{current_stop_p:.2f} TWD", f"距離最新價 {dist:.2f}%")
                else:
                    col_b.metric("當前動態停損價", "未啟用 / 未觸發")
                    
                # 持倉時顯示「預估平倉賣出價」
                if next_sell_p and isinstance(next_sell_p, (int, float)):
                    col_c.metric("預估平倉賣出價 (明日)", f"{next_sell_p:.2f} TWD", "跌破此價位將觸發訊號平倉")
                else:
                    col_c.metric("預估平倉賣出價 (明日)", "-")
            else:
                col_a.metric("當前持倉狀態", "空倉 (CASH)", f"最新收盤價: {last_close:.2f} TWD")
                col_b.metric("當前動態停損價", "無持倉")
                
                # 空倉時顯示「預估建倉買入價」
                if next_buy_p and isinstance(next_buy_p, (int, float)):
                    col_c.metric("預估建倉買入價 (明日)", f"{next_buy_p:.2f} TWD", "突破此價位將觸發訊號建倉")
                else:
                    col_c.metric("預估建倉買入價 (明日)", "-")

            st.divider()

            # 4. 繪製 KPI Summary
            st.subheader("📊 關鍵績效指標 (KPI Summary)")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("總報酬率", f"{results.get('total_return', 0)*100:.2f}%")
            col2.metric("年化報酬率", f"{results.get('cagr', 0)*100:.2f}%")
            col3.metric("最大回撤 (MDD)", f"{results.get('mdd', 0)*100:.2f}%")
            col4.metric("夏普比率 (Sharpe)", f"{results.get('sharpe', 0):.2f}")
            col5.metric("勝率 (Win Rate)", f"{results.get('win_rate', 0)*100:.1f}%")

            # 5. 繪製行情與資產圖表
            st.subheader("📈 回測走勢與資產變化")
            fig = go.Figure()
            
            # 收盤價 (左 Y 軸)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['Close'],
                mode='lines', name='收盤價 (TWD)',
                line=dict(color='#26a69a', width=1.5)
            ))
            
            # 資金曲線 (右 Y 軸)
            equity_df = results.get('equity_curve', pd.DataFrame())
            if not equity_df.empty and 'Equity' in equity_df.columns:
                fig.add_trace(go.Scatter(
                    x=equity_df.index, y=equity_df['Equity'],
                    mode='lines', name='帳戶資產淨值',
                    line=dict(color='#ff9800', width=2),
                    yaxis='y2'
                ))

            # 動態生成圖表風控標題描述
            if stop_type == 'hard':
                risk_info = f"硬停損: {stop_loss_input}%"
            elif stop_type == 'trailing':
                risk_info = f"移動停損: 拉回 {trailing_pct_input}%"
            elif stop_type == 'atr':
                risk_info = f"ATR 動態停損: {atr_multiplier}x ATR({atr_period})"
            else:
                risk_info = "無風控"

            fig.update_layout(
                title=f"{stock_display_name} 價格與資產變化曲線 ({risk_info})",
                xaxis_title="日期",
                yaxis=dict(title="股票價格 (TWD)"),
                yaxis2=dict(title="帳戶總資產 (TWD)", overlaying='y', side='right', showgrid=False),
                height=600,
                hovermode="x unified",
                legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.6)')
            )
            st.plotly_chart(fig, use_container_width=True)
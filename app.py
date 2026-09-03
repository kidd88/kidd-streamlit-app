import io
import os
import sys

# 強制將專案根目錄納入模組搜尋路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import plotly.graph_objects as go
from plotly.subplots import make_subplots  # 📌 用於建立 K 線與成交量的上下子圖
import streamlit as st
import pandas as pd
import yfinance as yf
from src import STRATEGY_MAP, load_price_data, run_backtest_engine
from src.indicators import add_volume_ratio  # 👈 引入獨立的量比與指標計算模組
from src.utils.candlestick_patterns import identify_pattern_combination


# --- 股票名稱抓取輔助函式 ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_stock_name(symbol: str) -> str:
  """透過 yfinance 獲取公司名稱/簡稱，抓不到則回傳原代碼"""
  try:
    ticker = yf.Ticker(symbol)
    info = ticker.info
    name = info.get("shortName") or info.get("longName")
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
end_date = st.sidebar.date_input("結束日期", pd.Timestamp.today())
init_cash = st.sidebar.number_input("初始資金 (TWD)", value=1000000.0, step=100000.0)

st.sidebar.header("2. 交易成本與風控管理")
discount = st.sidebar.slider(
    "券商手續費折扣", min_value=0.1, max_value=1.0, value=0.6, step=0.05
)

# 📌 模組化風控模式選擇
stop_type_display = st.sidebar.selectbox(
    "風控停損模式",
    [
        "無風控 (None)",
        "固定百分比停損 (Hard)",
        "移動停損 (Trailing)",
        "ATR 動態停損 (ATR)",
    ],
)

stop_type_map = {
    "無風控 (None)": "none",
    "固定百分比停損 (Hard)": "hard",
    "移動停損 (Trailing)": "trailing",
    "ATR 動態停損 (ATR)": "atr",
}
stop_type = stop_type_map[stop_type_display]

stop_loss_input = 7.0
atr_multiplier = 2.5
trailing_pct_input = 5.0
atr_period = 14

if stop_type == "hard":
  stop_loss_input = st.sidebar.slider(
      "硬停損比例 (%) [0=不啟用]",
      min_value=0.0,
      max_value=20.0,
      value=7.0,
      step=0.5,
  )
elif stop_type == "trailing":
  trailing_pct_input = st.sidebar.slider(
      "最高價拉回停損 (%)",
      min_value=1.0,
      max_value=20.0,
      value=5.0,
      step=0.5,
  )
elif stop_type == "atr":
  col_atr1, col_atr2 = st.sidebar.columns(2)
  with col_atr1:
    atr_period = st.number_input("ATR 週期", min_value=5, max_value=50, value=14)
  with col_atr2:
    atr_multiplier = st.number_input(
        "ATR 倍數", min_value=0.5, max_value=5.0, value=2.5, step=0.1
    )

st.sidebar.header("3. 選擇策略與參數")
strategy_name = st.sidebar.selectbox("策略類型", list(STRATEGY_MAP.keys()))

risk_kwargs = {
    "stop_type": stop_type,
    "stop_loss": stop_loss_input / 100.0,
    "atr_period": int(atr_period),
    "atr_multiplier": float(atr_multiplier),
    "trailing_pct": trailing_pct_input / 100.0,
}

strategy_kwargs = {}

# 📊 【全域共用】量比濾網閥值設定拉桿（放在所有策略選項的外側）
st.sidebar.markdown("---")
st.sidebar.markdown("##### 📊 量比濾網閥值設定")
buy_volume_ratio_threshold = st.sidebar.slider(
    "買進最低量比門檻 (x)", min_value=0.0, max_value=3.0, value=1.0, step=0.1,
    help="當進場訊號出現時，當日成交量必須達到 20 日均量的幾倍才允許買進 (0表示不限制)"
)
sell_volume_ratio_threshold = st.sidebar.slider(
    "賣出最低量比門檻 (x)", min_value=0.0, max_value=3.0, value=0.0, step=0.1,
    help="當出場訊號出現時的量比門檻 (0表示不限制)"
)

strategy_kwargs.update({
    "buy_volume_ratio_threshold": buy_volume_ratio_threshold,
    "sell_volume_ratio_threshold": sell_volume_ratio_threshold,
})

if strategy_name == "SmaCross":
  fast_period = st.sidebar.number_input("快均線週期", value=10, min_value=2)
  slow_period = st.sidebar.number_input("慢均線週期", value=50, min_value=5)
  strategy_kwargs.update(
      {"fast_period": fast_period, "slow_period": slow_period}
  )

elif strategy_name == "Rsi":
  rsi_period = st.sidebar.number_input("RSI 週期", value=14, min_value=2)
  oversold = st.sidebar.number_input(
      "超賣門檻 (買入)", value=30, min_value=5, max_value=45
  )
  overbought = st.sidebar.number_input(
      "超買門檻 (賣出)", value=70, min_value=55, max_value=95
  )
  strategy_kwargs.update({
      "rsi_period": rsi_period,
      "oversold": oversold,
      "overbought": overbought,
  })

elif strategy_name == "Macd":
  fast_period = st.sidebar.number_input("快線 EMA 週期", value=12, min_value=2)
  slow_period = st.sidebar.number_input("慢線 EMA 週期", value=26, min_value=5)
  signal_period = st.sidebar.number_input("訊號線 週期", value=9, min_value=2)
  strategy_kwargs.update({
      "fast_period": fast_period,
      "slow_period": slow_period,
      "signal_period": signal_period,
  })

elif strategy_name == "Bbands":
  period = st.sidebar.number_input("布林帶週期", value=20, min_value=5)
  devfactor = st.sidebar.number_input("標準差倍數", value=2.0, step=0.1)
  strategy_kwargs.update({"period": period, "devfactor": devfactor})

elif strategy_name == "Kd":
  k_period = st.sidebar.number_input("K 週期 (RSV)", value=9, min_value=2)
  d_period = st.sidebar.number_input("D 週期 (平滑)", value=3, min_value=1)
  k_oversold = st.sidebar.number_input(
      "低檔超賣門檻 (%K)", value=20, min_value=5, max_value=40
  )
  k_overbought = st.sidebar.number_input(
      "高檔超買門檻 (%K)", value=80, min_value=60, max_value=95
  )
  strategy_kwargs.update({
      "k_period": k_period,
      "d_period": d_period,
      "k_oversold": k_oversold,
      "k_overbought": k_overbought,
  })

elif strategy_name == "Candlestick":
  st.sidebar.markdown("---")
  st.sidebar.markdown("#### 📈 K線型態策略參數設定")
  
  bullish_options = ["啟明之星", "紅三兵", "旭日東升", "曙光初現", "好友反攻"]
  bearish_options = ["黃昏之星", "烏雲蓋頂", "黑三兵", "三只烏鴉"]
  
  selected_bullish = st.sidebar.multiselect(
      "多方買進型態清單",
      options=bullish_options,
      default=["啟明之星", "紅三兵", "旭日東升"]
  )
  
  selected_bearish = st.sidebar.multiselect(
      "空方賣出型態清單",
      options=bearish_options,
      default=["黃昏之星", "烏雲蓋頂", "黑三兵"]
  )
  
  strategy_kwargs.update({
      "bullish_target": selected_bullish,
      "bearish_target": selected_bearish,
  })

strategy_kwargs.update(risk_kwargs)

run_button = st.sidebar.button("🚀 開始執行回測", type="primary")

if run_button:
  with st.spinner("資料讀取與 Backtrader 事件驅動運算中..."):
    df = load_price_data(
        ticker, start_date=str(start_date), end_date=str(end_date)
    )
    stock_display_name = get_stock_name(ticker)

    if df is None or df.empty:
      st.error(
          f"無法讀取標的 {ticker}"
          " 在選定區間的歷史價格資料，請檢查代碼或日期區間。"
      )
    else:
      # 💡 透過獨立的量比模組計算成交金額與量比
      df = add_volume_ratio(df, sma_period=20)

      strategy_cls = STRATEGY_MAP[strategy_name]
      results = run_backtest_engine(
          df,
          strategy_cls,
          init_cash=init_cash,
          discount=discount,
          **strategy_kwargs,
      )

      latest = results.get("latest_status", results)
      st.subheader("🔮 最新交易訊號與預估價位 (Next Trade Outlook)")
      col_a, col_b, col_c, col_d = st.columns(4)

      last_close = df["Close"].iloc[-1]
      last_val = df["Trading_Value"].iloc[-1] / 1e8
      last_vr = df["Volume_Ratio"].iloc[-1]
      last_date = df.index[-1]

      position_status = latest.get(
          "position", latest.get("current_position", "CASH")
      )
      is_holding = latest.get(
          "is_holding", position_status in ["HOLD", "LONG", True]
      )

      entry_p = latest.get("entry_price", 0)
      current_stop_p = latest.get(
          "current_stop_price", latest.get("current_stop_loss")
      )
      next_buy_p = latest.get("next_buy_price", latest.get("next_signal_price"))
      next_sell_p = latest.get(
          "next_sell_price", latest.get("next_signal_price")
      )

      if is_holding:
        col_a.metric(
            "當前持倉狀態",
            "持有中 (HOLD)",
            f"進場成交價: {entry_p:.2f} TWD" if entry_p else "-",
        )
        if current_stop_p and isinstance(current_stop_p, (int, float)):
          dist = ((current_stop_p - last_close) / last_close) * 100
          col_b.metric(
              "當前動態停損價",
              f"{current_stop_p:.2f} TWD",
              f"距離最新價 {dist:.2f}%",
          )
        else:
          col_b.metric("當前動態停損價", "未啟用 / 未觸發")

        if (
            next_sell_p
            and isinstance(next_sell_p, (int, float))
            and next_sell_p > 0
        ):
          col_c.metric(
              "預估平倉賣出價 (明日)",
              f"{next_sell_p:.2f} TWD",
              "跌破此價位將觸發訊號平倉",
          )
        else:
          col_c.metric("預估平倉賣出價 (明日)", "-")
      else:
        col_a.metric(
            "當前持倉狀態", "空倉 (CASH)", f"最新收盤價: {last_close:.2f} TWD"
        )
        col_b.metric("當前動態停損價", "無持倉")
        if (
            next_buy_p
            and isinstance(next_buy_p, (int, float))
            and next_buy_p > 0
        ):
          col_c.metric(
              "預估建倉買入價 (明日)",
              f"{next_buy_p:.2f} TWD",
              "突破此價位將觸發訊號建倉",
          )
        else:
          col_c.metric("預估建倉買入價 (明日)", "無有效觸發價")

      vr_status_text = (
          "量能顯著增溫"
          if last_vr >= 1.5
          else ("量能溫和" if last_vr >= 1.0 else "量能偏冷")
      )
      col_d.metric(
          "當日成交金額 / 量比",
          f"{last_val:.1f} 億 TWD",
          f"量比 {last_vr:.2f}x ({vr_status_text})",
      )

      # 🔍 【新增】當選擇 Candlestick 策略時，在下方額外提示即時 K 棒型態檢測明細
      if strategy_name == "Candlestick":
        detected_pattern = identify_pattern_combination(df)
        last_date_str = pd.to_datetime(last_date).strftime('%Y-%m-%d')
        
        if detected_pattern in selected_bullish:
          st.success(f"🟢 **【K線型態即時檢測通知】** 最新交易日 ({last_date_str}) 成功偵測到多方買進型態：**【{detected_pattern}】**！預計將於次一交易日開盤尋求建倉機會。")
        elif detected_pattern in selected_bearish:
          st.warning(f"🔴 **【K線型態即時檢測通知】** 最新交易日 ({last_date_str}) 成功偵測到空方賣出型態：**【{detected_pattern}】**！預計將於次一交易日開盤尋求平倉機會。")
        else:
          st.info(f"ℹ️ **【K線型態即時檢測通知】** 最新交易日 ({last_date_str}) 檢測結果：**無符合您勾選清單的指定型態**（當前型態：{detected_pattern}），故無預估觸發價。")

      st.divider()

      st.subheader("📊 關鍵績效指標 (KPI Summary)")
      col1, col2, col3, col4, col5 = st.columns(5)
      col1.metric("總報酬率", f"{results.get('total_return', 0)*100:.2f}%")
      col2.metric("年化報酬率", f"{results.get('cagr', 0)*100:.2f}%")
      col3.metric("最大回撤 (MDD)", f"{results.get('mdd', 0)*100:.2f}%")
      col4.metric("夏普比率 (Sharpe)", f"{results.get('sharpe', 0):.2f}")
      col5.metric("勝率 (Win Rate)", f"{results.get('win_rate', 0)*100:.1f}%")

      # --- 5. 繪製專業 K 線與成交量圖表 ---
      st.subheader("📈 專業 K 線走勢與資產變化")

      fig = make_subplots(
          rows=2,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.03,
          row_heights=[0.75, 0.25],
          specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
      )

      fig.add_trace(
          go.Candlestick(
              x=df.index,
              open=df["Open"],
              high=df["High"],
              low=df["Low"],
              close=df["Close"],
              name="K線",
              increasing_line_color="#ef5350",
              decreasing_line_color="#26a69a",
          ),
          row=1,
          col=1,
          secondary_y=False,
      )

      equity_df = results.get("equity_curve", pd.DataFrame())
      if not equity_df.empty and "Equity" in equity_df.columns:
        fig.add_trace(
            go.Scatter(
                x=equity_df.index,
                y=equity_df["Equity"],
                mode="lines",
                name="帳戶資產淨值",
                line=dict(color="#ff9800", width=2),
            ),
            row=1,
            col=1,
            secondary_y=True,
        )

      vol_colors = []
      for vr in df["Volume_Ratio"]:
        if pd.isna(vr):
          vol_colors.append("#9e9e9e")
        elif vr >= 1.5:
          vol_colors.append("#ffca28")
        elif vr < 1.0:
          vol_colors.append("#9e9e9e")
        else:
          vol_colors.append("#29b6f6")

      fig.add_trace(
          go.Bar(
              x=df.index, y=df["Volume"], name="成交量", marker_color=vol_colors
          ),
          row=2,
          col=1,
      )

      if is_holding:
        if (
            next_sell_p
            and isinstance(next_sell_p, (int, float))
            and next_sell_p > 0
        ):
          fig.add_trace(
              go.Scatter(
                  x=[last_date],
                  y=[next_sell_p],
                  mode="markers+text",
                  marker=dict(
                      symbol="arrow-down", size=14, color="#26a69a"
                  ),
                  text=["平倉價位"],
                  textposition="bottom center",
                  name="預估平倉賣出",
              ),
              row=1,
              col=1,
              secondary_y=False,
          )

        if current_stop_p and isinstance(current_stop_p, (int, float)):
          fig.add_trace(
              go.Scatter(
                  x=[last_date],
                  y=[current_stop_p],
                  mode="markers+text",
                  marker=dict(
                      symbol="line-ew",
                      size=16,
                      color="#ff9800",
                      line=dict(width=3),
                  ),
                  text=["動態停損"],
                  textposition="middle right",
                  name="當前停損防線",
              ),
              row=1,
              col=1,
              secondary_y=False,
          )
      else:
        if (
            next_buy_p
            and isinstance(next_buy_p, (int, float))
            and next_buy_p > 0
        ):
          fig.add_trace(
              go.Scatter(
                  x=[last_date],
                  y=[next_buy_p],
                  mode="markers+text",
                  marker=dict(symbol="arrow-up", size=14, color="#ef5350"),
                  text=["突破買進"],
                  textposition="top center",
                  name="預估建倉買進",
              ),
              row=1,
              col=1,
              secondary_y=False,
          )

      if stop_type == "hard":
        risk_info = f"硬停損: {stop_loss_input}%"
      elif stop_type == "trailing":
        risk_info = f"移動停損: 拉回 {trailing_pct_input}%"
      elif stop_type == "atr":
        risk_info = f"ATR 動態停損: {atr_multiplier}x ATR({atr_period})"
      else:
        risk_info = "無風控"

      param_desc = f"策略: {strategy_name} | 參數: {strategy_kwargs}"
      perf_desc = (
          f"總報酬率: {results.get('total_return', 0)*100:.2f}% | "
          f"年化報酬: {results.get('cagr', 0)*100:.2f}% | "
          f"MDD: {results.get('mdd', 0)*100:.2f}% | "
          f"夏普: {results.get('sharpe', 0):.2f}"
      )

      fig.update_layout(
          title=dict(
              text=(
                  f"<b>{stock_display_name} 策略回測報告</b><br>"
                  f"<sub style='color:gray;'>{param_desc} | "
                  f"風控模式: {risk_info}</sub><br>"
                  f"<sub style='color:darkgreen;'>{perf_desc}</sub>"
              ),
              font=dict(size=14),
          ),
          height=850,
          hovermode="x unified",
          xaxis_rangeslider_visible=False,
          legend=dict(x=0.01, y=0.95, bgcolor="rgba(255,255,255,0.7)"),
      )

      fig.update_yaxes(
          title_text="股價 (TWD)", row=1, col=1, secondary_y=False
      )
      fig.update_yaxes(
          title_text="總資產 (TWD)",
          row=1,
          col=1,
          secondary_y=True,
          showgrid=False,
      )
      fig.update_yaxes(title_text="成交量", row=2, col=1)

      st.plotly_chart(fig, use_container_width=True)

      st.markdown("---")
      col_dl1, col_dl2 = st.columns([3, 1])
      with col_dl1:
        st.info(
            "💡 點擊右側按鈕可將當前帶有「完整策略條件、參數、風控與 KPI 績效摘要」的圖表匯出為"
            " PNG 高畫質圖片檔案。"
        )
      with col_dl2:
        try:
          img_bytes = fig.to_image(format="png", width=1200, height=850, scale=2)
          st.download_button(
              label="📥 下載回測圖表與條件 (PNG)",
              data=img_bytes,
              file_name=f"backtest_{ticker}_{strategy_name}.png",
              mime="image/png",
              type="primary",
          )
        except Exception as e:
          st.warning(
              "⚠️ 如需一鍵下載 PNG 圖片，請確認已安裝 kaleido 模組 (`pip"
              " install kaleido`)。您目前仍可透過右上角內建相機圖示截圖。"
          )
import os
import pandas as pd
import yfinance as yf
import config

# 自動相容 Streamlit 環境與純 Python 多進程腳本
try:
    import streamlit as st
    cache_decorator = st.cache_data(ttl=86400, show_spinner=False)
except ImportError:
    cache_decorator = lambda func: func


@cache_decorator
def load_price_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    從 yfinance 下載歷史行情數據，並清洗成 Backtrader 可讀取的標準 OHLCV 格式。
    預設包含本地 Parquet 檔案快取與例外處理。
    """
    cache_file = os.path.join(config.DATA_CACHE_DIR, f"{ticker}_{start_date}_{end_date}.parquet")
    
    # 1. 優先讀取本地快取
    if os.path.exists(cache_file):
        try:
            return pd.read_parquet(cache_file)
        except Exception:
            pass  # 若快取損壞則重新下載

    # 2. 下載 yfinance 數據
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True, progress=False)
    
    if df is None or df.empty:
        raise ValueError(f"無法取得 {ticker} 的歷史行情數據，請檢查股票代碼或日期範圍。")

    # 3. 處理 yfinance 新版 API 傳回 MultiIndex 欄位的狀況
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.levels[1]:
            df = df.xs(ticker, axis=1, level=1)
        else:
            df = df.droplevel(1, axis=1)

    # 4. 欄位清洗與格式轉型
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"行情數據缺少必要欄位: {col}")

    df_clean = df[required_cols].copy()
    df_clean = df_clean.dropna()
    df_clean.index = pd.to_datetime(df_clean.index)
    df_clean = df_clean.sort_index()

    # 5. 寫入本地 Parquet 快取
    try:
        os.makedirs(config.DATA_CACHE_DIR, exist_ok=True)
        df_clean.to_parquet(cache_file)
    except Exception as e:
        print(f"快取寫入失敗 (非致命錯誤): {str(e)}")

    return df_clean
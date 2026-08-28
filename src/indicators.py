import pandas as pd

def add_volume_ratio(df: pd.DataFrame, sma_period: int = 20) -> pd.DataFrame:
    """
    計算成交金額與量比，並直接擴充 DataFrame 欄位
    """
    df = df.copy()
    # 計算成交金額
    df["Trading_Value"] = df["Volume"] * df["Close"]
    
    # 計算成交量均線與量比
    df["Vol_SMA"] = df["Volume"].rolling(window=sma_period).mean()
    df["Volume_Ratio"] = df["Volume"] / df["Vol_SMA"]
    
    return df
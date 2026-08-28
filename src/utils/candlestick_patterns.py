import pandas as pd


def identify_pattern_combination(df_subset):
  """依據 7 種經典 K 棒組合圖譜，辨識核心多空型態

  多方買進型態圖解參考：
    1. 啟明之星:
       [跌黑K] -> [小實體] -> [漲紅K]
          ░░         □          ██
          ░░                    ██

    2. 紅三兵:
       [漲紅K] -> [漲紅K] -> [漲紅K]
          ██         ██          ██
          ██         ██          ██

    3. 旭日東升（含曙光初現）:
       [跌黑K] -> [漲紅K]
          ░░         ██
          ░░         ██

    4. 好友反攻:
       [跌黑K] -> [漲紅K]
          ░░         ██
          ░░         ██

  空方賣出型態圖解參考：
    5. 黃昏之星:
       [漲紅K] -> [小實體] -> [跌黑K]
          ██         □          ░░
          ██                    ░░

    6. 黑三兵:
       [跌黑K] -> [跌黑K] -> [跌黑K]
          ░░         ░░          ░░
          ░░         ░░          ░░

    7. 烏雲蓋頂:
       [漲紅K] -> [跌黑K]
          ██         ░░
          ██         ░░
  """
  n = len(df_subset)
  if n < 3:
    return "無"

  # 提取最後 3 根 K 棒資料
  c_candles = []
  for i in range(-3, 0):
    row = df_subset.iloc[i]
    c_candles.append({
        "O": row["Open"],
        "H": row["High"],
        "L": row["Low"],
        "C": row["Close"],
        "is_green": row["Close"] < row["Open"],  # 綠 = 跌/陰線
        "is_red": row["Close"] > row["Open"],  # 紅 = 漲/陽線
    })

  curr = c_candles[-1]
  prev1 = c_candles[-2]
  prev2 = c_candles[-3]

  # --- 三根 K 棒核心型態 ---
  # 啟明之星 (看漲)
  if (
      prev2["is_green"]
      and abs(prev1["C"] - prev1["O"]) <= (prev1["H"] - prev1["L"]) * 0.3
      and curr["is_red"]
      and curr["C"] >= (prev2["O"] + prev2["C"]) / 2
  ):
    return "啟明之星"

  # 黃昏之星 (看跌)
  if (
      prev2["is_red"]
      and abs(prev1["C"] - prev1["O"]) <= (prev1["H"] - prev1["L"]) * 0.3
      and curr["is_green"]
      and curr["C"] <= (prev2["O"] + prev2["C"]) / 2
  ):
    return "黃昏之星"

  # 紅三兵 (看漲)
  if (
      prev2["is_red"]
      and prev1["is_red"]
      and curr["is_red"]
      and prev1["C"] > prev2["C"]
      and curr["C"] > prev1["C"]
  ):
    return "紅三兵"

  # 黑三兵 (看跌)
  if (
      prev2["is_green"]
      and prev1["is_green"]
      and curr["is_green"]
      and prev1["C"] < prev2["C"]
      and curr["C"] < prev1["C"]
  ):
    return "黑三兵"

  # --- 雙根 K 棒核心型態 ---
  # 旭日東升 / 曙光初現 (看漲)
  if prev1["is_green"] and curr["is_red"] and curr["C"] >= prev1["O"]:
    return "旭日東升"

  # 烏雲蓋頂 (看跌)
  if (
      prev1["is_red"]
      and curr["is_green"]
      and curr["C"] <= (prev1["O"] + prev1["C"]) / 2
  ):
    return "烏雲蓋頂"

  # 好友反攻 (看漲)
  if (
      prev1["is_green"]
      and curr["is_red"]
      and abs(curr["C"] - prev1["C"])
      <= (prev1["H"] - prev1["L"]) * 0.1
  ):
    return "好友反攻"

  return "一般型態"
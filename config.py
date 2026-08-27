import os
from datetime import datetime

# --- 全域台股交易成本設定 ---
TAIWAN_COMMISSION_RATE = 0.001425  # 券商基本手續費率 (0.1425%)
DEFAULT_DISCOUNT = 0.6             # 手續費預設折扣 (6 折)
MIN_COMMISSION_TWD = 20            # 最低手續費 (新台幣 20 元)
TAIWAN_TAX_RATE = 0.003            # 賣出證券交易稅 (0.3%)

# --- 預設回測與個股設定 ---
DEFAULT_INITIAL_CASH = 1000000.0   # 初始資金 (台幣 100 萬)
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = datetime.now().strftime("%Y-%m-%d")
DEFAULT_TICKER = "2308.TW"         # 單次測試標的 (預設台達電)

# --- 預設策略與風控設定 ---
DEFAULT_STRATEGY_NAME = "SMACross"
DEFAULT_FAST_PERIOD = 20
DEFAULT_SLOW_PERIOD = 60

# 📌 模組化風控設定
# STOP_TYPE 可選: 
#  - 'hard': 固定百分比停損
#  - 'trailing': 最高價拉回移動停損 (Trailing Stop)
#  - 'atr': 真實波動區間動態停損 (ATR Stop)
DEFAULT_STOP_TYPE = "atr"          
DEFAULT_STOP_LOSS = 0.07           # 硬停損比例 (當 STOP_TYPE='hard' 時生效)
DEFAULT_ATR_PERIOD = 14            # ATR 計算週期
DEFAULT_ATR_MULTIPLIER = 2.0       # ATR 倍數 (當 STOP_TYPE='atr' 時生效，常見 1.5~3.0)
DEFAULT_TRAILING_PCT = 0.05        # 移動停損拉回比例 (當 STOP_TYPE='trailing' 時生效)

# --- 資料夾目錄與快取設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")

# 自動創建本地數據快取目錄
os.makedirs(DATA_CACHE_DIR, exist_ok=True)
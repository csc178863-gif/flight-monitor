"""監控設定：出發地、目的地、日期窗口、旅遊晚數與票價門檻。"""

from datetime import date, timedelta

# ── 出發機場 ──────────────────────────────────────────
ORIGINS = {
    "KHH": "高雄",
    "RMQ": "台中",
    "TPE": "桃園",
}

# ── 目的地（日本）─────────────────────────────────────
# TYO = 東京（成田＋羽田）
# OSA = 大阪（關西＋伊丹）
DESTS = {
    "OKA": "沖繩",
    "ISG": "石垣島",
    "NGO": "名古屋",
    "FUK": "福岡",
    "TYO": "東京",
    "OSA": "大阪",
    "CTS": "札幌",
}

# ── 出發日期窗口：包含開始日與結束日 ───────────────────
# 出發日期為 2027/01/23～2027/02/01；回程日期依晚數延伸。
WINDOW_START = date(2027, 1, 23)
WINDOW_END = date(2027, 2, 1)

# ── 旅遊晚數：7、8、9 晚 ──────────────────────────────
MIN_NIGHTS = 7
MAX_NIGHTS = 9

# 保留此變數，降低其他程式若仍引用 NIGHTS 時的不相容風險。
# 實際日期組合以 date_pairs() 為準。
NIGHTS = 7

# ── 價格門檻（新台幣，來回含稅）───────────────────────
THRESHOLD_TWD = 20000

# ── 轉機限制 ──────────────────────────────────────────
# 0 = 去程與回程都要求直飛；None = 不限制轉機次數
MAX_STOPS = 0

# ── 幣別與語言 ────────────────────────────────────────
CURRENCY = "TWD"
LANGUAGE = "zh-TW"

# ── LINE 推播服務設定（沿用原本設定）───────────────────
GMN_PUSH_URL = "https://finance-dashboard-dun-ten-84.vercel.app/api/gmn-push"

# ── 禮貌性延遲（秒），避免被 Google 限流 ───────────────
DELAY_MIN = 2.0
DELAY_MAX = 5.0


def date_pairs():
    """產生所有（出發日、回程日）組合：出發日期含首尾，旅遊 7～9 晚。"""
    pairs = []
    departure_date = WINDOW_START

    while departure_date <= WINDOW_END:
        for nights in range(MIN_NIGHTS, MAX_NIGHTS + 1):
            return_date = departure_date + timedelta(days=nights)
            pairs.append((departure_date, return_date))
        departure_date += timedelta(days=1)

    return pairs

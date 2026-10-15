
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
# 沒有符合條件的直飛航班時，由監控程式依原有邏輯處理。
DESTS = {
    "OKA": "沖繩",
    "ISG": "石垣島",
    "NGO": "名古屋",
    "FUK": "福岡",
    "TYO": "東京",
    "OSA": "大阪",
    "CTS": "札幌",
}

# ── 出發日期窗口 ──────────────────────────────────────
# 最早出發日：2027/01/23
# 最晚出發日：2027/02/01（包含當天）
WINDOW_START = date(2027, 1, 23)
WINDOW_END = date(2027, 2, 1)

# ── 旅遊晚數 ──────────────────────────────────────────
MIN_NIGHTS = 7
MAX_NIGHTS = 9

# 保留 NIGHTS，避免其他程式若仍引用此變數時發生錯誤。
# 實際日期組合由下方 date_pairs() 產生 7、8、9 晚。
NIGHTS = 7

# ── 價格門檻（新台幣，來回含稅）───────────────────────
THRESHOLD_TWD = 20000

# ── 轉機限制 ──────────────────────────────────────────
# 0 = 去程與回程都必須直飛
# None = 不限制轉機次數
MAX_STOPS = 0

# ── 幣別與語言 ────────────────────────────────────────
CURRENCY = "TWD"
LANGUAGE = "zh-TW"

# ── LINE 推播（沿用原本的推播服務）────────────────────
GMN_PUSH_URL = (
    "https://finance-dashboard-dun-ten-84.vercel.app/api/gmn-push"
)

# ── 禮貌性延遲（秒），避免被 Google 限流 ───────────────
DELAY_MIN = 2.0
DELAY_MAX = 5.0


def date_pairs():
    """
    產生所有（出發日、回程日）組合。

    出發日期：2027/01/23～2027/02/01，包含首尾兩天。
    旅遊晚數：7、8、9 晚。
    回程日依各組合的出發日與旅遊晚數計算。
    """
    pairs = []
    departure_date = WINDOW_START

    while departure_date <= WINDOW_END:
        for nights in range(MIN_NIGHTS, MAX_NIGHTS + 1):
            return_date = departure_date + timedelta(days=nights)
            pairs.append((departure_date, return_date))

        departure_date += timedelta(days=1)

    return pairs

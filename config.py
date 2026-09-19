"""監控設定：出發地、目的地、日期窗口、門檻。改這裡就好，不用動 monitor.py。"""

from datetime import date, timedelta

# ── 出發機場（台灣南部）────────────────────────────────
ORIGINS = {
    "KHH": "高雄",
    "RMQ": "台中",
}

# ── 目的地（日本，用大城市/都會代碼，涵蓋該區多個機場）──
# TYO=東京(成田+羽田)、OSA=大阪(關西+伊丹)，其餘為單一主要機場
DESTS = {
    "TYO": "東京",
    "OSA": "大阪",
    "FUK": "福岡",
    "OKA": "沖繩",
    "NGO": "名古屋",
}

# ── 日期窗口：一週 = 7 晚，回程不得晚於 2027-02-10 ──────
WINDOW_START = date(2027, 1, 28)   # 最早出發日
WINDOW_END = date(2027, 2, 10)     # 最晚回程日
NIGHTS = 7                          # 一週

# ── 價格門檻（台幣，來回含稅）──────────────────────────
THRESHOLD_TWD = 17000

# ── 轉機限制：0 = 只要直飛（去程/回程皆直飛）；None = 不限 ──
MAX_STOPS = 0

# ── 幣別與語言 ─────────────────────────────────────────
CURRENCY = "TWD"
LANGUAGE = "zh-TW"

# ── LINE 推播（沿用 finance-dashboard 的 /api/gmn-push）──
GMN_PUSH_URL = "https://finance-dashboard-dun-ten-84.vercel.app/api/gmn-push"

# ── 禮貌性延遲（秒），避免被 Google 限流 ───────────────
DELAY_MIN = 2.0
DELAY_MAX = 5.0


def date_pairs():
    """產生所有 (出發日, 回程日) 組合：出發日從 WINDOW_START 起，
    回程 = 出發 + NIGHTS，且回程 <= WINDOW_END。"""
    pairs = []
    d = WINDOW_START
    while d + timedelta(days=NIGHTS) <= WINDOW_END:
        pairs.append((d, d + timedelta(days=NIGHTS)))
        d += timedelta(days=1)
    return pairs

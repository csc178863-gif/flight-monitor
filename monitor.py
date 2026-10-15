
#!/usr/bin/env python3
"""日本機票監控：掃過設定的出發機場 × 日期窗口 × 日本各區，
找出符合預算（THRESHOLD_TWD）的來回票，並排除可辨識的廉價航空。

LINE 通知規則：
1. 日期組合首次達到門檻（票價 <= THRESHOLD_TWD）時通知。
2. 已通知過的日期組合，之後只有在達標且刷新歷史最低價時再次通知。
3. 票價高於門檻時不通知，即使刷新歷史最低價也不通知。
4. 票價反彈高於門檻時，保留已通知紀錄，避免再次跌回門檻時重複通知。
5. ALWAYS_REPORT=1 可強制回報目前全窗口最低票價。

廉航過濾：
在挑選每個日期組合的最低票價前，排除能從航空公司名稱或代碼辨識的廉航。
若航空公司資訊缺失或無法辨識，則保留該結果，避免誤刪傳統航空。

狀態存在 state.json，每個組合分別保存歷史最低價與通知紀錄。

用法：
    python monitor.py
    DRY_RUN=1 python monitor.py
    ALWAYS_REPORT=1 python monitor.py
"""

import json
import os
import random
import sys
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import requests
from fast_flights import create_query, get_flights, FlightQuery, Passengers

import config

STATE_FILE = Path(__file__).parent / "state.json"
TPE = timezone(timedelta(hours=8))

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
ALWAYS_REPORT = os.environ.get("ALWAYS_REPORT", "").lower() in ("1", "true", "yes")

# LINE Messaging API 設定（從 GitHub Repository Secrets 讀取）
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")


# ── 廉航辨識 ───────────────────────────────────────────
# 航空公司名稱可能因資料來源不同而使用英文、縮寫或品牌名稱。
# 以下清單涵蓋多家常見廉航；不是全球完整名單。
LOW_COST_AIRLINES = (
    # 台灣、日本及東亞
    "tigerair", "台灣虎航", "台湾虎航",
    "peach", "樂桃", "乐桃",
    "jetstar", "捷星",
    "spring airlines", "spring japan", "春秋航空",
    "zipair", "zip air",
    "airasia", "air asia",
    "vietjet", "越捷",
    "hk express", "hong kong express", "香港快運",
    "scoot", "酷航",
    "cebu pacific", "宿霧太平洋",
    "indigo", "interglobe aviation",
    "spicejet",
    "go first",
    "batik air",
    "lion air",
    "citilink",
    "firefly",
    "malindo air",
    "nokscoot",
    "noks air",
    "t'way", "tway", "德威航空",
    "jin air", "真航空",
    "jeju air", "濟州航空", "济州航空",
    "air busan", "釜山航空",
    "eastar jet", "易斯達航空",
    "aero k",
    "air premia",
    "peach aviation",
    "air do", "airdo",
    "solaseed air",
    "starflyer",
    "skymark",
    "spring airlines japan",

    # 歐洲
    "ryanair",
    "easyjet", "easy jet",
    "wizz air", "wizzair",
    "vueling",
    "volotea",
    "transavia",
    "jet2",
    "norwegian air",
    "eurowings",
    "flybe",
    "play airlines",
    "french bee",
    "condor",

    # 北美
    "southwest airlines",
    "spirit airlines",
    "frontier airlines",
    "allegiant air",
    "sun country airlines",
    "breeze airways",
    "aer lingus",

    # 中東及其他地區
    "air arabia",
    "flydubai",
    "flynas",
    "flyadeal",
    "pegasus airlines",
    "sunexpress",
    "azul brazil",
    "gol airlines",
    "jetblue",
)

# 航空公司代碼：只有在資料明確提供代碼時才用代碼判斷。
# 代碼清單並非完整；名稱比對仍會優先使用。
LOW_COST_CODES = {
    "IT",  # 台灣虎航
    "MM",  # 樂桃
    "GK",  # 捷星日本
    "JQ",  # 捷星
    "3K",  # 捷星亞洲
    "9C",  # 春秋航空
    "IJ",  # 春秋航空日本
    "ZG",  # ZIPAIR
    "TR",  # 酷航
    "AK",  # AirAsia
    "D7",  # AirAsia X
    "FD",  # Thai AirAsia
    "QZ",  # Indonesia AirAsia
    "VJ",  # VietJet
    "VZ",  # Thai VietJet
    "UO",  # HK Express
    "5J",  # Cebu Pacific
    "6E",  # IndiGo
    "SG",  # SpiceJet
    "7C",  # Jeju Air
    "TW",  # T'way Air
    "LJ",  # Jin Air
    "BX",  # Air Busan
    "ZE",  # Eastar Jet
    "RF",  # Aero K
    "FR",  # Ryanair
    "U2",  # easyJet
    "W6",  # Wizz Air
    "VY",  # Vueling
    "LS",  # Jet2
    "HV",  # Transavia
    "DY",  # Norwegian
    "F9",  # Frontier
    "NK",  # Spirit
    "WN",  # Southwest
    "G4",  # Allegiant
    "SY",  # Sun Country
    "PC",  # Pegasus
    "G9",  # Air Arabia
}


def _airline_names(airlines):
    """將航空公司資料轉成可比對的名稱清單。"""

    if not airlines:
        return []

    if isinstance(airlines, str):
        items = [airlines]
    else:
        try:
            items = list(airlines)
        except TypeError:
            items = [airlines]

    names = []

    for item in items:
        if item is None:
            continue

        # 若來源回傳的是航空公司物件，嘗試取名稱或代碼。
        if isinstance(item, str):
            name = item
        else:
            name = (
                getattr(item, "name", None)
                or getattr(item, "code", None)
                or str(item)
            )

        name = str(name).strip()
        if name:
            names.append(name)

    return names


def _is_low_cost(airlines):
    """只要其中一家航空公司可辨識為廉航，就排除該票價結果。"""

    names = _airline_names(airlines)

    # 航空公司資訊缺失時無法可靠判定，不直接排除。
    if not names:
        return False

    for name in names:
        normalized = name.casefold().replace("_", " ").strip()
        compact = "".join(ch for ch in normalized if ch.isalnum())

        # 比對已知廉航名稱及常見品牌名稱。
        for keyword in LOW_COST_AIRLINES:
            keyword_normalized = keyword.casefold().replace("_", " ").strip()
            keyword_compact = "".join(
                ch for ch in keyword_normalized if ch.isalnum()
            )

            if keyword_normalized in normalized or (
                keyword_compact and keyword_compact in compact
            ):
                return True

        # 只在名稱本身是兩字元航空公司代碼時判斷，降低誤判。
        if normalized.upper() in LOW_COST_CODES:
            return True

        # 兼容「航空公司名稱（代碼）」等格式。
        import re

        codes = re.findall(r"\b[A-Z0-9]{2}\b", name.upper())
        if any(code in LOW_COST_CODES for code in codes):
            return True

    return False


# ── 狀態讀寫 ───────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("⚠️ state.json 格式錯誤，將使用空白狀態。")

    return {"threshold_twd": config.THRESHOLD_TWD, "combos": {}}


def save_state(state):
    state["updated"] = datetime.now(TPE).isoformat(timespec="seconds")
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── 抓單一組合的最低價 ─────────────────────────────────
def fetch_combo(origin, dest, dep, ret):
    """回傳排除可辨識廉航後的最低來回結果，抓不到回 None。"""

    q = create_query(
        flights=[
            FlightQuery(
                date=dep.isoformat(),
                from_airport=origin,
                to_airport=dest,
                max_stops=config.MAX_STOPS,
            ),
            FlightQuery(
                date=ret.isoformat(),
                from_airport=dest,
                to_airport=origin,
                max_stops=config.MAX_STOPS,
            ),
        ],
        trip="round-trip",
        seat="economy",
        passengers=Passengers(adults=1),
        currency=config.CURRENCY,
        language=config.LANGUAGE,
    )

    res = get_flights(q)

    # 先過濾無效價格，再排除可辨識廉航，最後才挑選最低價。
    priced = [
        f for f in res
        if isinstance(getattr(f, "price", None), int)
        and f.price > 0
        and not _is_low_cost(getattr(f, "airlines", None))
    ]

    if not priced:
        return None

    best = min(priced, key=lambda f: f.price)

    info = {
        "price": best.price,
        "airlines": "／".join(_airline_names(best.airlines)) or "—",
        "code": getattr(best, "type", "") or "",
        "stops": max(0, len(best.flights) - 1),
        "out_from": "",
        "out_to": "",
        "out_dep": "",
        "out_arr": "",
        "out_dur": "",
        "plane": "",
        "url": q.url(),
    }

    try:
        leg = best.flights[0]
        dt, at = leg.departure.time, leg.arrival.time

        info["out_from"] = getattr(leg.from_airport, "code", origin)
        info["out_to"] = getattr(leg.to_airport, "code", dest)
        info["out_dep"] = f"{dt[0]:02d}:{dt[1]:02d}"
        info["out_arr"] = f"{at[0]:02d}:{at[1]:02d}"

        d = leg.duration or 0
        info["out_dur"] = f"{d // 60}h{d % 60:02d}m"
        info["plane"] = leg.plane_type or ""

    except Exception:
        pass

    return info


# ── 訊息排版 ───────────────────────────────────────────
def _md(iso):
    """'2027-01-28' -> '1/28'."""
    try:
        _, m, d = iso.split("-")
        return f"{int(m)}/{int(d)}"
    except Exception:
        return iso


def _detail_block(r):
    """完整航班資訊區塊（多行）。"""

    stops = "直飛" if r.get("stops", 0) == 0 else f"轉機 {r['stops']} 次"
    code = f" {r['code']}" if r.get("code") else ""

    lines = [
        f"🛫 {r['o_name']} {r['origin']} → {r['d_name']} {r['dest']}",
        (
            f"📅 去 {_md(r['dep'])} → 回 {_md(r['ret'])}"
            f"（{(date.fromisoformat(r['ret']) - date.fromisoformat(r['dep'])).days} 晚）"
        ),
        f"✈️ {r['airlines']}{code}｜{stops}",
    ]

    if r.get("out_dep"):
        plane = f", {r['plane']}" if r.get("plane") else ""
        lines.append(
            f"　去程 {r['out_from']} {r['out_dep']} → "
            f"{r['out_to']} {r['out_arr']}"
            f"（{r['out_dur']}{plane}）"
        )

    lines.append("　回程 訂票頁選（此為來回總價）")

    return lines


def _one_liner(r):
    """其他達標的一行摘要（含去回程日期及班次時間）。"""

    seg = f" {r['out_dep']}→{r['out_arr']}" if r.get("out_dep") else ""

    return (
        f"• 去 {_md(r['dep'])} 回 {_md(r['ret'])}｜"
        f"{r['o_name']}{r['origin']}→{r['d_name']}{r['dest']} "
        f"NT${r['price']:,}｜{r['airlines']}{seg}"
    )


def build_message(hits, cheapest):
    """hits：這次觸發推播的組合；cheapest：全窗口最低票價。"""

    lines = []

    if hits:
        top = hits[0]

        lines.append(
            f"✈️ 日本機票監控｜{len(hits)} 個達標"
            f"（≤ NT${config.THRESHOLD_TWD:,}，已排除可辨識廉航）"
        )
        lines.append("")
        lines.append(f"💰 最低 NT${top['price']:,}")
        lines += _detail_block(top)
        lines.append("")
        lines.append("🔗 訂票（Google Flights，可選回程）")
        lines.append(top["url"])

        if len(hits) > 1:
            lines.append("")
            lines.append("其他達標：")

            for h in hits[1:8]:
                lines.append(_one_liner(h))

            if len(hits) > 8:
                lines.append(f"（另有 {len(hits) - 8} 組達標組合未列出）")

    else:
        lines.append("✈️ 日本機票監控｜目前無達標票（回報現況）")
        lines.append("（已排除可辨識的廉價航空）")
        lines.append("")

        if cheapest:
            lines.append(
                f"💡 目前全窗口最低 NT${cheapest['price']:,}"
                f"（目標 NT${config.THRESHOLD_TWD:,}）"
            )
            lines += _detail_block(cheapest)
            lines.append("")
            lines.append("🔗 訂票（Google Flights，可選回程）")
            lines.append(cheapest["url"])

        else:
            lines.append("（這輪沒有符合篩選條件的有效票價）")

    lines.append("")
    lines.append("⚠️ 過年檔期價格變動快，看到好價建議盡快下手")

    return "\n".join(lines)


# ── LINE Messaging API 推播 ────────────────────────────

def push_line(message):
    """使用 LINE Broadcast API，推播給已加入官方帳號好友且可接收訊息的使用者。"""

    if DRY_RUN:
        print("── [DRY_RUN] 以下訊息不會送出 ──\n" + message)
        return

    if not LINE_CHANNEL_ACCESS_TOKEN:
        print(
            "⚠️ 缺少 LINE_CHANNEL_ACCESS_TOKEN，"
            "跳過推播。請檢查 GitHub Repository Secrets。"
        )
        return

    if len(message) > 4900:
        message = message[:4900] + "\n（訊息過長，已截斷）"

    # 改用 Broadcast：不再指定單一 LINE_USER_ID
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messages": [
            {
                "type": "text",
                "text": message,
            }
        ],
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        print(f"LINE 廣播推播結果 HTTP {response.status_code}")

        if not response.ok:
            print(f"LINE API 錯誤訊息：{response.text[:1000]}")

        response.raise_for_status()
        print("✅ LINE 廣播推播請求成功。")

    except requests.RequestException as e:
        print(f"❌ LINE 廣播推播失敗：{type(e).__name__}: {e}")
        raise


# ── 主流程 ─────────────────────────────────────────────
def main():
    state = load_state()
    state["threshold_twd"] = config.THRESHOLD_TWD
    combos = state.setdefault("combos", {})
    now_iso = datetime.now(TPE).isoformat(timespec="seconds")

    hits = []
    all_priced = []
    pairs = config.date_pairs()

    total = len(config.ORIGINS) * len(config.DESTS) * len(pairs)

    print(
        f"開始掃描：{total} 個組合（{len(config.ORIGINS)} 出發 × "
        f"{len(config.DESTS)} 目的地 × {len(pairs)} 組日期）"
        f"門檻 NT${config.THRESHOLD_TWD:,}；排除可辨識廉航"
    )

    i = 0

    for origin, o_name in config.ORIGINS.items():
        for dest, d_name in config.DESTS.items():
            for dep, ret in pairs:
                i += 1

                key = f"{origin}-{dest}-{dep.isoformat()}-{ret.isoformat()}"

                try:
                    r = fetch_combo(origin, dest, dep, ret)

                except Exception as e:
                    print(
                        f"[{i}/{total}] {key} 抓取失敗："
                        f"{type(e).__name__}: {e}"
                    )
                    time.sleep(
                        random.uniform(config.DELAY_MIN, config.DELAY_MAX)
                    )
                    continue

                if not r:
                    print(
                        f"[{i}/{total}] {key} 無符合條件的票價"
                        "（可能無票、只有廉航或抓取資料不足）"
                    )
                    time.sleep(
                        random.uniform(config.DELAY_MIN, config.DELAY_MAX)
                    )
                    continue

                price = r["price"]

                rec = {
                    "origin": origin,
                    "o_name": o_name,
                    "dest": dest,
                    "d_name": d_name,
                    "dep": dep.isoformat(),
                    "ret": ret.isoformat(),
                    **r,
                }

                all_priced.append(rec)

                prev = combos.get(key, {})

                # 相容舊版 state.json：舊版固定 7 晚。
                if not prev and (ret - dep).days == 7:
                    legacy_key = f"{origin}-{dest}-{dep.isoformat()}"
                    prev = combos.get(legacy_key, {})

                prev_low = prev.get("lowest_twd")
                prev_alerted = prev.get("below_threshold_alerted", False)

                is_new_low = prev_low is None or price < prev_low
                below = price <= config.THRESHOLD_TWD

                # 保留原本的通知判斷邏輯。
                trigger = below and (not prev_alerted or is_new_low)

                lowest_twd = (
                    min(price, prev_low)
                    if prev_low is not None
                    else price
                )

                combos[key] = {
                    "lowest_twd": lowest_twd,
                    "last_twd": price,
                    "below_threshold_alerted": prev_alerted or below,
                    "last_seen": now_iso,
                }

                tag = ""

                if trigger:
                    hits.append(rec)
                    tag = " 🔔達標觸發"
                elif is_new_low:
                    tag = " ↓新低"

                print(f"[{i}/{total}] {key} NT${price:,}{tag}")

                time.sleep(
                    random.uniform(config.DELAY_MIN, config.DELAY_MAX)
                )

    hits.sort(key=lambda h: h["price"])
    all_priced.sort(key=lambda h: h["price"])
    cheapest = all_priced[0] if all_priced else None

    cheapest_text = f"NT${cheapest['price']:,}" if cheapest else "—"

    print(
        f"\n掃描完成：抓到 {len(all_priced)} 筆符合條件的有效票價，"
        f"{len(hits)} 筆達標觸發。"
        f"全窗口最低 {cheapest_text}"
    )

    save_state(state)

    if hits:
        push_line(build_message(hits, cheapest))

    elif ALWAYS_REPORT:
        push_line(build_message([], cheapest))

    else:
        print("無達標票，不推播。")


if __name__ == "__main__":
    sys.exit(main())


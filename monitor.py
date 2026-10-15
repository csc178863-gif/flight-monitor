
#!/usr/bin/env python3
"""日本機票監控：掃過設定的出發機場 × 日期窗口 × 日本各區，
找出符合預算（THRESHOLD_TWD）的來回票。

LINE 通知規則：
1. 日期組合首次達到門檻（票價 <= THRESHOLD_TWD）時通知。
2. 已通知過的日期組合，之後只有在達標且刷新歷史最低價時再次通知。
3. 票價高於門檻時不通知，即使刷新歷史最低價也不通知。
4. 票價反彈高於門檻時，保留已通知紀錄，避免再次跌回門檻時重複通知。
5. ALWAYS_REPORT=1 可強制回報目前全窗口最低票價。

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
    """回傳最便宜的來回結果 dict，抓不到回 None。"""

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

    priced = [
        f for f in res
        if isinstance(getattr(f, "price", None), int) and f.price > 0
    ]

    if not priced:
        return None

    best = min(priced, key=lambda f: f.price)

    info = {
        "price": best.price,
        "airlines": "／".join(best.airlines) if best.airlines else "—",
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
    """其他達標的一行摘要（含班次時間）。"""

    seg = f" {r['out_dep']}→{r['out_arr']}" if r.get("out_dep") else ""

    return (
        f"• {r['o_name']}{r['origin']}→{r['d_name']}{r['dest']} "
        f"NT${r['price']:,}｜{r['airlines']}{seg}"
    )


def build_message(hits, cheapest):
    """hits：這次觸發推播的組合；cheapest：全窗口最便宜的票。"""

    lines = []

    if hits:
        top = hits[0]

        lines.append(
            f"✈️ 日本機票監控｜{len(hits)} 個達標"
            f"（≤ NT${config.THRESHOLD_TWD:,}）"
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

    else:
        lines.append("✈️ 日本機票監控｜目前無達標票（回報現況）")
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
            lines.append("（這輪沒抓到任何有效票價，可能被限流或無航班）")

    lines.append("")
    lines.append("⚠️ 過年檔期價格變動快，看到好價建議盡快下手")

    return "\n".join(lines)


# ── LINE Messaging API 推播 ────────────────────────────
def push_line(message):
    """使用 LINE Messaging API，將文字訊息推播給指定的 LINE 使用者。"""

    if DRY_RUN:
        print("── [DRY_RUN] 以下訊息不會送出 ──\n" + message)
        return

    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print(
            "⚠️ 缺少 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，"
            "跳過推播。請檢查 GitHub Repository Secrets。"
        )
        return

    # LINE 單則文字訊息上限為 5000 字元，預留部分空間避免超限
    if len(message) > 4900:
        message = message[:4900] + "\n（訊息過長，已截斷）"

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "to": LINE_USER_ID,
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

        print(f"LINE 推播結果 HTTP {response.status_code}")

        if not response.ok:
            print(f"LINE API 錯誤訊息：{response.text[:1000]}")

        response.raise_for_status()
        print("✅ LINE 推播請求成功。")

    except requests.RequestException as e:
        print(f"❌ LINE 推播失敗：{type(e).__name__}: {e}")
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
        f"門檻 NT${config.THRESHOLD_TWD:,}"
    )

    i = 0

    for origin, o_name in config.ORIGINS.items():
        for dest, d_name in config.DESTS.items():
            for dep, ret in pairs:
                i += 1

                # 每組去回程日期使用獨立識別碼，避免 7/8/9 晚價格紀錄互相覆蓋。
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
                    print(f"[{i}/{total}] {key} 無票價")
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

                # 相容舊版 state.json：
                # 舊版只用出發日作為 key，原本固定 7 晚。
                # 只有 7 晚組合尚無新紀錄時，才沿用舊紀錄。
                if not prev and (ret - dep).days == 7:
                    legacy_key = f"{origin}-{dest}-{dep.isoformat()}"
                    prev = combos.get(legacy_key, {})

                prev_low = prev.get("lowest_twd")
                prev_alerted = prev.get("below_threshold_alerted", False)

                is_new_low = prev_low is None or price < prev_low
                below = price <= config.THRESHOLD_TWD

                # 通知規則：
                # 1. 首次達到門檻時通知。
                # 2. 已通知過，且目前達標並刷新歷史最低價時再次通知。
                # 3. 價格反彈超過門檻時，保留已通知紀錄。
                trigger = below and (not prev_alerted or is_new_low)

                # 保留歷史最低價；不能用 prev_low 的真假值判斷是否存在，
                # 必須明確檢查 None。
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

                print(f"[{i}/{total}] {key}  NT${price:,}{tag}")

                time.sleep(
                    random.uniform(config.DELAY_MIN, config.DELAY_MAX)
                )

    hits.sort(key=lambda h: h["price"])
    all_priced.sort(key=lambda h: h["price"])
    cheapest = all_priced[0] if all_priced else None

    cheapest_text = f"NT${cheapest['price']:,}" if cheapest else "—"

    print(
        f"\n掃描完成：抓到 {len(all_priced)} 筆有效票價，"
        f"{len(hits)} 筆達標。全窗口最低 {cheapest_text}"
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
```

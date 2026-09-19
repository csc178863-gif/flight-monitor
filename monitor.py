#!/usr/bin/env python3
"""日本機票監控：掃過整個日期窗口 × 台灣南部出發 × 日本各區，
找出符合預算（THRESHOLD_TWD）的來回票，出現新低或首次跌破門檻時推播到 LINE。

用法：
    python monitor.py            # 正常跑一輪，有符合的才推播
    DRY_RUN=1 python monitor.py  # 只印結果、不推播（本機測試）
    ALWAYS_REPORT=1 python monitor.py  # 強制推播目前最便宜（驗證推播管線）

狀態存在 state.json（每個組合的歷史最低價 + 是否已通知），
所以只在「出現新低」或「首次跌破門檻」時才推，不會洗版。
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from fast_flights import create_query, get_flights, FlightQuery, Passengers

import config

STATE_FILE = Path(__file__).parent / "state.json"
TPE = timezone(timedelta(hours=8))  # Asia/Taipei

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
ALWAYS_REPORT = os.environ.get("ALWAYS_REPORT", "").lower() in ("1", "true", "yes")
API_KEY = os.environ.get("GMN_API_KEY", "")


# ── 狀態讀寫 ───────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"threshold_twd": config.THRESHOLD_TWD, "combos": {}}


def save_state(state):
    state["updated"] = datetime.now(TPE).isoformat(timespec="seconds")
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 抓單一組合的最低價 ─────────────────────────────────
def fetch_combo(origin, dest, dep, ret):
    """回傳最便宜的來回結果 dict，抓不到回 None。"""
    q = create_query(
        flights=[
            FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=dest,
                        max_stops=config.MAX_STOPS),
            FlightQuery(date=ret.isoformat(), from_airport=dest, to_airport=origin,
                        max_stops=config.MAX_STOPS),
        ],
        trip="round-trip",
        seat="economy",
        passengers=Passengers(adults=1),
        currency=config.CURRENCY,
        language=config.LANGUAGE,
    )
    res = get_flights(q)
    priced = [f for f in res if isinstance(getattr(f, "price", None), int) and f.price > 0]
    if not priced:
        return None
    best = min(priced, key=lambda f: f.price)

    dep_time = ""
    try:
        t = best.flights[0].departure.time  # (H, M)
        dep_time = f"{t[0]:02d}:{t[1]:02d}"
    except Exception:
        pass

    return {
        "price": best.price,
        "airlines": "／".join(best.airlines) if best.airlines else "—",
        "dep_time": dep_time,
        "url": q.url(),
    }


# ── 訊息排版（沿用 LINE 分段條列風格）──────────────────
def build_message(hits, cheapest):
    """hits: 這次觸發推播的組合（≤門檻）；cheapest: 全窗口最便宜（不論是否達標）。"""
    lines = []
    if hits:
        top = hits[0]
        lines.append(f"✈️ 日本機票監控｜{len(hits)} 個達標（≤ NT${config.THRESHOLD_TWD:,}）")
        lines.append("")
        lines.append(f"💰 最低 NT${top['price']:,}")
        lines.append(f"🛫 {top['o_name']} {top['origin']} → {top['d_name']} {top['dest']}")
        lines.append(f"📅 去 {top['dep']} → 回 {top['ret']}（{config.NIGHTS} 晚）")
        lines.append(f"🏢 {top['airlines']}｜{top['dep_time']} 出發")
        lines.append("")
        lines.append(f"🔗 訂票（Google Flights）")
        lines.append(top["url"])
        if len(hits) > 1:
            lines.append("")
            lines.append("其他達標：")
            for h in hits[1:8]:
                lines.append(
                    f"• {h['origin']}→{h['dest']} {h['dep']}→{h['ret']} "
                    f"NT${h['price']:,}（{h['airlines']}）"
                )
    else:
        # ALWAYS_REPORT：沒達標時回報目前最便宜
        lines.append("✈️ 日本機票監控｜目前無達標票（回報現況）")
        lines.append("")
        if cheapest:
            lines.append(f"💡 目前全窗口最低 NT${cheapest['price']:,}（目標 NT${config.THRESHOLD_TWD:,}）")
            lines.append(f"🛫 {cheapest['o_name']} {cheapest['origin']} → {cheapest['d_name']} {cheapest['dest']}")
            lines.append(f"📅 去 {cheapest['dep']} → 回 {cheapest['ret']}（{config.NIGHTS} 晚）")
            lines.append(f"🏢 {cheapest['airlines']}")
            lines.append("")
            lines.append(cheapest["url"])
        else:
            lines.append("（這輪沒抓到任何有效票價，可能被限流或無航班）")

    lines.append("")
    lines.append("⚠️ 過年檔期價格變動快，看到好價建議盡快下手")
    return "\n".join(lines)


def push_line(message):
    if DRY_RUN:
        print("── [DRY_RUN] 以下訊息不會送出 ──\n" + message)
        return
    if not API_KEY:
        print("⚠️ 沒有 GMN_API_KEY，跳過推播。訊息內容：\n" + message)
        return
    r = requests.post(
        config.GMN_PUSH_URL,
        json={"message": message},
        headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    print(f"推播結果 HTTP {r.status_code}: {r.text[:200]}")
    r.raise_for_status()


# ── 主流程 ─────────────────────────────────────────────
def main():
    state = load_state()
    state["threshold_twd"] = config.THRESHOLD_TWD
    combos = state.setdefault("combos", {})
    now_iso = datetime.now(TPE).isoformat(timespec="seconds")

    hits = []          # 這輪觸發推播的（首次達標 or 達標中創新低）
    all_priced = []    # 這輪所有抓到價的，用來找全窗口最便宜
    pairs = config.date_pairs()
    total = len(config.ORIGINS) * len(config.DESTS) * len(pairs)
    print(f"開始掃描：{total} 個組合（{len(config.ORIGINS)} 出發 × "
          f"{len(config.DESTS)} 目的地 × {len(pairs)} 組日期）門檻 NT${config.THRESHOLD_TWD:,}")

    i = 0
    for origin, o_name in config.ORIGINS.items():
        for dest, d_name in config.DESTS.items():
            for dep, ret in pairs:
                i += 1
                key = f"{origin}-{dest}-{dep.isoformat()}"
                try:
                    r = fetch_combo(origin, dest, dep, ret)
                except Exception as e:
                    print(f"[{i}/{total}] {key} 抓取失敗：{type(e).__name__}: {e}")
                    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
                    continue

                if not r:
                    print(f"[{i}/{total}] {key} 無票價")
                    time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
                    continue

                price = r["price"]
                rec = {
                    "origin": origin, "o_name": o_name,
                    "dest": dest, "d_name": d_name,
                    "dep": dep.isoformat(), "ret": ret.isoformat(),
                    **r,
                }
                all_priced.append(rec)

                prev = combos.get(key, {})
                prev_low = prev.get("lowest_twd")
                prev_alerted = prev.get("below_threshold_alerted", False)

                is_new_low = prev_low is None or price < prev_low
                below = price <= config.THRESHOLD_TWD
                # 觸發條件：首次跌破門檻，或達標中又創新低
                trigger = below and (not prev_alerted or is_new_low)

                combos[key] = {
                    "lowest_twd": min(price, prev_low) if prev_low else price,
                    "last_twd": price,
                    "below_threshold_alerted": below,  # 漲回門檻以上會自動歸 False，下次再跌破會再通知
                    "last_seen": now_iso,
                }

                tag = ""
                if trigger:
                    hits.append(rec)
                    tag = " 🔔達標觸發"
                elif is_new_low:
                    tag = " ↓新低"
                print(f"[{i}/{total}] {key}  NT${price:,}{tag}")

                time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))

    hits.sort(key=lambda h: h["price"])
    all_priced.sort(key=lambda h: h["price"])
    cheapest = all_priced[0] if all_priced else None

    print(f"\n掃描完成：抓到 {len(all_priced)} 筆有效票價，"
          f"{len(hits)} 筆達標。全窗口最低 "
          f"{('NT$%s' % format(cheapest['price'], ',')) if cheapest else '—'}")

    save_state(state)

    if hits:
        push_line(build_message(hits, cheapest))
    elif ALWAYS_REPORT:
        push_line(build_message([], cheapest))
    else:
        print("無達標票，不推播。")


if __name__ == "__main__":
    sys.exit(main())

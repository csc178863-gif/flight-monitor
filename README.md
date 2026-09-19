# ✈️ 日本機票監控 flight-monitor

自動掃日期窗口 × 台灣南部出發 × 日本各區的來回機票，找到符合預算的票就推播到 LINE。

- **抓價引擎**：Python `fast-flights`（直接查 Google Flights，含廉航，不用開瀏覽器）
- **排程**：GitHub Actions cron，每小時一次（純雲端，不靠本機 Mac）
- **推播**：找到達標票 → POST 到 `finance-dashboard` 的 `/api/gmn-push` → LINE
- **防洗版**：`state.json` 記每個組合的歷史最低價，只在「首次跌破門檻」或「達標中創新低」才推

## 目前設定（改 `config.py`）

| 項目 | 值 |
|---|---|
| 出發 | 高雄 KHH、台中 RMQ |
| 目的地 | 東京 TYO、大阪 OSA、福岡 FUK、沖繩 OKA、名古屋 NGO |
| 日期窗口 | 2027-01-28 出發 ～ 2027-02-10 回程 |
| 行程長度 | 7 晚 |
| 航班 | 只要直飛（去程/回程皆直飛，`MAX_STOPS=0`） |
| 價格門檻 | NT$17,000（來回含稅，1 名成人；過年檔期直飛的實際低點約 17,500） |

⚠️ 此窗口橫跨 **2027 農曆春節（2/6）**，過年檔期票價偏高且變動快，前半段（1/28 出發那側）通常較便宜。

## 本機測試

```bash
pip install -r requirements.txt
DRY_RUN=1 python monitor.py          # 掃一輪、只印不推播
ALWAYS_REPORT=1 python monitor.py    # 掃一輪 + 強制推播目前最便宜（驗證 LINE 管線）
```

## 部署狀態

- ✅ 程式碼已在此 repo（公開，免費無上限 Actions 分鐘數）
- ✅ Actions secret `GMN_API_KEY` 已設定（推播用）
- ⏳ **排程尚未啟用**：排程檔目前放在 `deploy/monitor.yml`，還沒移到 `.github/workflows/`
  （因為 `gh` OAuth token 缺 `workflow` 權限，無法用 git 推送 workflow 檔）

### 啟用每小時排程（二選一）

**方法 A｜手機/瀏覽器就能做，不用終端機：**
1. 開 repo → `deploy/monitor.yml` → 複製內容
2. repo 首頁 → **Add file → Create new file**
3. 檔名填 `.github/workflows/monitor.yml` → 貼上 → **Commit**
（用 GitHub 網頁登入態建立 workflow 不受 OAuth 權限限制）

**方法 B｜回到終端機：**
```bash
gh auth refresh -h github.com -s workflow   # 補 workflow 權限（跳瀏覽器確認一次）
```
之後把 `deploy/monitor.yml` 搬到 `.github/workflows/` 再 push 即可。

### 啟用後測一次
Actions 頁面 → flight-monitor → **Run workflow** → 把 `always_report` 打勾 → 會強制推一則現況到 LINE。

## 常見調整

- **改門檻**：`config.py` 的 `THRESHOLD_TWD`
- **加/減目的地**：`config.py` 的 `DESTS`
- **改頻率**：`.github/workflows/monitor.yml` 的 `cron`（`0 */2 * * *` = 每 2 小時；被 Google 限流時就調稀）
- **手動複查**：見 `skyscanner_urls.md`

## 已知限制

- `fast-flights` 是非官方抓 Google Flights，Google 改版面時可能失效，需偶爾維修。
- 高頻掃描（如每 15 分）易被 Google 限流，故預設每小時；若 Actions log 出現大量「無票價／抓取失敗」，把 cron 調稀。

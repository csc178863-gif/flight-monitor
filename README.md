# ✈️ 日本機票監控 flight-monitor

自動搜尋台灣出發、前往日本的來回機票。透過 GitHub Actions 定時掃描指定日期與目的地，並使用 LINE 通知符合條件的票價。

## 一、目前監控設定

| 項目    | 設定                           |
| ----- | ---------------------------- |
| 出發機場  | 高雄 KHH、台中 RMQ、桃園 TPE         |
| 日本目的地 | 名古屋 NGO、東京 TYO、大阪 OSA、札幌 CTS |
| 出發日期  | 2027-01-23～2027-02-01        |
| 旅遊晚數  | 7、8、9 晚                      |
| 最晚回程日 | 2027-02-10                   |
| 價格門檻  | NT$20,000                    |
| 航班限制  | 只搜尋直飛航班（MAX_STOPS=0）         |
| 執行頻率  | GitHub Actions 每小時一次         |
| 通知方式  | LINE                         |

### 已移除的目的地

以下目的地不再列入目前掃描：

* 沖繩 OKA
* 石垣島 ISG
* 福岡 FUK

如需重新加入或調整目的地，請修改 `config.py` 的 `DESTS`。

## 二、掃描規模

目前設定：

* 3 個出發機場
* 4 個日本目的地
* 30 組日期組合
* 理論最大查詢量：360 組

計算方式：

`3 × 4 × 30 = 360 組`

相較於原本 630 組，每輪理論查詢量減少 270 組，約 42.9%。

實際成功取得票價的組數可能較少，因為部分航線可能沒有航班或查詢失敗。

## 三、通知機制

程式使用 `state.json` 記錄各航班組合的歷史最低價，以減少重複通知。

一般掃描會依照程式設定，在符合通知條件時推播 LINE，例如首次達到價格門檻或符合新低價通知條件。

手動執行時，可使用 `always_report` 強制回報目前最便宜的搜尋結果，以測試通知流程。

注意：搜尋結果不代表訂票網站一定仍有相同票價。訂票前應再次確認日期、直飛條件、行李、稅費及實際可訂購價格。

## 四、GitHub Actions

專案使用 GitHub Actions 自動執行，不需要個人電腦持續開機。

工作流程包含：

1. 驗證設定。
2. 安裝 Python 依賴套件。
3. 執行 `monitor.py` 搜尋機票。
4. 透過 LINE 推播符合條件的結果。
5. 更新並提交 `state.json`。

### 手動執行

前往 GitHub 專案的 **Actions** 頁面，選擇 `flight-monitor` 工作流程，再按 **Run workflow**。

可依需求選擇：

* `validate_config`：只驗證設定，不執行正式掃描。
* `always_report`：正式掃描後，強制回報目前最便宜的搜尋結果。

一般情況下，先執行設定驗證，再執行正式掃描。

## 五、必要的 GitHub Secrets

請在 Repository → Settings → Secrets and variables → Actions 設定以下機密值：

* `GMN_API_KEY`
* `LINE_CHANNEL_ACCESS_TOKEN`
* `LINE_USER_ID`

請勿將 API Key、LINE Token 或其他機密資訊直接寫入公開程式碼或 README。

## 六、常見調整

| 想調整的項目 | 修改位置                                     |
| ------ | ---------------------------------------- |
| 出發機場   | `config.py` 的 `ORIGINS`                  |
| 日本目的地  | `config.py` 的 `DESTS`                    |
| 出發日期範圍 | `config.py` 的日期設定                        |
| 旅遊晚數   | `config.py` 的日期組合設定                      |
| 票價門檻   | `config.py` 的 `THRESHOLD_TWD`            |
| 直飛限制   | `config.py` 的 `MAX_STOPS`                |
| 執行頻率   | `.github/workflows/monitor.yml` 的 `cron` |

修改設定後，建議先使用 `validate_config` 驗證，再進行正式掃描。

## 七、常見問題與錯誤排查

### 1. 工作流程成功，但沒有收到 LINE

請檢查：

* GitHub Actions 的 `Run monitor` 是否有執行推播。
* LINE 相關 Secrets 是否正確。
* 本次掃描是否符合通知條件。
* LINE 推播 API 是否回傳錯誤。

### 2. 出現 `FlightsNotFound`

表示該日期與航線沒有找到符合條件的航班，不一定代表程式故障。

### 3. 出現 `TypeError: 'NoneType' object is not subscriptable`

可能是查詢結果為空或資料格式不符合程式預期。即使整個工作流程最後顯示成功，也應檢查相關紀錄，確認是否有部分航線漏查。

### 4. 查詢失敗或沒有票價的紀錄很多

請先查看 GitHub Actions 日誌，確認是否為航班不存在、Google Flights 查詢限制，或程式處理資料時發生錯誤。

不要只根據工作流程的綠色勾勾，就認定所有航線都已成功取得價格。

## 八、技術與限制

* Python：執行機票搜尋及通知程式。
* `fast-flights`：透過 Google Flights 取得搜尋結果。
* GitHub Actions：定時執行自動化工作。
* `state.json`：保存價格狀態。
* LINE：接收符合條件的票價通知。

`fast-flights` 使用非官方方式取得搜尋結果，可能受到 Google Flights 網頁變更、查詢限制或資料格式改變影響，因此需要定期檢查執行日誌。

---

**專案用途：** 自動監控日本來回機票價格，減少手動搜尋時間，並在符合設定條件時透過 LINE 通知。

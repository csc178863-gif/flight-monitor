# Skyscanner 人工複查清單

自動監控走 Google Flights（`monitor.py`）。Skyscanner 反爬強、常跳人機驗證，不適合自動化，
但**手動複查很好用**——尤其它的「整月最便宜」檢視。以下網址點開即可，不用登入。

> 網址格式：`skyscanner.com.tw/transport/flights/{出發}/{目的}/{去YYMMDD}/{回YYMMDD}/`
> `jp` = 整個日本（Skyscanner 支援「飛往國家」，會列出各城市最低價）

## 高雄 KHH → 日本（來回，7 晚）

- 去 1/28 → 回 2/4：https://www.skyscanner.com.tw/transport/flights/khh/jp/270128/270204/
- 去 1/29 → 回 2/5：https://www.skyscanner.com.tw/transport/flights/khh/jp/270129/270205/
- 去 1/30 → 回 2/6：https://www.skyscanner.com.tw/transport/flights/khh/jp/270130/270206/
- 去 1/31 → 回 2/7：https://www.skyscanner.com.tw/transport/flights/khh/jp/270131/270207/
- 去 2/1 → 回 2/8：https://www.skyscanner.com.tw/transport/flights/khh/jp/270201/270208/
- 去 2/2 → 回 2/9：https://www.skyscanner.com.tw/transport/flights/khh/jp/270202/270209/
- 去 2/3 → 回 2/10：https://www.skyscanner.com.tw/transport/flights/khh/jp/270203/270210/

## 台中 RMQ → 日本（來回，7 晚）

- 去 1/28 → 回 2/4：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270128/270204/
- 去 1/29 → 回 2/5：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270129/270205/
- 去 1/30 → 回 2/6：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270130/270206/
- 去 1/31 → 回 2/7：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270131/270207/
- 去 2/1 → 回 2/8：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270201/270208/
- 去 2/2 → 回 2/9：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270202/270209/
- 去 2/3 → 回 2/10：https://www.skyscanner.com.tw/transport/flights/rmq/jp/270203/270210/

## 小技巧

- **整月檢視**：進去後把回程日期欄改成「最便宜的月份」，一次看整個 1、2 月哪天最低。
- **設定價格提醒**：Skyscanner 自己有「價格通知」功能（需登入 Google 帳號），可當作這套監控的雙保險。
- 換單一城市：把 `jp` 換成 `tyoa`(東京)、`osaa`(大阪)、`fuk`(福岡)、`oka`(沖繩)、`ngoa`(名古屋)。

# train-query

原始專案為通勤列車查詢頁面；本次新增「台股與美股公開股票投資研究代理」文件、prompt、可執行腳本與排程範例。

## 通勤列車查詢

開啟 `index.html` 可查詢汐科 ⇄ 板橋通勤列車班次。

## 台股與美股公開股票投資研究代理

請參考 `investing_agent/README.md`。

排程提醒：GitHub Actions 已設定每天 **台灣時間上午 11:30（Asia/Taipei；UTC 03:30）** 自動產生報告，並將報告寫入 workflow summary 與 artifact。若需要在 Codex / ChatGPT 對話視窗看到內容，請在 11:30 後回到對話要求更新；目前 GitHub Actions 無法主動推送訊息到既有聊天視窗。

API key 安全提醒：若要使用 RapidAPI 取得更新行情，請把 `RAPIDAPI_KEY` 設成 GitHub Actions Secret 或本機未追蹤的 `investing_agent/.env`，不要貼到聊天視窗、README 或任何 commit；詳細步驟請看 `investing_agent/README.md`。

快速產生每日研究報告：

```bash
python investing_agent/scripts/daily_public_equity_report.py
```

若要輸出到檔案：

```bash
python investing_agent/scripts/daily_public_equity_report.py --output reports/daily-equity-$(date +%F).md
```

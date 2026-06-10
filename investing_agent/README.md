# 台股與美股公開股票投資研究代理

本目錄提供一個可手動執行、也可用排程觸發的「Public Equity Investing」每日研究流程。輸出語言固定為繁體中文，並依照使用者指定格式產出台股市場狀態、主要影響因素、技術面、操作判斷、風險提醒、持股建議與一句話總結。

## 排程狀態

本儲存庫無法直接宣告 Codex Cloud automation/schedule，也無法由 GitHub Actions 主動把訊息推送到既有 Codex / ChatGPT 對話視窗；因此目前採用下列交付方式：

1. 可手動執行的 Python 分析流程。
2. 可交給 Codex 或其他 LLM 使用的每日研究 prompt。
3. GitHub Actions 範例排程：**每天台灣時間上午 11:30（Asia/Taipei；UTC 03:30）自動執行**，也支援手動觸發。
4. 排程執行後，報告會同時出現在 GitHub Actions 的 workflow summary 與 `daily-equity-report` artifact；若平台日後支援對話視窗 automation/schedule，請沿用本 prompt 與相同 11:30 排程。

> 重要：若使用者指定「在這個視窗看到報告」，在目前無主動推送能力的環境下，代理應在使用者回到此對話並要求更新時，直接貼出當日報告；不可假裝已能主動推送到聊天視窗。

## 在這個對話視窗取得報告

可以。若你希望每天直接在 Codex / ChatGPT 對話視窗看到報告，請在台北時間 11:30 後開啟本專案並輸入：

```text
請使用 investing_agent/prompts/daily_public_equity_investing_zh_tw.md 的規則，
並以 investing_agent/scripts/daily_public_equity_report.py 的資料取得邏輯，
直接在這個對話視窗產出台股與美股公開股票投資研究報告。
```

若環境允許連線，代理會即時查詢最新可得行情與新聞並在視窗內輸出完整報告；若資料源不可用，會明確標示「資料不足」，不硬補數字。

## 手動執行

```bash
python investing_agent/scripts/daily_public_equity_report.py
```

預設會在標準輸出印出 Markdown 報告。如需寫入檔案：

```bash
python investing_agent/scripts/daily_public_equity_report.py --output reports/daily-equity-$(date +%F).md
```

## 可選環境變數

- `RAPIDAPI_KEY`：RapidAPI API key。必須放在本機環境變數或 GitHub Actions Secret，**不要寫進程式碼、README、prompt、commit 或聊天訊息**。
- `RAPIDAPI_HOST`：RapidAPI marketplace 頁面提供的 host，建議放在 GitHub Actions Variables；若服務商要求保密，也可放在 Secret。
- `RAPIDAPI_QUOTE_URL`：RapidAPI 報價 URL 範本，需包含 `{symbol}`，例如 `https://example.p.rapidapi.com/quote?symbol={symbol}`；建議放在 GitHub Actions Variables。
- `ALPHAVANTAGE_API_KEY`：可作為未來 Alpha Vantage 備援來源；程式不會輸出 key。

## 安全設定 RapidAPI key

建議使用下列方式，依安全性與自動化需求排序：

1. **GitHub Actions 自動排程（推薦）**
   - 到 GitHub repo 的 `Settings` → `Secrets and variables` → `Actions`。
   - 在 `Secrets` 新增 `RAPIDAPI_KEY`，貼上真正的 API key。
   - 在 `Variables` 新增 `RAPIDAPI_HOST` 與 `RAPIDAPI_QUOTE_URL`；若你的 RapidAPI 供應商把 host 或 URL 視為敏感資訊，也可改放 Secrets。
   - `.github/workflows/daily-equity-research.yml` 已用 `${{ secrets.RAPIDAPI_KEY }}` 注入 key，排程執行時不會把 key 寫入報告。

2. **本機手動執行**
   - 複製範例檔：`cp investing_agent/.env.example investing_agent/.env`。
   - 只在 `investing_agent/.env` 填入真實 key；`.gitignore` 已排除 `.env` / `.env.*`，避免誤 commit。
   - 執行前匯入環境變數：

     ```bash
     set -a
     source investing_agent/.env
     set +a
     python investing_agent/scripts/daily_public_equity_report.py
     ```

3. **臨時單次執行**
   - 可在 shell session 暫時 export，但不要貼到聊天視窗或 commit：

     ```bash
     export RAPIDAPI_KEY='只放在你的本機終端機，不要貼給代理'
     export RAPIDAPI_HOST='你的 RapidAPI host'
     export RAPIDAPI_QUOTE_URL='你的 quote URL，包含 {symbol}'
     python investing_agent/scripts/daily_public_equity_report.py
     ```

安全原則：不要把 API key 貼給 Codex / ChatGPT、不要存在 tracked 檔案、定期輪替 key、設定 RapidAPI 用量上限 / billing alert，並在疑似外洩時立刻 revoke / regenerate。

## 資料來源優先序

1. 台股大盤、上市個股、法人資料：TWSE 官方 OpenAPI。
2. 若 RapidAPI 設定完整且可用：用於美股、TSM ADR、Nasdaq、S&P 500、SOXX、USD/TWD、台股 `.TW` 報價。
3. 若 RapidAPI 不可用：使用 Yahoo Finance chart API 等可驗證延遲 / 收盤資料。
4. 抓不到的項目輸出「資料不足」，不硬補數字。

## 每日人工複核步驟

1. 於台北時間 11:30 後執行腳本。
2. 檢查「主要資料來源與 as-of」是否涵蓋台股、美股、半導體、匯率與持股。
3. 若新聞面需要納入，使用最新可引用來源補充 AI server / 半導體供應鏈重大事件。
4. 若任何資料為「資料不足」，不要改寫成確定訊號；僅以條件式風險提醒呈現。
5. 若要交給 LLM 潤稿或補充，使用 `prompts/daily_public_equity_investing_zh_tw.md`，並貼上腳本輸出的行情摘要。

## 重要聲明

此流程僅供公開市場研究與風險控管參考，不構成投資建議、招攬或保證獲利。沒有成本價、停損承受度、投資期限與完整資產配置時，持股建議必須維持一般性與條件式。

#!/usr/bin/env python3
"""Generate a Traditional Chinese daily public-equity research report.

The script intentionally degrades to 「資料不足」 when a source is unreachable.
It never prints API keys or secrets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

TAIPEI_TZ = dt.timezone(dt.timedelta(hours=8), name="Asia/Taipei")
USER_AGENT = "public-equity-research-agent/1.0"


@dataclass(frozen=True)
class Holding:
    name: str
    symbol: str
    shares: float
    screenshot_price: float
    screenshot_value: float
    group: str


@dataclass
class Quote:
    symbol: str
    name: str
    price: float | None = None
    previous_close: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    avg_volume_20: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    support: float | None = None
    resistance: float | None = None
    as_of: str = "資料不足"
    source: str = "資料不足"
    realtime_note: str = "資料不足"
    error: str | None = None


HOLDINGS: list[Holding] = [
    Holding("元大台灣50", "0050.TW", 7000, 104.15, 729050, "市值型ETF"),
    Holding("復華台灣科技優息", "00929.TW", 10000, 29.94, 299400, "科技高股息ETF"),
    Holding("統一台灣高息動能", "00939.TW", 5000, 20.89, 104450, "高息動能ETF"),
    Holding("鴻海", "2317.TW", 1000, 284.5, 284500, "AI server / 電子代工"),
    Holding("台積電", "2330.TW", 74, 2365, 175010, "半導體"),
    Holding("華南金", "2880.TW", 6186, 34.8, 215272, "金融股"),
    Holding("玉山金", "2884.TW", 151, 33.35, 5035, "金融股"),
    Holding("第一金", "2892.TW", 15353, 29.3, 449842, "金融股"),
    Holding("合庫金", "5880.TW", 16043, 23.45, 376208, "金融股"),
]

MARKET_SYMBOLS = {
    "美股S&P500": "^GSPC",
    "美股Nasdaq": "^IXIC",
    "半導體SOXX": "SOXX",
    "TSM ADR": "TSM",
    "美元/台幣": "USDTWD=X",
    "台股加權": "^TWII",
}

TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_MI_INDEX = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX?type=ALL"
TWSE_T86 = "https://openapi.twse.com.tw/v1/exchangeReport/T86"


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> Any:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    with urlopen(req, timeout=timeout) as res:
        raw = res.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return float(value)
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "--", "-", "N/A", "null"}:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "資料不足"
    return f"{value:,.{digits}f}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "資料不足"
    return f"{value:+.2f}%"


def pct_change(price: float | None, prev: float | None) -> float | None:
    if price is None or prev in (None, 0):
        return None
    return (price / prev - 1) * 100


def yahoo_chart_quote(symbol: str, label: str, range_: str = "6mo") -> Quote:
    encoded = quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range={range_}&interval=1d&includePrePost=false"
    q = Quote(symbol=symbol, name=label)
    try:
        data = fetch_json(url)
        result = data.get("chart", {}).get("result", [])
        if not result:
            raise ValueError(data.get("chart", {}).get("error") or "empty result")
        item = result[0]
        meta = item.get("meta", {})
        timestamps = item.get("timestamp", []) or []
        quote_data = (item.get("indicators", {}).get("quote", []) or [{}])[0]
        closes = [to_float(v) for v in quote_data.get("close", [])]
        volumes = [to_float(v) for v in quote_data.get("volume", [])]
        pairs = [(c, volumes[i] if i < len(volumes) else None) for i, c in enumerate(closes) if c is not None]
        if not pairs:
            raise ValueError("no close prices")
        close_values = [p[0] for p in pairs]
        volume_values = [p[1] for p in pairs if p[1] is not None]
        q.price = to_float(meta.get("regularMarketPrice")) or close_values[-1]
        q.previous_close = to_float(meta.get("chartPreviousClose"))
        if q.previous_close is None and len(close_values) >= 2:
            q.previous_close = close_values[-2]
        q.change_pct = pct_change(q.price, q.previous_close)
        q.volume = volume_values[-1] if volume_values else None
        if len(volume_values) >= 20:
            q.avg_volume_20 = statistics.fmean(volume_values[-20:])
        if len(close_values) >= 20:
            q.ma20 = statistics.fmean(close_values[-20:])
            q.support = min(close_values[-20:])
            q.resistance = max(close_values[-20:])
        if len(close_values) >= 60:
            q.ma60 = statistics.fmean(close_values[-60:])
        asof_epoch = meta.get("regularMarketTime")
        if asof_epoch:
            q.as_of = dt.datetime.fromtimestamp(int(asof_epoch), TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
        elif timestamps:
            q.as_of = dt.datetime.fromtimestamp(int(timestamps[-1]), TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
        q.source = "Yahoo Finance chart API"
        q.realtime_note = "非即時 / 延遲或收盤資料"
    except Exception as exc:
        q.error = str(exc)
    return q


def rapidapi_quote(symbol: str, label: str) -> Quote | None:
    key = os.getenv("RAPIDAPI_KEY")
    host = os.getenv("RAPIDAPI_HOST")
    url_template = os.getenv("RAPIDAPI_QUOTE_URL")
    if not key or not host or not url_template:
        return None
    q = Quote(symbol=symbol, name=label)
    try:
        url = url_template.format(symbol=quote(symbol, safe=""))
        data = fetch_json(url, headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": host})
        payload = data.get("body", data) if isinstance(data, dict) else data
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            raise ValueError("unsupported RapidAPI response format")
        q.price = to_float(payload.get("regularMarketPrice") or payload.get("price") or payload.get("lastPrice"))
        q.previous_close = to_float(payload.get("regularMarketPreviousClose") or payload.get("previousClose"))
        q.change_pct = to_float(payload.get("regularMarketChangePercent") or payload.get("changePercent"))
        if q.change_pct is not None and abs(q.change_pct) <= 1:
            q.change_pct *= 100
        if q.change_pct is None:
            q.change_pct = pct_change(q.price, q.previous_close)
        q.volume = to_float(payload.get("regularMarketVolume") or payload.get("volume"))
        q.as_of = str(payload.get("regularMarketTime") or payload.get("asOf") or "RapidAPI 回傳時間欄位不足")
        q.source = f"RapidAPI ({host})"
        q.realtime_note = "依 RapidAPI 方案而定"
        if q.price is None:
            raise ValueError("RapidAPI response has no usable price")
        return q
    except Exception as exc:
        q.error = f"RapidAPI 不可用：{exc}"
        return q


def get_quote(symbol: str, label: str) -> Quote:
    rapid = rapidapi_quote(symbol, label)
    if rapid and rapid.price is not None:
        return rapid
    fallback = yahoo_chart_quote(symbol, label)
    if rapid and rapid.error and fallback.error:
        fallback.error = f"{rapid.error}; Yahoo fallback: {fallback.error}"
    return fallback


def fetch_twse_stock_snapshot() -> dict[str, dict[str, Any]]:
    try:
        rows = fetch_json(TWSE_STOCK_DAY_ALL)
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("Code") or row.get("證券代號") or "").strip()
        if code:
            out[code] = row
    return out


def apply_twse_snapshot(quote: Quote, row: dict[str, Any]) -> Quote:
    close = to_float(row.get("ClosingPrice") or row.get("收盤價"))
    open_ = to_float(row.get("OpeningPrice") or row.get("開盤價"))
    change = to_float(row.get("Change") or row.get("漲跌價差"))
    volume = to_float(row.get("TradeVolume") or row.get("成交股數"))
    if close is not None:
        quote.price = close
        if change is not None:
            quote.previous_close = close - change
            quote.change_pct = pct_change(close, quote.previous_close)
        elif open_ is not None:
            quote.change_pct = pct_change(close, open_)
        quote.volume = volume or quote.volume
        quote.source = "TWSE 官方 OpenAPI STOCK_DAY_ALL + Yahoo Finance chart API 技術指標"
        quote.realtime_note = "TWSE 最新收盤資料；技術指標可能為延遲資料"
        quote.as_of = row.get("Date") or row.get("日期") or quote.as_of
    return quote


def indicator_label(change: float | None, up_threshold: float = 0.3, down_threshold: float = -0.3) -> str:
    if change is None:
        return "資料不足"
    if change >= up_threshold:
        return "正面"
    if change <= down_threshold:
        return "負面"
    return "中性"


def trend_label(q: Quote) -> str:
    if q.price is None or q.ma20 is None:
        return "資料不足"
    if q.ma60 is not None and q.price > q.ma20 > q.ma60:
        return "正面"
    if q.ma60 is not None and q.price < q.ma20 < q.ma60:
        return "負面"
    return "中性"


def technical_conclusion(q: Quote) -> str:
    if q.price is None or q.ma20 is None:
        return "盤整"
    if q.ma60 is not None and q.price > q.ma20 > q.ma60:
        return "偏強"
    if q.ma60 is not None and q.price < q.ma20 < q.ma60:
        return "偏弱"
    return "盤整"


def volume_note(q: Quote) -> tuple[str, str]:
    if q.volume is None or q.avg_volume_20 is None:
        return "資料不足", "成交量或 20 日均量資料不足。"
    ratio = q.volume / q.avg_volume_20 if q.avg_volume_20 else None
    if ratio is None:
        return "資料不足", "20 日均量為 0 或資料異常。"
    if ratio >= 1.1 and (q.change_pct or 0) >= 0:
        return "正面", f"成交量約為 20 日均量 {ratio:.2f} 倍，且價格未轉弱。"
    if ratio >= 1.1 and (q.change_pct or 0) < 0:
        return "負面", f"成交量約為 20 日均量 {ratio:.2f} 倍，但價格下跌，需防放量賣壓。"
    return "中性", f"成交量約為 20 日均量 {ratio:.2f} 倍，量能未明顯擴張。"


def market_state(factors: dict[str, tuple[str, str]]) -> tuple[str, int]:
    score_map = {"正面": 1, "中性": 0, "負面": -1, "資料不足": 0}
    valid = [v[0] for v in factors.values() if v[0] != "資料不足"]
    if not valid:
        return "震盪", 20
    score = sum(score_map[v] for v in valid)
    max_abs = len(valid)
    confidence = int(min(85, max(35, 45 + abs(score) / max_abs * 40 + len(valid) / len(factors) * 15)))
    if score >= 2:
        return "偏多", confidence
    if score <= -2:
        return "偏空", confidence
    return "震盪", confidence


def operation_decision(state: str, tech: str) -> str:
    if state == "偏空" and tech == "偏弱":
        return "避免交易"
    if state == "偏多" and tech == "偏強":
        return "等拉回"
    if state == "偏多" and tech == "盤整":
        return "等突破"
    if state == "震盪":
        return "觀望"
    return "小部位"


def holding_action(holding: Holding, quote: Quote, state: str) -> tuple[str, str, str, str]:
    if quote.price is None:
        return "觀望", "最新行情資料不足，無法覆蓋截圖價格。", "資料不足下不宜加碼，需等報價恢復。", "取得最新收盤或即時行情後再評估。"
    tech = technical_conclusion(quote)
    concentration_note = ""
    if holding.screenshot_value >= 350000:
        concentration_note = "；部位金額較大，需留意集中度與回撤"
    if state == "偏空" or tech == "偏弱":
        action = "減碼" if holding.group in {"半導體", "AI server / 電子代工", "科技高股息ETF"} else "停損觀察"
        reason = f"整體狀態 {state}、個股技術面 {tech}{concentration_note}。"
        risk = "若大盤或族群續弱，可能面臨估值修正與放量下跌。"
        trigger = f"跌破支撐 {fmt_num(quote.support)} 或放量跌破 20 日線 {fmt_num(quote.ma20)} 時提高防守。"
        return action, reason, risk, trigger
    if state == "偏多" and tech == "偏強":
        action = "續抱"
        if holding.group in {"金融股", "市值型ETF"}:
            action = "續抱"
        reason = f"市場與技術面偏正向，價格相對 20/60 日線維持較佳結構{concentration_note}。"
        risk = "短線若漲多，追價容易承擔拉回風險；ETF仍受成分股與配息政策影響。"
        trigger = f"守住 20 日線 {fmt_num(quote.ma20)} 可續抱；接近壓力 {fmt_num(quote.resistance)} 且量縮時避免追價。"
        return action, reason, risk, trigger
    if tech == "偏強":
        return "等拉回", f"個股技術面偏強，但整體市場仍為 {state}。", "震盪盤追高容易被洗出。", f"回測 20 日線 {fmt_num(quote.ma20)} 不破或突破壓力 {fmt_num(quote.resistance)} 並放量再評估。"
    return "觀望", f"個股技術面 {tech}，市場狀態 {state}，訊號尚未一致。", "盤整期間容易出現假突破與類股輪動。", f"突破壓力 {fmt_num(quote.resistance)} 或跌破支撐 {fmt_num(quote.support)} 後再調整策略。"


def build_report() -> str:
    now = dt.datetime.now(TAIPEI_TZ)
    twse_snapshot = fetch_twse_stock_snapshot()

    quotes: dict[str, Quote] = {}
    for label, symbol in MARKET_SYMBOLS.items():
        quotes[label] = get_quote(symbol, label)
    for holding in HOLDINGS:
        q = get_quote(holding.symbol, holding.name)
        code = holding.symbol.split(".")[0]
        if code in twse_snapshot:
            q = apply_twse_snapshot(q, twse_snapshot[code])
        quotes[holding.name] = q

    spx = quotes["美股S&P500"]
    nasdaq = quotes["美股Nasdaq"]
    soxx = quotes["半導體SOXX"]
    tsm_adr = quotes["TSM ADR"]
    twii = quotes["台股加權"]
    usdtwd = quotes["美元/台幣"]
    tsm_tw = quotes["台積電"]

    us_label = "資料不足"
    if spx.change_pct is not None or nasdaq.change_pct is not None:
        vals = [v for v in [spx.change_pct, nasdaq.change_pct] if v is not None]
        us_label = indicator_label(statistics.fmean(vals))
    tw_label = trend_label(twii)
    semi_label = indicator_label(soxx.change_pct)
    tsm_label = "正面" if any(v == "正面" for v in [trend_label(tsm_tw), indicator_label(tsm_adr.change_pct)]) else trend_label(tsm_tw)
    fx_label = "資料不足"
    fx_reason = "美元/台幣資料不足。"
    if usdtwd.change_pct is not None:
        if usdtwd.change_pct > 0.5:
            fx_label = "負面"
            fx_reason = f"美元/台幣上升 {fmt_pct(usdtwd.change_pct)}，台幣轉弱通常不利外資風險偏好。"
        elif usdtwd.change_pct < -0.5:
            fx_label = "正面"
            fx_reason = f"美元/台幣下降 {fmt_pct(usdtwd.change_pct)}，台幣偏強有利資金面。"
        else:
            fx_label = "中性"
            fx_reason = f"美元/台幣變動 {fmt_pct(usdtwd.change_pct)}，匯率訊號不極端。"
    vol_label, vol_reason = volume_note(twii)

    factors = {
        "美股": (us_label, f"S&P 500 {fmt_pct(spx.change_pct)}、Nasdaq {fmt_pct(nasdaq.change_pct)}。"),
        "台股大盤": (tw_label, f"加權指數 {fmt_num(twii.price)}，20 日線 {fmt_num(twii.ma20)}，60 日線 {fmt_num(twii.ma60)}。"),
        "半導體族群": (semi_label, f"SOXX {fmt_pct(soxx.change_pct)}，作為全球半導體風險偏好代理。"),
        "台積電": (tsm_label, f"台積電 {fmt_num(tsm_tw.price)}（{fmt_pct(tsm_tw.change_pct)}）、TSM ADR {fmt_pct(tsm_adr.change_pct)}。"),
        "匯率": (fx_label, fx_reason),
        "成交量": (vol_label, vol_reason),
        "外資 / 投信 / 自營商": ("資料不足", "本流程嘗試保留 TWSE 法人資料欄位；若端點或格式不可得則不硬補。"),
    }
    state, confidence = market_state(factors)
    tech = technical_conclusion(twii)
    op = operation_decision(state, tech)
    non_trading_note = ""
    if twii.as_of != "資料不足":
        non_trading_note = "若今天不是台股交易日，請以最近交易日收盤判斷。"

    lines: list[str] = []
    lines.append(f"# 台股與美股公開股票投資研究報告（{now.strftime('%Y-%m-%d %H:%M:%S %Z')}）")
    lines.append("")
    lines.append("> 免責聲明：以下僅供公開市場研究與風險控管參考，不構成投資建議、招攬或保證獲利。因缺少成本價、停損承受度、投資期限與完整資產配置，持股建議皆為一般性與條件式。")
    lines.append("")
    lines.append("## 1. 今日市場狀態")
    lines.append(f"- {state}")
    lines.append(f"- 信心分數：{confidence}%")
    if non_trading_note:
        lines.append(f"- {non_trading_note}")
    lines.append("")
    lines.append("## 2. 主要影響因素")
    for key, (label, reason) in factors.items():
        lines.append(f"- {key}：{label}。{reason}")
    lines.append("")
    lines.append("## 3. 技術面")
    lines.append(f"- 關鍵支撐：{fmt_num(twii.support)}")
    lines.append(f"- 關鍵壓力：{fmt_num(twii.resistance)}")
    lines.append(f"- 成交量是否配合：{vol_label}。{vol_reason}")
    lines.append(f"- 技術結論：{tech}")
    lines.append("")
    lines.append("## 4. 操作判斷")
    lines.append(f"- {op}")
    lines.append("")
    lines.append("## 5. 風險提醒")
    lines.append("- 波動風險：美股科技股、半導體與台積電權重高，若美債利率、AI server 需求或估值預期反轉，台股可能同步放大波動。")
    lines.append("- 流動性風險：大型 ETF 與權值股流動性通常較佳，但高股息 ETF 在除息、成分股調整或市場急跌時仍可能擴大折溢價與追蹤誤差。")
    lines.append("- 槓桿風險：若使用融資、質押或衍生品，需先降槓桿；本報告不建議在資料不足或偏空環境加槓桿。")
    lines.append(f"- 停損條件：加權指數跌破關鍵支撐 {fmt_num(twii.support)}、放量跌破 20 日線 {fmt_num(twii.ma20)}，或外資 / 匯率 / 半導體族群同步轉弱時，應提高現金與防守部位。")
    lines.append("")
    lines.append("## 持股建議")
    for holding in HOLDINGS:
        q = quotes[holding.name]
        action, reason, risk, trigger = holding_action(holding, q, state)
        latest_value = q.price * holding.shares if q.price is not None else None
        lines.append(f"- {holding.name}（{holding.symbol}，{holding.shares:,.0f} 股）：{action}")
        lines.append(f"  - 最新可得價格 / 現值：{fmt_num(q.price)} / {fmt_num(latest_value, 0)}；截圖價格 {fmt_num(holding.screenshot_price)}、截圖現值 {fmt_num(holding.screenshot_value, 0)}。")
        lines.append(f"  - 主要理由：{reason}")
        lines.append(f"  - 風險：{risk}")
        lines.append(f"  - 觸發條件：{trigger}")
    lines.append("")
    lines.append("## 6. 一句話總結")
    stance = "積極" if state == "偏多" and tech == "偏強" else "保守" if state == "偏空" else "觀望"
    lines.append(f"今天比較適合：{stance}。原因是{state}訊號搭配技術面{tech}，且仍需確認成交量、匯率與法人資料是否同步支持。")
    lines.append("")
    lines.append("## 主要資料來源與 as-of")
    seen: set[str] = set()
    for label, q in quotes.items():
        key = f"{q.symbol}-{q.as_of}-{q.source}"
        if key in seen:
            continue
        seen.add(key)
        error_note = f"；錯誤：{q.error}" if q.error and q.price is None else ""
        lines.append(f"- {label}（{q.symbol}）：{q.source}，as-of：{q.as_of}，{q.realtime_note}{error_note}")
    lines.append("- 截圖持股價格時間：2026/06/06 23:06:46；若最新資料成功取得，以上最新可得行情已覆蓋截圖價格。")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="產出台股與美股每日公開股票投資研究報告。")
    parser.add_argument("--output", help="輸出 Markdown 檔案路徑；未提供時印到 stdout。")
    args = parser.parse_args()
    report = build_report()
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

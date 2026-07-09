# 📊 InvestUni-LearnHub — 投資學堂

**狀態**：🟢 運行中  
**最後更新**：2026-06-27  
**GitHub**：https://github.com/sssunwl/InvestUniS

---

## �項目簡介

投資教學平台 + Telegram Bot。提供市場分析、大環境評估、標的監控。

**核心功能**：
- 📈 市場分析工具
- 🌍 大環境 Tab（交通燈框架）
- 📅 經濟日曆
- 🤖 TG Bot 自動推送
- 💰 11 支標的監控

---

## 📁 資料夾結構

```
InvestUni-LearnHub/
├── README.md（本文件）
├── src/                         ← 平台代碼
├── bot/                         ← TG Bot
├── data/                        ← 監控數據
└── docs/                        ← 文檔
```

---

## 📊 監控指標

**大環境（5 信號看 3 方向）**：
- 日報：VIX / SPY 200MA / 美股期貨 / US10Y / DXY
- 週報：經濟日曆 / Put-Call Ratio / S&P Beat Rate / HY 信用利差
- 月報：CPI / PCE / FOMC / GDP / NFP

**標的監控**：
- 11 支股票/指數各加財報日、監控事件提醒

---

## 🤖 TG Bot

自動推送市場資訊、監控提醒。

**問題**：
- ⚠️ Actions queue 延遲 2-4 小時
- 解決方案：遷移至 Google Cloud Always Free VM

---

## 📈 進度

- ✅ 大環境 Tab 上線
- ✅ 11 支標的監控
- 🟡 TG Bot 延遲優化中


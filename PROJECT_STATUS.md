# InvestUni 投資學堂 — 專案進度

> 最後更新：2026-06-23

---

## 專案

**InvestUni 投資學堂**
Suniverse 旗下投資教育平台，由 Sterling 主導，Steve 技術協助。
目標：提供初學者從基礎概念到實戰策略的完整投資知識庫，並透過 Telegram Bot 每日推送市場資訊。

- **Repo**：https://github.com/sssunwl/InvestUni/
- **技術棧**：純靜態 HTML + Python + GitHub Actions
- **成本**：$0/月

---

## 完成

### 網站 index.html（11 個 Tab）

| Tab | 內容 | 狀態 |
|-----|------|------|
| 🏠 首頁 | 香港時鐘、五大市場狀態（美/港/台/日/加密）、開收市時間表、7日假日提醒、盤前盤後新聞 | ✅ |
| 📊 成交量 | 8種量價信號，各含 CSS 迷你量價圖示 | ✅ |
| 🕯 K線 | 8種形態，各含 CSS 迷你 K 線圖示 | ✅ |
| 📖 名詞 | 基礎概念、訂單類型、技術指標、動能&市場指標（DXY/RVOL/Float）、期權希臘字母 | ✅ |
| ⚡ 期權 | 四種核心玩法、策略選擇器（15種含 Bull Put/Bear Call Spread）+ 損益圖、Expected Move、黃金窗口、操盤 SOP | ✅ |
| 🏛 債券 | 6大術語、利率反向關係比喻、5種類型、風險說明 | ✅ |
| 📋 合約 | 期貨/CFD/遠期合約/互換，各附小學生比喻 | ✅ |
| 📈 期貨 | 期貨原理、常見品種、保證金制度、期貨 vs 期權比較 | ✅ |
| 📊 高息ETF | 原理說明（Covered Call/NAV侵蝕/ROC稅務）、4項風險提示、16支 ETF 即時參考表（每日 GH Actions 更新） | ✅ |
| 🧮 股息計算器 | 選 ETF 自動填入現價，輸入入場/金額/月數/離場，輸出股數/股息/資本損益/總回報/年化回報 | ✅ |
| 🌍 盤前 | 市場結構原則、宏觀四寶（VIX/WTI/US10Y/DXY）、Risk-on/off、30秒清單、例行程序、數據日曆、Tier-1 資訊來源、平台（含超連結） | ✅ |
| 📈 動能 | Momentum Breakout Radar V1：指標詳解、Scanner A+B、Finviz 實操教學、進場 Setup、假突破警示、出場規則、進階概念、實用網站（含超連結） | ✅ |
| ⏰ 日內 | 五時段流程（盤前/開盤/盤中/盤尾/盤後）、VWAP 行為、收盤強弱公式、15 分鐘最佳流程 SOP、雙 Scanner 對照表（含超連結） | ✅ |

### 自動化系統

- **GitHub Actions（新聞）**：每日定時抓取新聞並 commit（`chore: news update`）
- **GitHub Actions（ETF）**：每日 13:00 HKT 抓取 16 支高息 ETF 資料 → `data/etf_data.json`（`chore: etf data update`）
- **Telegram Bot**：4次/天推送
  - 08:00 HKT — 美股夜盤後
  - 09:00 HKT — 亞洲盤前
  - 17:00 HKT — 亞洲盤後
  - 21:30 HKT — 美股盤前（開市通知）

### 已修復 Bug

- HTML escaping 問題
- 重複來源名稱
- GitHub Actions 權限
- Node.js 24 升級
- TG 訊息時間由 hardcoded（08:00/09:00/17:00/21:30）改為實際發送時間

---

## 目前狀態

- 網站正常運行，共 12 個 Tab（基本 4 + 高階 4 + 工具 3 + 實戰 3）
- 所有工具名稱（Finviz、TradingView、Benzinga、Market Chameleon、Unusual Whales、Fintel、BullFlow、WhaleWisdom、SEC EDGAR、Yahoo Finance、Investing.com 等）已加入可點擊超連結
- TG Bot 正在運行，08:00 / 09:00 HKT 基本準時
- 17:00 / 21:30 HKT 通知有系統性延遲（詳見問題/風險）

---

## 下一步

| 優先 | 項目 | 說明 |
|------|------|------|
| 🔴 高 | Oracle Cloud Always Free VM 遷移 | 解決 TG Bot 延遲問題，用真正的 crontab 替代 GitHub Actions cron |
| 🟡 中 | 網站其他內容擴充 | 視 SS 需求決定 |
| 🟢 低 | KujiUniverse、InvestUni 前端美化 | 視優先排序決定 |

**Oracle Cloud 遷移所需：**
1. SS 在 oracle.com/cloud/free 建立免費帳號（需信用卡驗證，不收費）
2. 開 Always Free VM instance（Ampere ARM 機型）
3. 提供 SSH key → Steve 完成後續設定

---

## 問題/風險

| 問題 | 詳情 | 嚴重性 |
|------|------|--------|
| **TG Bot 延遲** | GitHub Actions 免費 tier cron 在 UTC 白天（09:00-17:00 UTC）因 queue 擁擠，延遲 2-4 小時。17:00 HKT（09:00 UTC）和 21:30 HKT（13:30 UTC）均受影響。最近 21:30 HKT 通知於 00:18 HKT 才到，延遲 2h48m。 | 🔴 高（美股盤前通知幾乎失去時效性） |
| **08:00 HKT 準時** | 此 cron 對應 00:00 UTC（午夜），queue 幾乎空閒，不受影響。 | ✅ 無問題 |
| **根本解法未啟動** | Oracle Cloud VM 方案已規劃但尚未執行，待 SS 建立帳號後可快速完成。 | 🟡 待處理 |

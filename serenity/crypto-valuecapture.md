# 鏈 3：加密貨幣價值捕獲鏈

> ⚠️ 這條鏈的網站區塊**可能尚未建立**。首次執行需先 bootstrap，之後每週只做更新。

## 方法論變形說明
加密不是實體供應鏈，Serenity 的「咽喉」在這裡變成 **價值捕獲點**：整條加密經濟裡，真正收得到租/費、有護城河的環節在哪，而不是靠敘事炒作。分析軸線：
下游需求（用戶/機構）→ 應用（DeFi/RWA）→ 結算軌道（穩定幣/L2）→ 基礎設施（staking/驗證/節點）→ 底層（L1/礦機/電力）。
判斷 **誰真的在收費（fee capture / real yield）vs 誰只有敘事**。

## 首次執行：Bootstrap 新區塊（只在 `id="chain-crypto"` 不存在時做）
在 `index.html` 的產業鏈 Tab 內，**完整鏡射現有鏈的結構**新增第四條：
1. 在 `<div class="chain-selector">` 內、矽光子按鈕之後，加一顆按鈕：
   `<button class="chain-btn" id="chain-btn-crypto" onclick="showChain('crypto')">🪙 加密價值捕獲鏈</button>`
2. 在最後一條 `chain-panel` 之後，複製一份 `chain-panel` 結構，改成 `<div class="chain-panel" id="chain-crypto">`，內含：`bond-intro-box`（核心命題）、`chain-tier-grid`（上/中/下游或改為「底層/軌道/應用」三層）、`chain-bottleneck`（🔴 今日價值咽喉）、`options-section`（優先標的排序）、`chain-update`（今天日期）。
3. JS **不用改**：`showChain(id)`（約在 `index.html` 第 3678 行）是通用寫法，用 `document.getElementById('chain-' + id)` 與 `'chain-btn-' + id` 拼接。只要按鈕 id=`chain-btn-crypto`、面板 id=`chain-crypto` 對上，切換自動生效。**不要去動這個函式**，以免弄壞其他三條鏈。

上市可投資標的（美股/ADR 為主，符合 InvestUniS 定位；純幣種只當背景，不列為個股標的）：
COIN（Coinbase，交易所/結算）、CRCL 或穩定幣發行方相關、MSTR（BTC 代理）、CR?/礦企如 MARA・CLSK・RIOT（礦機/電力）、CRWV 等算力、以及 BTC/ETH 現貨 ETF（IBIT 等）作為底層敞口。上架前自行查證代號正確與可交易性。

## 本週研究關鍵字（WebSearch 起點）
穩定幣結算量 / USDC・USDT 供給、GENIUS Act / 穩定幣監管、RWA 代幣化規模、ETH staking real yield、L2 手續費捕獲、BTC 現貨 ETF 淨流入、礦企 hashprice / 電力成本、Coinbase 手續費與訂閱收入。

## 要判斷的核心問題
1. 本週最強的「價值咽喉」在哪——結算軌道（穩定幣）、staking real yield、還是交易所收費？
2. 誰真的在收費、現金流可驗證（財報/鏈上數據），誰只有敘事？
3. 監管（穩定幣立法、ETF）本週有無實質進展改變格局？

## 硬限制
- 只列**可在美股/ADR/ETF 管道投資**的標的；不提供買賣加密貨幣本身的操作建議。
- 鏈上數據可當佐證，但社群情緒只能當線索（Serenity 佐證等級 D）。

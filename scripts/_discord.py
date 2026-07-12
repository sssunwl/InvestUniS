"""把訊息鏡射到 Discord webhook(#n-investunis)。失敗絕不影響主流程。純 stdlib。

webhook URL 來源(依序):
  1. 環境變數 DISCORD_WEBHOOK_INVESTUNIS(GitHub Actions secret / Oracle VM 用這個)
  2. 環境變數 DISCORD_WEBHOOK
  3. ~/.config/sol/config.json 的 webhooks["n-investunis"](本機跑用這個)
沒設就安靜跳過。
"""
import os
import re
import sys
import json
import urllib.request

CHANNEL = "n-investunis"
ENV_VAR = "DISCORD_WEBHOOK_INVESTUNIS"


def _webhook_url():
    url = os.environ.get(ENV_VAR) or os.environ.get("DISCORD_WEBHOOK")
    if url:
        return url
    cfg = os.path.expanduser("~/.config/sol/config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, encoding="utf-8") as f:
                return json.load(f).get("webhooks", {}).get(CHANNEL)
        except Exception:
            return None
    return None


def _html_to_plain(t):
    # Telegram HTML → Discord 純文字:<a href="u">t</a> → "t (u)",其餘標籤去掉
    t = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', r'\2 (\1)', t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    return t


def notify_discord(text):
    url = _webhook_url()
    if not url or not str(url).startswith("https"):
        return
    body = _html_to_plain(text)[:1900]  # Discord 單則上限 2000 字
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"content": body}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SolBot (https://suniverse.local, 0.1)",
            },
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[discord] 通知失敗(不影響主流程): {e}", file=sys.stderr)

"""
カードマスタ更新バッチ
クラロワAPI /v1/cards から全カード情報を取得し、CardMasterシートに書き込む。
"""

import logging
import os
import sys

import gspread
import requests
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SHEET_NAME = "CardMaster"
HEADERS = ["Name", "IconURL", "ElixirCost", "Rarity"]


def main():
    load_dotenv()
    api_key = os.environ.get("CLASH_API_KEY", "").strip()
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "").strip()
    spreadsheet_key = os.environ.get("SPREADSHEET_KEY", "").strip()

    if not all([api_key, creds_path, spreadsheet_key]):
        logger.error(".env の CLASH_API_KEY, GOOGLE_SHEETS_CREDS_PATH, SPREADSHEET_KEY を確認してください。")
        sys.exit(1)

    # --- 1. APIからカード一覧取得 ---
    logger.info("クラロワAPIからカード一覧を取得中...")
    try:
        resp = requests.get(
            "https://api.clashroyale.com/v1/cards",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("API呼び出し失敗: %s", e)
        sys.exit(1)

    items = resp.json().get("items", [])
    logger.info("%d 枚のカードを取得", len(items))

    # --- 2. 行データ構築 ---
    rows = []
    for card in items:
        rows.append([
            card.get("name", ""),
            card.get("iconUrls", {}).get("medium", ""),
            card.get("elixirCost", ""),
            card.get("rarity", ""),
        ])
    rows.sort(key=lambda r: r[0])  # アルファベット順

    # --- 3. スプレッドシートに書き込み ---
    logger.info("スプレッドシートに接続中...")
    gc = gspread.service_account(filename=creds_path)
    sh = gc.open_by_key(spreadsheet_key)

    # 既存シートがあれば削除して再作成（上書き）
    try:
        old_ws = sh.worksheet(SHEET_NAME)
        sh.del_worksheet(old_ws)
        logger.info("既存の '%s' シートを削除", SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        pass

    ws = sh.add_worksheet(title=SHEET_NAME, rows=len(rows) + 1, cols=len(HEADERS))
    ws.append_row(HEADERS)
    ws.append_rows(rows, value_input_option="USER_ENTERED")

    logger.info("=== CardMaster 更新完了: %d 枚のカードを書き込みました ===", len(rows))


if __name__ == "__main__":
    main()

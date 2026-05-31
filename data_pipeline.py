"""
Clash Royale データ収集パイプライン
APIからバトルログを取得し、プレイヤーごとのワークシートに追記する。
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from datetime import datetime

import gspread
import pandas as pd
import requests
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

HEADERS = [
    "MatchID", "Timestamp", "GameMode", "MyDeck_Raw",
    "OpponentDeck_Raw", "Result", "MyCrowns", "OpponentCrowns",
    "MyTrophy", "OpponentTrophy", "MyTower", "OpponentTower",
]

EXCLUDED_BATTLE_TYPES = {"friendly"}


# ==========================================
# 1. 設定読み込み
# ==========================================
def load_config() -> dict:
    load_dotenv()
    required = {
        "CLASH_API_KEY": "Clash Royale APIキー",
        "PLAYER_TAGS": "プレイヤータグ（#なし、カンマ区切りで複数可）",
        "GOOGLE_SHEETS_CREDS_PATH": "サービスアカウントJSONのパス",
        "SPREADSHEET_KEY": "スプレッドシートID",
    }
    config = {}
    missing = []
    for key, label in required.items():
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(f"  - {key} ({label})")
        config[key] = val

    if missing:
        logger.error(".envに以下の変数が未設定です:\n%s", "\n".join(missing))
        sys.exit(1)

    # カンマ区切りのタグをリストに変換
    config["PLAYER_TAGS"] = [
        tag.strip() for tag in config["PLAYER_TAGS"].split(",") if tag.strip()
    ]
    return config


# ==========================================
# 2. API呼び出し
# ==========================================
def fetch_player_name(api_key: str, player_tag: str) -> str | None:
    """プレイヤー名をAPIから取得する。失敗時はNoneを返す。"""
    url = f"https://api.clashroyale.com/v1/players/%23{player_tag}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("name")
    except requests.exceptions.RequestException:
        pass
    return None


def fetch_battle_log(api_key: str, player_tag: str) -> list[dict] | None:
    """バトルログを取得する。失敗時はNoneを返す（複数プレイヤー処理を継続するため）。"""
    url = f"https://api.clashroyale.com/v1/players/%23{player_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        logger.error("[%s] ネットワークエラー: %s", player_tag, e)
        return None

    if resp.status_code == 200:
        return resp.json()

    if resp.status_code == 403:
        logger.error(
            "[%s] API 403: APIキーのIP制限に該当している可能性があります。\n"
            "https://developer.clashroyale.com でキーを再生成してください。",
            player_tag,
        )
    elif resp.status_code == 429:
        logger.error("[%s] API 429: レートリミット超過です。しばらく待ってください。", player_tag)
    else:
        logger.error("[%s] APIエラー %d: %s", player_tag, resp.status_code, resp.text)
    return None


# ==========================================
# 3. MatchID生成
# ==========================================
def generate_match_id(battle_time: str, my_tag: str, opp_tag: str) -> str:
    raw = f"{battle_time}_{my_tag}_{opp_tag}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def extract_tower_troop(player: dict) -> str:
    """supportCardsからタワートループ名を取り出す。存在しない場合はUnknownを返す。"""
    support_cards = player.get("supportCards") or []
    if not isinstance(support_cards, list) or not support_cards:
        return "Unknown"

    for card in support_cards:
        if isinstance(card, dict) and card.get("name"):
            return card["name"]
    return "Unknown"


# ==========================================
# 4. バトルログ整形
# ==========================================
def process_battle_log(raw_data: list[dict]) -> list[list]:
    rows = []
    skipped = 0

    for match in raw_data:
        if match.get("type") in EXCLUDED_BATTLE_TYPES:
            skipped += 1
            continue

        battle_time = match["battleTime"]
        dt = datetime.strptime(battle_time, "%Y%m%dT%H%M%S.%fZ")
        team = match["team"][0]
        opponent = match["opponent"][0]

        my_cards = ", ".join(card["name"] for card in team["cards"])
        opp_cards = ", ".join(card["name"] for card in opponent["cards"])
        my_tower = extract_tower_troop(team)
        opponent_tower = extract_tower_troop(opponent)

        if team["crowns"] > opponent["crowns"]:
            result = "Win"
        elif team["crowns"] < opponent["crowns"]:
            result = "Loss"
        else:
            result = "Draw"

        row = [
            generate_match_id(battle_time, team["tag"], opponent["tag"]),
            dt.strftime("%Y/%m/%d %H:%M"),
            match["type"],
            my_cards,
            opp_cards,
            result,
            team["crowns"],
            opponent["crowns"],
            team.get("startingTrophies", ""),
            opponent.get("startingTrophies", ""),
            my_tower,
            opponent_tower,
        ]
        rows.append(row)

    logger.info("整形完了: %d件の対象バトル（%d件スキップ）", len(rows), skipped)
    return rows


# ==========================================
# 5. Google Sheets接続
# ==========================================
def connect_to_spreadsheet(creds_path: str, spreadsheet_key: str) -> gspread.Spreadsheet:
    """スプレッドシートオブジェクトを返す。"""
    if not os.path.exists(creds_path):
        logger.error("サービスアカウントJSONが見つかりません: %s", creds_path)
        sys.exit(1)

    try:
        gc = gspread.service_account(filename=creds_path)
        return gc.open_by_key(spreadsheet_key)
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(
            "スプレッドシートが見つかりません。\n"
            "サービスアカウントのメールアドレスにシートを共有してください。"
        )
        sys.exit(1)


def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet, sheet_name: str
) -> gspread.Worksheet:
    """指定名のワークシートを取得する。存在しなければ新規作成しヘッダーを書き込む。"""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        logger.info("既存ワークシート '%s' を選択", sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(HEADERS))
        worksheet.append_row(HEADERS)
        logger.info("新規ワークシート '%s' を作成しヘッダーを初期化", sheet_name)
    else:
        existing_headers = worksheet.row_values(1)
        if existing_headers != HEADERS:
            worksheet.resize(cols=max(len(existing_headers), len(HEADERS)))
            worksheet.update("A1", [HEADERS])
            logger.info("ワークシート '%s' のヘッダーを更新しました", sheet_name)
    return worksheet


# ==========================================
# 6. 重複チェック & 追記
# ==========================================
def get_existing_ids(worksheet: gspread.Worksheet) -> set[str]:
    match_ids = worksheet.col_values(1)
    return set(match_ids[1:])  # ヘッダー行をスキップ


def append_new_rows(
    worksheet: gspread.Worksheet, rows: list[list], existing_ids: set[str]
) -> int:
    new_rows = [row for row in rows if row[0] not in existing_ids]

    if not new_rows:
        logger.info("新規データなし（全件が既存データと重複）")
        return 0

    worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
    logger.info("%d件の新規バトルをシートに追記しました", len(new_rows))
    return len(new_rows)


# ==========================================
# 7. メイン処理
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Clash Royale データ収集パイプライン")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Google Sheetsへの書き込みをスキップし、結果をコンソールに表示",
    )
    args = parser.parse_args()

    logger.info("=== Clash Royale データパイプライン開始 ===")
    config = load_config()
    player_tags = config["PLAYER_TAGS"]
    api_key = config["CLASH_API_KEY"]

    logger.info("対象プレイヤー: %d人 (%s)", len(player_tags), ", ".join(player_tags))

    # Sheets接続（dry-run以外）
    spreadsheet = None
    if not args.dry_run:
        spreadsheet = connect_to_spreadsheet(
            config["GOOGLE_SHEETS_CREDS_PATH"], config["SPREADSHEET_KEY"]
        )

    total_added = 0

    for i, tag in enumerate(player_tags):
        logger.info("--- [%d/%d] プレイヤー %s を処理中 ---", i + 1, len(player_tags), tag)

        # プレイヤー名取得
        player_name = fetch_player_name(api_key, tag)
        if player_name:
            sheet_name = player_name
            logger.info("プレイヤー名: %s", player_name)
        else:
            sheet_name = tag
            logger.warning("プレイヤー名を取得できませんでした。タグ '%s' をシート名に使用", tag)

        # Rate Limit対策: プレイヤー名取得後に待機
        time.sleep(1)

        # バトルログ取得
        raw_data = fetch_battle_log(api_key, tag)
        if not raw_data:
            logger.warning("[%s] バトルログが取得できません。スキップします。", tag)
            if i < len(player_tags) - 1:
                time.sleep(1)
            continue

        # データ整形
        rows = process_battle_log(raw_data)
        if not rows:
            logger.warning("[%s] 対象バトル（PvP / Path of Legend）なし。スキップ。", tag)
            if i < len(player_tags) - 1:
                time.sleep(1)
            continue

        if args.dry_run:
            df = pd.DataFrame(rows, columns=HEADERS)
            print(f"\n=== Dry Run [{sheet_name}] ({tag}) ===")
            print(df.to_string(index=False))
        else:
            worksheet = get_or_create_worksheet(spreadsheet, sheet_name)
            existing_ids = get_existing_ids(worksheet)
            count = append_new_rows(worksheet, rows, existing_ids)
            total_added += count

        # Rate Limit対策: 次のプレイヤー処理前に待機
        if i < len(player_tags) - 1:
            time.sleep(1)

    if args.dry_run:
        logger.info("Dry Runモード: Google Sheetsへの書き込みはスキップしました")
    else:
        logger.info("=== パイプライン完了: 全プレイヤー合計 %d件追加 ===", total_added)


if __name__ == "__main__":
    main()

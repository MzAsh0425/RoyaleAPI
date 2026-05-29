import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 設定（ご自身の情報に書き換えてください）
# ==========================================
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjQzOTk1NmRiLWZmNWEtNDBmMC04OGU3LTZmM2Q4ZTcyNDM2MCIsImlhdCI6MTc4MDA1MTU5MCwic3ViIjoiZGV2ZWxvcGVyL2RiYmFhN2JhLTRmMzQtY2EzZi01NjRhLTMyMjRlYThkODI4MiIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyIxMDMuNS4xNDAuMTcxIl0sInR5cGUiOiJjbGllbnQifV19.xKPBaKuIaCguK_M3X6fpvDWDhrB5TFU9Gp-Lqnl27p3d1osUJ7vVcJetfuV8mfC0zhESDBW9oysfVu09KdsALQ"
PLAYER_TAG = "P2VRRJCLQ" # 自分のプレイヤータグ（#は含めず、英数字のみ）

# ==========================================
# 2. クラロワAPIからバトルログを取得する関数
# ==========================================
def fetch_battle_log(api_key, player_tag):
    # プレイヤータグの先頭にはURLエンコードされた '#' (%23) が必要
    url = f"https://api.clashroyale.com/v1/players/%23{player_tag}/battlelog"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"エラーが発生しました: {response.status_code}")
        print(response.text)
        return None

# ==========================================
# 3. 取得したJSONデータを表形式に整形する関数
# ==========================================
def process_battle_log(raw_data):
    processed_matches = []
    
    for match in raw_data:
        # 1vs1の通常バトルやマルチのみを対象にする場合
        if match.get("type") not in ["PvP", "pathOfLegend"]:
            continue
            
        # 日時のフォーマット整形 (例: 20260529T103000.000Z -> 2026/05/29 10:30)
        raw_time = match["battleTime"]
        dt = datetime.strptime(raw_time, "%Y%m%dT%H%M%S.000Z")
        
        # 自分と相手のデータ
        team = match["team"][0]
        opponent = match["opponent"][0]
        
        # 8枚のカード名だけをリストとして抽出
        my_cards = [card["name"] for card in team["cards"]]
        opp_cards = [card["name"] for card in opponent["cards"]]
        
        # 勝敗判定
        if team["crowns"] > opponent["crowns"]:
            result = "勝ち"
        elif team["crowns"] < opponent["crowns"]:
            result = "負け"
        else:
            result = "引き分け"
            
        # 1試合分のデータを辞書にまとめる
        match_info = {
            "試合日時": dt.strftime("%Y/%m/%d %H:%M"),
            "ゲームモード": match["type"],
            "勝敗": result,
            "獲得クラウン": team["crowns"],
            "相手クラウン": opponent["crowns"],
            "自分のデッキ": ", ".join(my_cards),
            "相手のデッキ": ", ".join(opp_cards)
        }
        processed_matches.append(match_info)
        
    return pd.DataFrame(processed_matches)

# ==========================================
# 4. 実行部分
# ==========================================
if __name__ == "__main__":
    print("クラロワAPIからデータを取得中...")
    raw_log = fetch_battle_log(API_KEY, PLAYER_TAG)
    
    if raw_log:
        df = process_battle_log(raw_log)
        print("\n=== 直近のバトルログ取得成功！ ===")
        # 表をきれいに表示
        print(df.head(10))
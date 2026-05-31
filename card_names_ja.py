"""
クラッシュ・ロワイヤル カード名 英語→日本語 変換辞書
"""

CARD_NAME_EN_TO_JA: dict[str, str] = {
    # --- ユニット (コモン) ---
    "Archers": "アーチャー",
    "Barbarians": "バーバリアン",
    "Bats": "コウモリの群れ",
    "Bomber": "ボンバー",
    "Elite Barbarians": "エリートバーバリアン",
    "Fire Spirit": "ファイアスピリット",
    "Firecracker": "ファイアクラッカー",
    "Goblins": "ゴブリン",
    "Ice Spirit": "アイススピリット",
    "Knight": "ナイト",
    "Minion Horde": "ガーゴイルの群れ",
    "Minions": "ガーゴイル",
    "Royal Giant": "ロイヤルジャイアント",
    "Royal Hogs": "ロイヤルホグ",
    "Royal Recruits": "見習い親衛隊",
    "Skeleton Army": "スケルトン部隊",
    "Skeleton Barrel": "スケルトンバレル",
    "Skeleton Dragons": "スケルトンドラゴン",
    "Skeletons": "スケルトン",
    "Spear Goblins": "槍ゴブリン",
    "Wall Breakers": "ウォールブレイカー",
    # --- ユニット (レア) ---
    "Battle Healer": "バトルヒーラー",
    "Battle Ram": "攻城バーバリアン",
    "Dart Goblin": "吹き矢ゴブリン",
    "Elixir Golem": "エリクサーゴーレム",
    "Flying Machine": "ホバリング砲",
    "Giant": "ジャイアント",
    "Goblin Gang": "ゴブリンギャング",
    "Guards": "盾の戦士",
    "Heal Spirit": "ヒールスピリット",
    "Hog Rider": "ホグライダー",
    "Ice Golem": "アイスゴーレム",
    "Mega Minion": "メガガーゴイル",
    "Mini P.E.K.K.A": "ミニP.E.K.K.A",
    "Musketeer": "マスケット銃士",
    "Three Musketeers": "三銃士",
    "Valkyrie": "バルキリー",
    "Wizard": "ウィザード",
    "Zappies": "ザッピー",
    # --- ユニット (エピック) ---
    "Baby Dragon": "ベビードラゴン",
    "Balloon": "エアバルーン",
    "Bowler": "ボウラー",
    "Cannon Cart": "60式ムート",
    "Dark Prince": "ダークプリンス",
    "Electro Dragon": "ライトニングドラゴン",
    "Electro Spirit": "エレクトロスピリット",
    "Executioner": "執行人ファルチェ",
    "Giant Skeleton": "巨大スケルトン",
    "Goblin Giant": "ゴブジャイアント",
    "Golem": "ゴーレム",
    "Goblin Drill": "ゴブリンドリル",
    "Hunter": "ハンター",
    "P.E.K.K.A": "P.E.K.K.A",
    "Prince": "プリンス",
    "Rascals": "アウトロー",
    "Witch": "ネクロマンサー",
    # --- ユニット (レジェンダリー) ---
    "Bandit": "バンデット",
    "Electro Wizard": "エレクトロウィザード",
    "Fisherman": "フィッシャーマン",
    "Ghost": "ロイヤルゴースト",
    "Graveyard": "スケルトンラッシュ",
    "Ice Wizard": "アイスウィザード",
    "Inferno Dragon": "インフェルノドラゴン",
    "Lava Hound": "ラヴァハウンド",
    "Lumberjack": "ランバージャック",
    "Magic Archer": "マジックアーチャー",
    "Mega Knight": "メガナイト",
    "Miner": "ディガー",
    "Mother Witch": "マザーネクロマンサー",
    "Night Witch": "ダークネクロ",
    "Phoenix": "フェニックス",
    "Princess": "プリンセス",
    "Ram Rider": "ラムライダー",
    "Royal Ghost": "ロイヤルゴースト",
    "Sparky": "スパーキー",
    "Electro Giant": "エレクトロジャイアント",
    # --- チャンピオン ---
    "Archer Queen": "アーチャークイーン",
    "Golden Knight": "ゴールドナイト",
    "Little Prince": "リトルプリンス",
    "Mighty Miner": "マイティディガー",
    "Monk": "モンク",
    "Skeleton King": "スケルトンキング",
    # --- 呪文 ---
    "Arrows": "矢の雨",
    "Clone": "クローン",
    "Earthquake": "アースクエイク",
    "Fireball": "ファイアボール",
    "Freeze": "フリーズ",
    "Giant Snowball": "巨大雪玉",
    "Lightning": "ライトニング",
    "Mirror": "ミラー",
    "Poison": "ポイズン",
    "Rage": "レイジ",
    "Rocket": "ロケット",
    "Royal Delivery": "ロイヤルデリバリー",
    "The Log": "ローリングウッド",
    "Tornado": "トルネード",
    "Zap": "ザップ",
    "Barbarian Barrel": "ローリングバーバリアン",
    "Goblin Barrel": "ゴブリンバレル",
    # --- 建物 ---
    "Barbarian Hut": "バーバリアンの小屋",
    "Bomb Tower": "ボムタワー",
    "Cannon": "大砲",
    "Elixir Collector": "エリクサーポンプ",
    "オーブン": "ファーネス",
    "Goblin Cage": "ゴブリンの檻",
    "Goblin Hut": "ゴブリンの小屋",
    "Inferno Tower": "インフェルノタワー",
    "Mortar": "迫撃砲",
    "Tesla": "テスラ",
    "Tombstone": "墓石",
    "X-Bow": "クロスボウ",
    # --- 新カード (2024-2025追加) ---
    "Berserker": "バーサーカー",
    "Boss Bandit": "ボスアサシン",
    "Goblin Curse": "ゴブリンの呪い",
    "Goblin Demolisher": "ダイナマイトゴブリン",
    "Goblin Machine": "ゴブリンマシン",
    "Goblinstein": "ゴブリンシュタイン",
    "Rune Giant": "鍛冶屋ジャイアント",
    "Spirit Empress": "スピリットエンプレス",
    "Suspicious Bush": "ステルスブッシュ",
    "Vines": "ヴァイン",
    "Void": "ヴォイド",
    # --- タワートループ ---
    "Tower Princess": "タワープリンセス",
    "Cannoneer": "ブラスター",
    "Dagger Duchess": "ダガーガール",
    "Baby Goblin": "ベビーゴブリン",
}


def translate_card(name_en: str) -> str:
    """英語カード名を日本語に変換する。辞書にない場合は英語名をそのまま返す。"""
    if name_en is None:
        return "Unknown"
    name_en = str(name_en)
    if name_en.strip() == "" or name_en.strip().lower() == "nan":
        return "Unknown"
    return CARD_NAME_EN_TO_JA.get(name_en.strip(), name_en.strip())


def translate_deck(deck_raw: str) -> str:
    """カンマ区切りのデッキ文字列を日本語に変換する。"""
    if deck_raw is None:
        return "Unknown"
    deck_raw = str(deck_raw)
    if deck_raw.strip() == "" or deck_raw.strip().lower() == "nan":
        return "Unknown"
    cards = deck_raw.split(",")
    return ", ".join(translate_card(c) for c in cards)

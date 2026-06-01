"""
Clash Royale 戦績分析ダッシュボード
Google Sheetsからデータを読み込み、基礎分析・相性分析・統計EDAを表示する。
アーキタイプ分類はスプレッドシートの辞書シート(Archetype_Dict)で定義する。
"""

import json
import os
from itertools import combinations

import gspread
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from card_names_ja import translate_card, translate_deck

load_dotenv()

ARCHETYPE_SHEET_NAME = "Archetype_Dict"
SYSTEM_SHEETS = {"Archetype_Dict", "CardMaster"}
TOWER_COLUMNS = ["MyTower", "OpponentTower"]
JST_OFFSET_HOURS = 9

# ==========================================
# ページ設定
# ==========================================
st.set_page_config(
    page_title="クラロワ戦績分析",
    page_icon="🏆",
    layout="wide",
)


# ==========================================
# 認証（ローカル / Streamlit Cloud 両対応）
# ==========================================
def _get_gspread_client() -> gspread.Client:
    """環境に応じてgspreadクライアントを返す。"""
    # 1) Streamlit Cloud: st.secrets から認証
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        return gspread.service_account_from_dict(creds_dict)
    except (KeyError, FileNotFoundError):
        pass

    # 2) ローカル: .env の JSONファイルパスから認証
    creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "")
    if creds_path and os.path.exists(creds_path):
        return gspread.service_account(filename=creds_path)

    raise RuntimeError(
        "Google認証情報が見つかりません。\n"
        "ローカル: .env に GOOGLE_SHEETS_CREDS_PATH を設定\n"
        "Cloud: st.secrets に gcp_service_account を設定してください。"
    )


def _get_spreadsheet_key() -> str:
    """スプレッドシートキーを環境に応じて取得する。"""
    # st.secrets を優先
    try:
        return st.secrets["SPREADSHEET_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    return os.environ.get("SPREADSHEET_KEY", "")


# ==========================================
# データ読み込み（キャッシュ付き）
# ==========================================
@st.cache_data(ttl=3600)
def get_worksheet_names(spreadsheet_key: str) -> list[str]:
    """スプレッドシート内のワークシート名一覧を取得する。"""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_key)
    return [ws.title for ws in sh.worksheets()]


@st.cache_data(ttl=3600)
def load_player_data(spreadsheet_key: str, sheet_name: str) -> pd.DataFrame:
    """指定ワークシートの全データをDataFrameとして返す。"""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_key)
    ws = sh.worksheet(sheet_name)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    for col in TOWER_COLUMNS:
        if col not in df.columns:
            df[col] = "Unknown"
        df[col] = df[col].replace("", "Unknown").fillna("Unknown")
    # Spreadsheet timestamps are stored in UTC. Convert once at load time so all
    # dashboard grouping, sorting, and display logic uses JST.
    df["Timestamp"] = (
        pd.to_datetime(df["Timestamp"], format="%Y/%m/%d %H:%M")
        + pd.Timedelta(hours=JST_OFFSET_HOURS)
    )
    df["MyCrowns"] = pd.to_numeric(df["MyCrowns"], errors="coerce")
    df["OpponentCrowns"] = pd.to_numeric(df["OpponentCrowns"], errors="coerce")
    df["MyTrophy"] = pd.to_numeric(df["MyTrophy"], errors="coerce")
    df["OpponentTrophy"] = pd.to_numeric(df["OpponentTrophy"], errors="coerce")
    df = df.sort_values("Timestamp", ascending=False).reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def load_archetype_dict(spreadsheet_key: str) -> pd.DataFrame:
    """Archetype_Dictシートを読み込む。存在しなければ新規作成して空DataFrameを返す。"""
    gc = _get_gspread_client()
    sh = gc.open_by_key(spreadsheet_key)
    try:
        ws = sh.worksheet(ARCHETYPE_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=ARCHETYPE_SHEET_NAME, rows=50, cols=2)
        ws.append_row(["Archetype", "KeyCards"])
        return pd.DataFrame(columns=["Archetype", "KeyCards"])

    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Archetype", "KeyCards"])
    return pd.DataFrame(records)


# ==========================================
# 時間帯分類
# ==========================================
def classify_time_period(hour: int) -> str:
    if 6 <= hour < 12:
        return "朝 (6-11時)"
    elif 12 <= hour < 18:
        return "昼 (12-17時)"
    elif 18 <= hour < 24:
        return "夜 (18-23時)"
    else:
        return "深夜 (0-5時)"


TIME_PERIOD_ORDER = ["朝 (6-11時)", "昼 (12-17時)", "夜 (18-23時)", "深夜 (0-5時)"]


# ==========================================
# アーキタイプ分類（データ駆動型）
# ==========================================
def classify_archetype(deck_raw: str, archetype_df: pd.DataFrame) -> str:
    """辞書DataFrameのルールに基づき相手デッキのアーキタイプを判定する。"""
    if archetype_df.empty:
        return "Other"
    if deck_raw is None or str(deck_raw).strip() == "":
        return "Other"
    deck_raw = str(deck_raw)
    deck_cards = {c.strip() for c in deck_raw.split(",")}
    for _, row in archetype_df.iterrows():
        key_cards = {c.strip() for c in str(row["KeyCards"]).split(",")}
        if key_cards <= deck_cards:  # 全キーカードが含まれているか
            return row["Archetype"]
    return "Other"


# ==========================================
# メインアプリ
# ==========================================
def main():
    spreadsheet_key = _get_spreadsheet_key()

    if not spreadsheet_key:
        st.error("SPREADSHEET_KEY が未設定です。.env または st.secrets を確認してください。")
        return

    try:
        sheet_names = get_worksheet_names(spreadsheet_key)
    except Exception as e:
        st.error(f"スプレッドシートへの接続に失敗しました: {e}")
        return

    # プレイヤーシートのみ抽出（システムシートを除外）
    player_sheets = [s for s in sheet_names if s not in SYSTEM_SHEETS]

    if not player_sheets:
        st.warning("プレイヤーデータがありません。先に data_pipeline.py を実行してください。")
        return

    # アーキタイプ辞書の読み込み
    try:
        archetype_df = load_archetype_dict(spreadsheet_key)
    except Exception as e:
        st.error(f"アーキタイプ辞書の読み込みに失敗しました: {e}")
        archetype_df = pd.DataFrame(columns=["Archetype", "KeyCards"])

    # ------------------------------------------
    # サイドバー
    # ------------------------------------------
    st.sidebar.title("🎮 分析設定")
    selected_player = st.sidebar.selectbox("プレイヤーを選択", player_sheets)

    range_options = {"全期間": 0, "直近20戦": 20, "直近50戦": 50, "直近100戦": 100}
    selected_range = st.sidebar.selectbox("データ範囲", list(range_options.keys()))

    if st.sidebar.button("🔄 データを再読み込み"):
        st.cache_data.clear()
        st.rerun()

    # 辞書の状態をサイドバーに表示
    st.sidebar.divider()
    st.sidebar.subheader("🏷️ アーキタイプ辞書")
    if archetype_df.empty:
        st.sidebar.warning(
            f"辞書が空です。スプレッドシートの '{ARCHETYPE_SHEET_NAME}' シートに定義を追加してください。"
        )
    else:
        st.sidebar.success(f"{len(archetype_df)} 件の定義を読み込み済み")
        st.sidebar.dataframe(archetype_df, use_container_width=True, hide_index=True)

    # ------------------------------------------
    # データ読み込み
    # ------------------------------------------
    try:
        df_all = load_player_data(spreadsheet_key, selected_player)
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return

    if df_all.empty:
        st.warning(f"'{selected_player}' のデータがありません。")
        return

    n = range_options[selected_range]
    df = df_all.head(n) if n > 0 else df_all.copy()

    # アーキタイプ列を事前計算
    df["OppArchetype"] = df["OpponentDeck_Raw"].apply(
        lambda deck: classify_archetype(deck, archetype_df)
    )

    st.title(f"⚔️ {selected_player} の戦績分析")
    st.caption(f"総試合数: {len(df_all)}戦 ／ 表示中: {len(df)}戦（{selected_range}）")

    # ------------------------------------------
    # タブ構成
    # ------------------------------------------
    tab_basic, tab_matchup, tab_eda = st.tabs(["📊 基礎分析", "🎯 相性分析", "📈 統計・EDA"])

    with tab_basic:
        render_basic_analytics(df, df_all)

    with tab_matchup:
        render_matchup_analytics(df)

    with tab_eda:
        render_eda_analytics(df)


# ==========================================
# 基礎分析タブ
# ==========================================
def render_basic_analytics(df: pd.DataFrame, df_all: pd.DataFrame):
    # --- KPI サマリー ---
    st.header("📊 戦績サマリー")

    total = len(df)
    wins = (df["Result"] == "Win").sum()
    losses = (df["Result"] == "Loss").sum()
    draws = (df["Result"] == "Draw").sum()
    win_rate = wins / total * 100 if total > 0 else 0
    avg_my_crowns = df["MyCrowns"].mean()
    avg_opp_crowns = df["OpponentCrowns"].mean()

    df_recent = df_all.head(20)
    recent_total = len(df_recent)
    recent_wins = (df_recent["Result"] == "Win").sum()
    recent_rate = recent_wins / recent_total * 100 if recent_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("勝率", f"{win_rate:.1f}%", f"直近20戦: {recent_rate:.1f}%")
    col2.metric("勝敗", f"{wins}勝 {losses}敗 {draws}分")
    col3.metric("平均獲得クラウン", f"{avg_my_crowns:.2f}")
    col4.metric("平均喪失クラウン", f"{avg_opp_crowns:.2f}")

    st.divider()

    # --- デッキ別勝率ランキング ---
    st.header("🃏 デッキ別勝率ランキング")

    deck_stats = df.groupby("MyDeck_Raw").agg(
        使用回数=("Result", "size"),
        勝利数=("Result", lambda x: (x == "Win").sum()),
    ).reset_index()
    deck_stats["勝率"] = (deck_stats["勝利数"] / deck_stats["使用回数"] * 100).round(1)
    deck_stats = deck_stats.sort_values("使用回数", ascending=False).reset_index(drop=True)
    deck_stats.index += 1
    deck_stats = deck_stats.rename(columns={"MyDeck_Raw": "デッキ"})
    deck_stats["デッキ"] = deck_stats["デッキ"].apply(translate_deck)

    st.dataframe(
        deck_stats[["デッキ", "使用回数", "勝利数", "勝率"]].style.format({"勝率": "{:.1f}%"}),
        use_container_width=True,
        height=min(400, 35 * len(deck_stats) + 38),
    )

    st.divider()

    # --- 時間帯別パフォーマンス ---
    st.header("🕐 時間帯別パフォーマンス")

    df_time = df.copy()
    df_time["時間帯"] = df_time["Timestamp"].dt.hour.apply(classify_time_period)

    time_stats = df_time.groupby("時間帯").agg(
        試合数=("Result", "size"),
        勝利数=("Result", lambda x: (x == "Win").sum()),
    ).reset_index()
    time_stats["勝率"] = (time_stats["勝利数"] / time_stats["試合数"] * 100).round(1)
    time_stats["時間帯"] = pd.Categorical(time_stats["時間帯"], categories=TIME_PERIOD_ORDER, ordered=True)
    time_stats = time_stats.sort_values("時間帯").reset_index(drop=True)

    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(time_stats.set_index("時間帯")["勝率"], horizontal=False)
    with col_table:
        st.dataframe(
            time_stats[["時間帯", "試合数", "勝利数", "勝率"]].style.format({"勝率": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )


# ==========================================
# 相性分析タブ
# ==========================================
def render_matchup_analytics(df: pd.DataFrame):

    # --- B-1. アーキタイプ別勝率 ---
    st.header("🏷️ 相手アーキタイプ別勝率")

    arch_stats = df.groupby("OppArchetype").agg(
        試合数=("Result", "size"),
        勝利数=("Result", lambda x: (x == "Win").sum()),
    ).reset_index()
    arch_stats["勝率"] = (arch_stats["勝利数"] / arch_stats["試合数"] * 100).round(1)
    arch_stats = arch_stats.sort_values("試合数", ascending=False).reset_index(drop=True)
    arch_stats = arch_stats.rename(columns={"OppArchetype": "アーキタイプ"})

    col_chart, col_table = st.columns([2, 1])
    with col_chart:
        st.bar_chart(arch_stats.set_index("アーキタイプ")["勝率"])
    with col_table:
        st.dataframe(
            arch_stats.style.format({"勝率": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # --- B-2. 対面相性マトリクス ---
    st.header("📋 対面相性マトリクス")
    st.caption("自分のデッキ（行） × 相手のアーキタイプ（列） の勝率")

    min_games = st.slider("デッキの最低使用回数", min_value=1, max_value=20, value=2, key="matrix_min")
    deck_counts = df["MyDeck_Raw"].value_counts()
    valid_decks = deck_counts[deck_counts >= min_games].index

    df_filtered = df[df["MyDeck_Raw"].isin(valid_decks)]

    if df_filtered.empty:
        st.info("条件に合うデータがありません。最低使用回数を下げてみてください。")
    else:
        df_filtered = df_filtered.copy()
        df_filtered["IsWin"] = (df_filtered["Result"] == "Win").astype(int)

        pivot_rate = pd.pivot_table(
            df_filtered, values="IsWin", index="MyDeck_Raw",
            columns="OppArchetype", aggfunc="mean",
        ).mul(100).round(1)

        pivot_count = pd.pivot_table(
            df_filtered, values="IsWin", index="MyDeck_Raw",
            columns="OppArchetype", aggfunc="count",
        ).fillna(0).astype(int)

        # 文字列型DataFrameで「勝率% (試合数)」を構築
        display = pd.DataFrame(index=pivot_rate.index, columns=pivot_rate.columns, dtype=str)
        for col in display.columns:
            for idx in display.index:
                rate = pivot_rate.at[idx, col] if pd.notna(pivot_rate.at[idx, col]) else None
                count = pivot_count.at[idx, col] if idx in pivot_count.index and col in pivot_count.columns else 0
                if rate is not None and count > 0:
                    display.at[idx, col] = f"{rate:.0f}% ({int(count)})"
                else:
                    display.at[idx, col] = "-"

        display.index = [translate_deck(d) for d in display.index]
        display.index.name = "自分のデッキ"
        st.dataframe(display, use_container_width=True)

    st.divider()

    # --- B-3. 特定カード天敵・シナジー分析 ---
    st.header("🔍 特定カード天敵・シナジー分析")
    st.caption("相手のデッキに特定カードが含まれていた場合の勝率変動")

    all_opp_cards_en = set()
    for deck in df["OpponentDeck_Raw"]:
        for card in deck.split(","):
            all_opp_cards_en.add(card.strip())
    all_opp_cards_en = sorted(all_opp_cards_en)

    # 日本語名でドロップダウン表示 → 英語名に逆引き
    ja_to_en = {translate_card(c): c for c in all_opp_cards_en}
    card_options_ja = sorted(ja_to_en.keys())

    selected_card_ja = st.selectbox("分析するカードを選択", card_options_ja, key="card_select")
    selected_card_en = ja_to_en[selected_card_ja]

    df_with = df[df["OpponentDeck_Raw"].str.contains(selected_card_en, regex=False)]
    df_without = df[~df["OpponentDeck_Raw"].str.contains(selected_card_en, regex=False)]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"✅ {selected_card_ja} あり")
        total_w = len(df_with)
        if total_w > 0:
            wins_w = (df_with["Result"] == "Win").sum()
            rate_w = wins_w / total_w * 100
            st.metric("勝率", f"{rate_w:.1f}%")
            st.metric("試合数", f"{total_w}戦")
        else:
            st.info("該当データなし")

    with col2:
        st.subheader(f"❌ {selected_card_ja} なし")
        total_wo = len(df_without)
        if total_wo > 0:
            wins_wo = (df_without["Result"] == "Win").sum()
            rate_wo = wins_wo / total_wo * 100
            st.metric("勝率", f"{rate_wo:.1f}%")
            st.metric("試合数", f"{total_wo}戦")
        else:
            st.info("該当データなし")

    if len(df_with) > 0 and len(df_without) > 0:
        diff = rate_w - rate_wo
        if diff > 0:
            st.success(f"📈 {selected_card_ja} がいる方が **+{diff:.1f}%** 勝ちやすい")
        elif diff < 0:
            st.error(f"📉 {selected_card_ja} がいると **{diff:.1f}%** 勝率が下がる（天敵候補）")
        else:
            st.info("勝率に差はありません")


# ==========================================
# 統計・EDAタブ
# ==========================================
TROPHY_BINS = [-9999, -100, -30, 30, 100, 9999]
TROPHY_LABELS = ["格下 (< -100)", "やや格下 (-100~-30)", "同格 (-29~+29)", "やや格上 (+30~+99)", "格上 (100+)"]

DAY_NAMES = ["月", "火", "水", "木", "金", "土", "日"]
HOURS_24 = list(range(24))


def render_eda_analytics(df: pd.DataFrame):

    # ==============================================
    # C-1. トロフィー差・格上/格下分析
    # ==============================================
    st.header("🏆 トロフィー差分析")

    df_trophy = df.dropna(subset=["MyTrophy", "OpponentTrophy"]).copy()

    if df_trophy.empty:
        st.info("トロフィーデータがありません。")
    else:
        df_trophy["TrophyDiff"] = df_trophy["MyTrophy"] - df_trophy["OpponentTrophy"]
        df_trophy["TrophyBin"] = pd.cut(
            df_trophy["TrophyDiff"], bins=TROPHY_BINS, labels=TROPHY_LABELS, ordered=True,
        )

        trophy_stats = df_trophy.groupby("TrophyBin", observed=False).agg(
            試合数=("Result", "size"),
            勝利数=("Result", lambda x: (x == "Win").sum()),
        ).reset_index()
        trophy_stats["勝率"] = (trophy_stats["勝利数"] / trophy_stats["試合数"] * 100).round(1)
        trophy_stats["勝率"] = trophy_stats["勝率"].fillna(0)

        fig = px.bar(
            trophy_stats, x="TrophyBin", y="勝率",
            text="勝率", color="勝率",
            color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
            labels={"TrophyBin": "トロフィー差", "勝率": "勝率 (%)"},
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            showlegend=False, coloraxis_showscale=False,
            yaxis_range=[0, max(trophy_stats["勝率"].max() + 15, 100)],
            height=400,
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.dataframe(
                trophy_stats.rename(columns={"TrophyBin": "区分"})[["区分", "試合数", "勝利数", "勝率"]]
                    .style.format({"勝率": "{:.1f}%"}),
                use_container_width=True, hide_index=True,
            )

    st.divider()

    # ==============================================
    # C-2. タワートループ分析
    # ==============================================
    st.header("🏰 タワートループ分析")

    df_tower = df.copy()
    for col in TOWER_COLUMNS:
        if col not in df_tower.columns:
            df_tower[col] = "Unknown"
        df_tower[col] = df_tower[col].replace("", "Unknown").fillna("Unknown")
        df_tower[f"{col}_JA"] = df_tower[col].apply(translate_card)

    df_tower["IsWin"] = (df_tower["Result"] == "Win").astype(int)
    df_tower_known_opp = df_tower[df_tower["OpponentTower"] != "Unknown"].copy()

    if df_tower_known_opp.empty:
        st.info("相手タワーが記録されたデータがまだありません。")
    else:
        tower_stats = df_tower_known_opp.groupby("OpponentTower_JA").agg(
            試合数=("Result", "size"),
            勝利数=("IsWin", "sum"),
            勝率=("IsWin", "mean"),
        ).reset_index()
        tower_stats["勝率"] = (tower_stats["勝率"] * 100).round(1)
        tower_stats = tower_stats.sort_values("試合数", ascending=False).reset_index(drop=True)
        tower_stats = tower_stats.rename(columns={"OpponentTower_JA": "相手のタワー"})

        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            fig_tower = px.bar(
                tower_stats, x="相手のタワー", y="勝率",
                text="勝率", color="勝率",
                color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                labels={"勝率": "勝率 (%)"},
            )
            fig_tower.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_tower.update_layout(
                showlegend=False, coloraxis_showscale=False,
                yaxis_range=[0, max(tower_stats["勝率"].max() + 15, 100)],
                height=380,
            )
            st.plotly_chart(fig_tower, use_container_width=True)
        with col_table:
            st.dataframe(
                tower_stats[["相手のタワー", "試合数", "勝利数", "勝率"]]
                    .style.format({"勝率": "{:.1f}%"}),
                use_container_width=True, hide_index=True,
            )

    df_tower_known_my = df_tower[df_tower["MyTower"] != "Unknown"].copy()
    my_tower_stats = df_tower_known_my.groupby("MyTower_JA").agg(
        試合数=("Result", "size"),
        勝利数=("IsWin", "sum"),
        勝率=("IsWin", "mean"),
    ).reset_index()
    if not my_tower_stats.empty:
        my_tower_stats["勝率"] = (my_tower_stats["勝率"] * 100).round(1)
        my_tower_stats = my_tower_stats.sort_values("試合数", ascending=False)
        my_tower_stats = my_tower_stats.rename(columns={"MyTower_JA": "自分のタワー"})

        with st.expander("自分のタワー別使用状況"):
            st.dataframe(
                my_tower_stats[["自分のタワー", "試合数", "勝利数", "勝率"]]
                    .style.format({"勝率": "{:.1f}%"}),
                use_container_width=True, hide_index=True,
            )

    st.subheader("自分のデッキ × 相手タワー 勝率")
    deck_counts = df_tower_known_opp["MyDeck_Raw"].value_counts()
    valid_decks = deck_counts[deck_counts >= 1].index
    df_tower_matrix = df_tower_known_opp[df_tower_known_opp["MyDeck_Raw"].isin(valid_decks)].copy()

    if df_tower_matrix.empty:
        st.info("タワートループ分析に使えるデータがありません。")
    else:
        pivot_rate = pd.pivot_table(
            df_tower_matrix, values="IsWin", index="MyDeck_Raw",
            columns="OpponentTower_JA", aggfunc="mean",
        ).mul(100).round(1)
        pivot_count = pd.pivot_table(
            df_tower_matrix, values="IsWin", index="MyDeck_Raw",
            columns="OpponentTower_JA", aggfunc="count",
        ).fillna(0).astype(int)

        display = pd.DataFrame(index=pivot_rate.index, columns=pivot_rate.columns, dtype=str)
        for col in display.columns:
            for idx in display.index:
                rate = pivot_rate.at[idx, col] if pd.notna(pivot_rate.at[idx, col]) else None
                count = pivot_count.at[idx, col] if idx in pivot_count.index and col in pivot_count.columns else 0
                display.at[idx, col] = f"{rate:.0f}% ({int(count)})" if rate is not None and count > 0 else "-"

        display.index = [translate_deck(d) for d in display.index]
        display.index.name = "自分のデッキ"
        st.dataframe(display, use_container_width=True)

    st.subheader("相手タワー別 相手カード使用ランキング")
    if df_tower_known_opp.empty:
        st.info("相手タワーが記録されたデータがまだありません。")
    else:
        top_cards_per_tower = st.slider(
            "タワーごとに表示する相手カード数",
            min_value=1,
            max_value=20,
            value=10,
            key="opp_tower_card_top_n",
        )

        tower_totals = df_tower_known_opp.groupby("OpponentTower_JA").size()
        opponent_card_by_tower = df_tower_known_opp.copy()
        opponent_card_by_tower["OpponentCard"] = opponent_card_by_tower["OpponentDeck_Raw"].apply(
            lambda deck: [
                card.strip()
                for card in str(deck).split(",")
                if card.strip()
            ]
        )
        opponent_card_by_tower = opponent_card_by_tower.explode("OpponentCard")
        opponent_card_by_tower = opponent_card_by_tower.dropna(subset=["OpponentCard"])

        opponent_card_by_tower = opponent_card_by_tower.groupby(
            ["OpponentTower_JA", "OpponentCard"]
        ).agg(
            使用回数=("Result", "size"),
            勝利数=("IsWin", "sum"),
        ).reset_index()
        opponent_card_by_tower["採用率"] = (
            opponent_card_by_tower["使用回数"]
            / opponent_card_by_tower["OpponentTower_JA"].map(tower_totals)
            * 100
        ).round(1)
        opponent_card_by_tower["こちらの勝率"] = (
            opponent_card_by_tower["勝利数"] / opponent_card_by_tower["使用回数"] * 100
        ).round(1)
        opponent_card_by_tower = opponent_card_by_tower.sort_values(
            ["OpponentTower_JA", "使用回数", "採用率"],
            ascending=[True, False, False],
        )
        opponent_card_by_tower = opponent_card_by_tower.groupby(
            "OpponentTower_JA", group_keys=False
        ).head(top_cards_per_tower)
        opponent_card_by_tower = opponent_card_by_tower.rename(
            columns={
                "OpponentTower_JA": "相手のタワー",
                "OpponentCard": "相手のカード",
            }
        )
        opponent_card_by_tower["相手のカード"] = opponent_card_by_tower["相手のカード"].apply(
            translate_card
        )

        st.dataframe(
            opponent_card_by_tower[
                ["相手のタワー", "相手のカード", "使用回数", "採用率", "こちらの勝率"]
            ].style.format({"採用率": "{:.1f}%", "こちらの勝率": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ==============================================
    # C-3. 曜日×時間帯ヒートマップ
    # ==============================================
    st.header("📅 曜日×時間帯パフォーマンス")

    df_dt = df.copy()
    df_dt["Hour"] = df_dt["Timestamp"].dt.hour
    df_dt["DayOfWeek"] = df_dt["Timestamp"].dt.dayofweek  # 0=月曜
    df_dt["DayName"] = df_dt["DayOfWeek"].map(dict(enumerate(DAY_NAMES)))
    df_dt["IsWin"] = (df_dt["Result"] == "Win").astype(int)

    # ヒートマップ用ピボット（勝率）
    pivot_wr = pd.pivot_table(
        df_dt, values="IsWin", index="DayOfWeek", columns="Hour",
        aggfunc="mean",
    ).reindex(index=range(7), columns=HOURS_24).mul(100).round(1)
    pivot_wr.index = [DAY_NAMES[i] for i in pivot_wr.index]

    # 試合数ピボット（ホバーテキスト用）
    pivot_cnt = pd.pivot_table(
        df_dt, values="IsWin", index="DayOfWeek", columns="Hour",
        aggfunc="count",
    ).reindex(index=range(7), columns=HOURS_24).fillna(0).astype(int)
    pivot_cnt.index = [DAY_NAMES[i] for i in pivot_cnt.index]

    # カスタムホバーテキスト
    hover_text = []
    for day in pivot_wr.index:
        row_text = []
        for hour in HOURS_24:
            wr = pivot_wr.at[day, hour] if pd.notna(pivot_wr.at[day, hour]) else 0
            cnt = pivot_cnt.at[day, hour] if day in pivot_cnt.index and hour in pivot_cnt.columns else 0
            row_text.append(f"{day} {hour}時<br>勝率: {wr:.0f}%<br>試合数: {int(cnt)}")
        hover_text.append(row_text)

    fig_hm = go.Figure(data=go.Heatmap(
        z=pivot_wr.values,
        x=[f"{h}時" for h in HOURS_24],
        y=pivot_wr.index,
        text=hover_text,
        hoverinfo="text",
        colorscale=[[0, "#e74c3c"], [0.5, "#f5f5dc"], [1, "#2ecc71"]],
        zmid=50,
        colorbar=dict(title="勝率%"),
    ))
    fig_hm.update_layout(height=350, yaxis=dict(autorange="reversed"))

    st.plotly_chart(fig_hm, use_container_width=True)

    st.divider()

    # ==============================================
    # C-4. メンタル・ティルト分析
    # ==============================================
    st.header("🧠 メンタル・ティルト分析")

    df_streak = df.sort_values("Timestamp").reset_index(drop=True).copy()
    df_streak["PrevResult"] = df_streak["Result"].shift(1)
    df_streak["IsWin"] = (df_streak["Result"] == "Win").astype(int)

    # 連勝/連敗ストリークを計算
    streaks = []
    current_result = None
    current_len = 0
    for _, row in df_streak.iterrows():
        if row["Result"] == current_result:
            current_len += 1
        else:
            current_result = row["Result"]
            current_len = 1
        streaks.append(current_len)
    df_streak["StreakLen"] = streaks

    # 前戦の結果ごとの次戦勝率
    df_with_prev = df_streak.dropna(subset=["PrevResult"])

    if df_with_prev.empty:
        st.info("連戦データが不足しています。")
    else:
        prev_stats = df_with_prev.groupby("PrevResult").agg(
            試合数=("IsWin", "size"),
            勝利数=("IsWin", "sum"),
        ).reset_index()
        prev_stats["次戦勝率"] = (prev_stats["勝利数"] / prev_stats["試合数"] * 100).round(1)
        prev_stats = prev_stats.rename(columns={"PrevResult": "前戦の結果"})

        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("前戦の結果 → 次戦の勝率")
            fig_prev = px.bar(
                prev_stats, x="前戦の結果", y="次戦勝率",
                text="次戦勝率", color="前戦の結果",
                color_discrete_map={"Win": "#2ecc71", "Loss": "#e74c3c", "Draw": "#95a5a6"},
            )
            fig_prev.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_prev.update_layout(showlegend=False, yaxis_range=[0, 100], height=350)
            st.plotly_chart(fig_prev, use_container_width=True)

        with col2:
            st.subheader("連敗数と次戦勝率の関係")
            # 連敗中（直前が負け）のデータだけ抽出
            df_losing = df_streak[df_streak["PrevResult"] == "Loss"].copy()
            # 直前までの連敗数を計算
            lose_streaks_before = []
            streak_count = 0
            prev_r = None
            for _, row in df_streak.iterrows():
                if prev_r == "Loss":
                    streak_count += 1
                else:
                    streak_count = 0
                lose_streaks_before.append(streak_count)
                prev_r = row["Result"]
            df_streak["LoseStreakBefore"] = lose_streaks_before

            df_tilt = df_streak[df_streak["LoseStreakBefore"] > 0].copy()
            df_tilt["LoseStreakBefore"] = df_tilt["LoseStreakBefore"].clip(upper=5)
            if not df_tilt.empty:
                tilt_stats = df_tilt.groupby("LoseStreakBefore").agg(
                    試合数=("IsWin", "size"),
                    勝率=("IsWin", "mean"),
                ).reset_index()
                tilt_stats["勝率"] = (tilt_stats["勝率"] * 100).round(1)
                tilt_stats = tilt_stats.rename(columns={"LoseStreakBefore": "直前連敗数"})
                tilt_stats["直前連敗数"] = tilt_stats["直前連敗数"].astype(str) + "連敗後"
                fig_tilt = px.bar(
                    tilt_stats, x="直前連敗数", y="勝率",
                    text="勝率", color="勝率",
                    color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                )
                fig_tilt.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_tilt.update_layout(
                    showlegend=False, coloraxis_showscale=False,
                    yaxis_range=[0, 100], height=350,
                )
                st.plotly_chart(fig_tilt, use_container_width=True)
            else:
                st.info("連敗データが不足しています。")

    st.divider()

    # ==============================================
    # C-5. カード共起分析（環境シナジー）
    # ==============================================
    st.header("🔗 カード共起分析（環境シナジー）")
    st.caption("相手のデッキ内でよく一緒に採用されるカードの組み合わせ")

    top_n = st.slider("表示する組み合わせ数", min_value=5, max_value=30, value=15, key="cooccur_n")

    pair_counts: dict[tuple, int] = {}
    for deck in df["OpponentDeck_Raw"]:
        cards = sorted(c.strip() for c in deck.split(","))
        for pair in combinations(cards, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    if not pair_counts:
        st.info("データが不足しています。")
    else:
        pair_df = pd.DataFrame(
            [(a, b, cnt) for (a, b), cnt in pair_counts.items()],
            columns=["Card_A", "Card_B", "共起回数"],
        )
        pair_df = pair_df.sort_values("共起回数", ascending=False).head(top_n).reset_index(drop=True)
        pair_df["Card_A_JA"] = pair_df["Card_A"].apply(translate_card)
        pair_df["Card_B_JA"] = pair_df["Card_B"].apply(translate_card)
        pair_df["組み合わせ"] = pair_df["Card_A_JA"] + "  +  " + pair_df["Card_B_JA"]
        pair_df["採用率"] = (pair_df["共起回数"] / len(df) * 100).round(1)

        fig_co = px.bar(
            pair_df.iloc[::-1], x="共起回数", y="組み合わせ",
            orientation="h", text="共起回数",
            color="共起回数",
            color_continuous_scale="Viridis",
        )
        fig_co.update_layout(
            showlegend=False, coloraxis_showscale=False,
            height=max(400, top_n * 28),
            yaxis=dict(tickfont=dict(size=11)),
        )
        fig_co.update_traces(textposition="outside")
        st.plotly_chart(fig_co, use_container_width=True)

        with st.expander("詳細テーブル"):
            st.dataframe(
                pair_df[["Card_A_JA", "Card_B_JA", "共起回数", "採用率"]]
                    .rename(columns={"Card_A_JA": "カードA", "Card_B_JA": "カードB"})
                    .style.format({"採用率": "{:.1f}%"}),
                use_container_width=True, hide_index=True,
            )


if __name__ == "__main__":
    main()

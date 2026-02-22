import streamlit as st
import feedparser
import re
from urllib.parse import quote
from datetime import datetime
from html import escape


# ─── ページ設定 ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI ニュース収集ダッシュボード",
    page_icon="📰",
    layout="wide",
)

# ─── カスタム CSS ────────────────────────────────────────────
st.markdown("""
<style>
/* ---------- 全体テーマ ---------- */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif;
}

/* ---------- ヘッダー ---------- */
.dashboard-header {
    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    color: #ffffff;
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(48, 43, 99, .35);
}
.dashboard-header h1 {
    margin: 0;
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: .04em;
}
.dashboard-header p {
    margin: .5rem 0 0;
    opacity: .8;
    font-size: 1rem;
}

/* ---------- ニュースカード ---------- */
.news-card {
    background: linear-gradient(145deg, #1e1e2f 0%, #2a2a40 100%);
    border: 1px solid rgba(255, 255, 255, .08);
    border-radius: 14px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.2rem;
    transition: transform .25s ease, box-shadow .25s ease;
    box-shadow: 0 4px 20px rgba(0, 0, 0, .25);
}
.news-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 36px rgba(100, 80, 255, .2);
    border-color: rgba(100, 80, 255, .3);
}
.news-card .card-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #e0e0ff;
    margin: 0 0 .6rem;
    line-height: 1.5;
}
.news-card .card-date {
    font-size: .82rem;
    color: #8888cc;
    margin-bottom: .7rem;
    display: flex;
    align-items: center;
    gap: .4rem;
}
.news-card .card-summary {
    font-size: .93rem;
    color: #b0b0d0;
    line-height: 1.7;
    margin-bottom: 1rem;
}
.news-card .card-link a {
    display: inline-block;
    background: linear-gradient(135deg, #6c63ff, #48c6ef);
    color: #fff !important;
    text-decoration: none;
    padding: .45rem 1.2rem;
    border-radius: 8px;
    font-size: .85rem;
    font-weight: 500;
    transition: opacity .2s;
}
.news-card .card-link a:hover {
    opacity: .85;
}

/* ---------- 統計バッジ ---------- */
.stat-badge {
    background: linear-gradient(135deg, #6c63ff 0%, #48c6ef 100%);
    color: #fff;
    padding: 1rem 1.5rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(108, 99, 255, .3);
}
.stat-badge .stat-number {
    font-size: 2rem;
    font-weight: 700;
    display: block;
}
.stat-badge .stat-label {
    font-size: .85rem;
    opacity: .85;
}

/* ---------- サイドバー ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #13111c 0%, #1a1830 100%);
}

/* ---------- 空ステート ---------- */
.empty-state {
    text-align: center;
    padding: 3rem;
    color: #888;
    font-size: 1.1rem;
}
</style>
""", unsafe_allow_html=True)


# ─── データ取得 ──────────────────────────────────────────────
@st.cache_data(ttl=300)  # 5 分キャッシュ
def fetch_news(query: str, num: int = 20) -> tuple[list[dict[str, str]], str]:
    """Google News RSS から記事を取得する"""
    encoded = quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
    )
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:num]:
        # 日付のパース
        published = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                parts: tuple[int, ...] = tuple(entry.published_parsed[:6])
                dt = datetime(*parts)
                published = dt.strftime("%Y年%m月%d日 %H:%M")
            except Exception:
                published = getattr(entry, "published", "")
        elif hasattr(entry, "published"):
            published = entry.published

        # 要約テキスト（HTMLタグ除去）
        summary: str = getattr(entry, "summary", "")
        # 簡易的なHTMLタグ除去
        summary = str(re.sub(r"<[^>]+>", "", summary)).strip()
        if len(summary) > 300:
            summary = summary[:300] + "…"

        # タイトルもサニタイズしてXSSを防止
        safe_title = escape(entry.title)
        safe_summary = escape(summary) if summary else "要約はありません。"

        articles.append({
            "title": safe_title,
            "link": entry.link,
            "published": published,
            "summary": safe_summary,
        })
    return articles, url


# ─── サイドバー ──────────────────────────────────────────────
# クイックタグが押された場合のデフォルト値を設定
default_query = st.session_state.pop("quick_query", "Artificial Intelligence")

with st.sidebar:
    st.markdown("## 🔍 検索設定")
    query = st.text_input(
        "検索キーワード",
        value=default_query,
        placeholder="例: ChatGPT, 生成AI, LLM …",
    )
    num_articles = st.slider("表示件数", min_value=5, max_value=30, value=15, step=5)

    st.markdown("---")
    st.markdown("### 🏷️ クイックタグ")
    quick_tags = ["ChatGPT", "生成AI", "LLM", "機械学習", "ロボティクス", "自動運転"]
    cols = st.columns(2)
    for i, tag in enumerate(quick_tags):
        with cols[i % 2]:
            if st.button(tag, key=f"tag_{tag}", use_container_width=True):
                st.session_state["quick_query"] = tag
                st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:#666;font-size:.8rem;'>"
        "📡 データソース: Google News RSS<br>"
        f"⏰ 最終更新: {datetime.now().strftime('%H:%M:%S')}"
        "</div>",
        unsafe_allow_html=True,
    )

# ─── メインコンテンツ ────────────────────────────────────────
# ヘッダー
st.markdown(
    '<div class="dashboard-header">'
    "<h1>📰 AI ニュース収集ダッシュボード</h1>"
    "<p>Google News RSS から最新の AI 関連ニュースをリアルタイム収集</p>"
    "</div>",
    unsafe_allow_html=True,
)

# 記事取得
with st.spinner("🔄 ニュースを取得中…"):
    articles, _ = fetch_news(query, num_articles)

# 統計
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f'<div class="stat-badge">'
        f'<span class="stat-number">{len(articles)}</span>'
        f'<span class="stat-label">取得記事数</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f'<div class="stat-badge">'
        f'<span class="stat-number">🔎</span>'
        f'<span class="stat-label">{query}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f'<div class="stat-badge">'
        f'<span class="stat-number">🕐</span>'
        f'<span class="stat-label">{datetime.now().strftime("%Y/%m/%d %H:%M")}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ニュースカード一覧
if articles:
    # 2 カラムレイアウト
    left, right = st.columns(2)
    for idx, article in enumerate(articles):  # type: ignore[arg-type]
        target = left if idx % 2 == 0 else right
        with target:
            st.markdown(
                f'<div class="news-card">'
                f'  <div class="card-title">{article["title"]}</div>'
                f'  <div class="card-date">🗓️ {article["published"]}</div>'
                f'  <div class="card-summary">{article["summary"]}</div>'
                f'  <div class="card-link">'
                f'    <a href="{article["link"]}" target="_blank">📖 元記事を読む</a>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
else:
    st.markdown(
        '<div class="empty-state">'
        "😔 ニュースが見つかりませんでした。<br>検索キーワードを変えてお試しください。"
        "</div>",
        unsafe_allow_html=True,
    )

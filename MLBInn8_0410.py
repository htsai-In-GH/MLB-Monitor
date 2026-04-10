import time
import requests
from datetime import datetime, timedelta
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MLB Live Monitor",
    page_icon="⚾",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;600&display=swap');

:root {
    --green:  #00d46a;
    --red:    #ff4b4b;
    --yellow: #ffd93d;
    --bg:     #0d0d0d;
    --card:   #161616;
    --border: #2a2a2a;
    --muted:  #555;
    --text:   #e8e8e8;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--text);
}

[data-testid="stHeader"] { background: transparent !important; }

/* 隱藏 Streamlit 預設元素 */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

/* 主標題 */
.mlb-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3rem;
    letter-spacing: 0.12em;
    color: var(--green);
    margin: 0;
    line-height: 1;
}
.mlb-subtitle {
    font-size: 0.72rem;
    color: var(--muted);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-top: 2px;
}

/* 比賽卡片 */
.game-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 18px;
    position: relative;
    overflow: hidden;
}
.game-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--green), transparent);
}

/* 隊伍比分 */
.scoreline {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem;
    letter-spacing: 0.08em;
    color: #fff;
    margin-bottom: 10px;
}
.score-num {
    color: var(--green);
    font-size: 2.4rem;
}

/* 局數標籤 */
.inning-badge {
    display: inline-block;
    background: #1e2e1e;
    color: var(--green);
    border: 1px solid var(--green);
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 0.75rem;
    letter-spacing: 0.15em;
    font-weight: 600;
    margin-bottom: 12px;
}

/* 資訊列 */
.info-row {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    margin-bottom: 10px;
    font-size: 0.78rem;
    color: #aaa;
}
.info-item { display: flex; flex-direction: column; gap: 2px; }
.info-label { color: var(--muted); font-size: 0.65rem; letter-spacing: 0.15em; text-transform: uppercase; }
.info-value { color: var(--text); font-weight: 600; font-size: 0.82rem; }
.info-value.highlight { color: var(--yellow); }

/* 壘包圖示 */
.bases-display {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 1rem;
}

/* 球員區 */
.player-section {
    border-top: 1px solid var(--border);
    margin-top: 12px;
    padding-top: 12px;
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    font-size: 0.78rem;
}
.player-block { display: flex; flex-direction: column; gap: 3px; }
.player-role { color: var(--muted); font-size: 0.62rem; letter-spacing: 0.18em; text-transform: uppercase; }
.player-name { color: #fff; font-weight: 600; }
.player-stat { color: var(--green); font-size: 0.72rem; }

/* 沒有比賽 */
.no-game {
    text-align: center;
    padding: 60px 0;
    color: var(--muted);
    font-size: 1rem;
    letter-spacing: 0.1em;
}

/* 時間戳 */
.timestamp {
    font-size: 0.65rem;
    color: var(--muted);
    letter-spacing: 0.12em;
    margin-top: 4px;
}

/* 出局數點點 */
.out-dots { display: inline-flex; gap: 5px; }
.out-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    border: 1.5px solid var(--muted);
    display: inline-block;
}
.out-dot.active { background: var(--yellow); border-color: var(--yellow); }
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
LIVE_URL     = "https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"
LIVE_DETAILED_STATES = {"In Progress", "Manager Challenge", "Review", "Warmup"}
REFRESH_SECONDS = 15

# ── Helper functions ───────────────────────────────────────────────────────────
def safe_get(d, *keys, default=""):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur

def get_player_stat_avg(player_obj):
    for path in [
        ("seasonStats", "batting", "avg"),
        ("stats", "batting", "avg"),
        ("stats", "batting", "summary"),
    ]:
        v = safe_get(player_obj, *path)
        if v != "":
            return v
    return "-"

def get_player_stat_era(player_obj):
    for path in [
        ("seasonStats", "pitching", "era"),
        ("stats", "pitching", "era"),
        ("stats", "pitching", "summary"),
    ]:
        v = safe_get(player_obj, *path)
        if v != "":
            return v
    return "-"

def get_pitch_count(player_obj):
    for path in [
        ("stats", "pitching", "numberOfPitches"),
        ("stats", "pitching", "pitchesThrown"),
        ("seasonStats", "pitching", "numberOfPitches"),
    ]:
        v = safe_get(player_obj, *path)
        if v != "":
            return v
    return "-"

def format_bases(on_1b, on_2b, on_3b):
    def dot(filled):
        return "🟡" if filled else "⚪"
    return f"{dot(on_3b)} {dot(on_2b)} {dot(on_1b)}"

def out_dots_html(outs):
    dots = ""
    for i in range(3):
        cls = "out-dot active" if i < int(outs) else "out-dot"
        dots += f'<span class="{cls}"></span>'
    return f'<span class="out-dots">{dots}</span>'

def is_live(game):
    if game.get("abstract_state") == "Live":
        return True
    if game.get("status") in LIVE_DETAILED_STATES:
        return True
    return False

# ── API calls ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def fetch_live_games():
    today = datetime.now().date()
    params = {
        "sportId": 1,
        "startDate": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
        "endDate":   (today + timedelta(days=1)).strftime("%Y-%m-%d"),
    }
    r = requests.get(SCHEDULE_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    games, seen = [], set()
    for d in data.get("dates", []):
        for g in d.get("games", []):
            pk = g["gamePk"]
            if pk in seen:
                continue
            seen.add(pk)
            games.append({
                "gamePk":         pk,
                "abstract_state": safe_get(g, "status", "abstractGameState"),
                "status":         safe_get(g, "status", "detailedState"),
            })

    results = []
    for g in games:
        if not is_live(g):
            continue
        try:
            snap = fetch_snapshot(g["gamePk"])
            if snap:
                results.append(snap)
        except Exception:
            continue
    return results

@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def fetch_snapshot(gamePk):
    url = LIVE_URL.format(gamePk=gamePk)
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()

    gd   = data.get("gameData", {})
    ld   = data.get("liveData", {})
    ls   = ld.get("linescore", {})
    plays = ld.get("plays", {})
    bs   = ld.get("boxscore", {})

    offense = ls.get("offense", {})
    on_1b = "first"  in offense
    on_2b = "second" in offense
    on_3b = "third"  in offense

    cp = plays.get("currentPlay", {})
    batter_id  = safe_get(cp, "matchup", "batter",  "id", default=None)
    pitcher_id = safe_get(cp, "matchup", "pitcher", "id", default=None)

    all_players = {}
    all_players.update(safe_get(bs, "teams", "away", "players", default={}) or {})
    all_players.update(safe_get(bs, "teams", "home", "players", default={}) or {})

    batter_avg = pitcher_era = pitcher_pitch_count = "-"
    if batter_id:
        batter_avg = get_player_stat_avg(all_players.get(f"ID{batter_id}", {}))
    if pitcher_id:
        obj = all_players.get(f"ID{pitcher_id}", {})
        pitcher_era         = get_player_stat_era(obj)
        pitcher_pitch_count = get_pitch_count(obj)

    inning_state = ls.get("inningState", "")
    offense_key  = "away" if inning_state == "Top" else ("home" if inning_state == "Bottom" else "")
    next_batters = []
    if offense_key:
        ot = safe_get(bs, "teams", offense_key, default={}) or {}
        order = ot.get("battingOrder", []) or []
        tplayers = ot.get("players", {}) or {}
        cur_idx = None
        if batter_id:
            for idx, pid in enumerate(order):
                if str(pid) == str(batter_id):
                    cur_idx = idx
                    break
        if cur_idx is not None:
            for step in [1, 2]:
                ni = (cur_idx + step) % len(order)
                np_obj = tplayers.get(f"ID{order[ni]}", {})
                nm = safe_get(np_obj, "person", "fullName")
                if nm:
                    next_batters.append({"name": nm, "avg": get_player_stat_avg(np_obj)})

    return {
        "gamePk":       gamePk,
        "away":         safe_get(gd, "teams", "away", "name", default="Away"),
        "home":         safe_get(gd, "teams", "home", "name", default="Home"),
        "away_score":   safe_get(ls, "teams", "away", "runs", default=0),
        "home_score":   safe_get(ls, "teams", "home", "runs", default=0),
        "status":       safe_get(gd, "status", "detailedState"),
        "abstract_state": safe_get(gd, "status", "abstractGameState"),
        "inning":       ls.get("currentInning", "-"),
        "inning_state": inning_state,
        "outs":         ls.get("outs", 0),
        "balls":        safe_get(cp, "count", "balls",   default="?"),
        "strikes":      safe_get(cp, "count", "strikes", default="?"),
        "on_1b": on_1b, "on_2b": on_2b, "on_3b": on_3b,
        "batter_name":         safe_get(cp, "matchup", "batter",  "fullName"),
        "batter_avg":          batter_avg,
        "pitcher_name":        safe_get(cp, "matchup", "pitcher", "fullName"),
        "pitcher_era":         pitcher_era,
        "pitcher_pitch_count": pitcher_pitch_count,
        "next_batters":        next_batters,
    }

# ── Render one game card ───────────────────────────────────────────────────────
def render_game_card(s):
    inning_label = f"{s['inning_state'].upper()} {s['inning']}" if s['inning_state'] else str(s['inning'])
    bases_str    = format_bases(s["on_1b"], s["on_2b"], s["on_3b"])
    outs_html    = out_dots_html(s["outs"])

    n1 = s["next_batters"][0] if len(s["next_batters"]) > 0 else {"name": "—", "avg": "—"}
    n2 = s["next_batters"][1] if len(s["next_batters"]) > 1 else {"name": "—", "avg": "—"}

    st.markdown(f"""
    <div class="game-card">
        <div class="scoreline">
            {s['away']} <span class="score-num">{s['away_score']}</span>
            &nbsp;:&nbsp;
            <span class="score-num">{s['home_score']}</span> {s['home']}
        </div>

        <div class="inning-badge">▶ {inning_label}</div>

        <div class="info-row">
            <div class="info-item">
                <span class="info-label">Count</span>
                <span class="info-value highlight">{s['balls']}B {s['strikes']}S</span>
            </div>
            <div class="info-item">
                <span class="info-label">Outs</span>
                <span class="info-value">{outs_html}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Bases</span>
                <span class="info-value">{bases_str}</span>
            </div>
        </div>

        <div class="player-section">
            <div class="player-block">
                <span class="player-role">⚡ Pitcher</span>
                <span class="player-name">{s['pitcher_name'] or '—'}</span>
                <span class="player-stat">ERA {s['pitcher_era']} &nbsp;|&nbsp; {s['pitcher_pitch_count']} pitches</span>
            </div>
            <div class="player-block">
                <span class="player-role">🏏 Batter</span>
                <span class="player-name">{s['batter_name'] or '—'}</span>
                <span class="player-stat">AVG {s['batter_avg']}</span>
            </div>
            <div class="player-block">
                <span class="player-role">🔜 On Deck</span>
                <span class="player-name">{n1['name']}</span>
                <span class="player-stat">AVG {n1['avg']}</span>
            </div>
            <div class="player-block">
                <span class="player-role">⏭ In the Hole</span>
                <span class="player-name">{n2['name']}</span>
                <span class="player-stat">AVG {n2['avg']}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Main layout ────────────────────────────────────────────────────────────────
st.markdown('<p class="mlb-title">⚾ MLB LIVE MONITOR</p>', unsafe_allow_html=True)
st.markdown(f'<p class="mlb-subtitle">Auto-refresh every {REFRESH_SECONDS}s &nbsp;|&nbsp; Live games only</p>', unsafe_allow_html=True)

now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f'<p class="timestamp">Last updated: {now_str}</p>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Fetch & render ─────────────────────────────────────────────────────────────
with st.spinner("抓取比賽資料中..."):
    try:
        live_games = fetch_live_games()
    except Exception as e:
        st.error(f"API 錯誤：{e}")
        live_games = []

if not live_games:
    st.markdown('<div class="no-game">⚾ &nbsp; 目前沒有進行中的 MLB 比賽</div>', unsafe_allow_html=True)
else:
    for s in live_games:
        render_game_card(s)

# ── Auto-refresh ───────────────────────────────────────────────────────────────
time.sleep(REFRESH_SECONDS)
st.rerun()

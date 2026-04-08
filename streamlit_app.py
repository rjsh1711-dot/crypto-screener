import streamlit as st
import requests
import time
from datetime import datetime
import pytz
IST = pytz.timezone("Asia/Kolkata")
from cryptography.hazmat.primitives.asymmetric import ed25519
from urllib.parse import urlencode
import urllib
import math
import hmac
import hashlib
 
# ══════════════════════════════════════════════════════════════
#  CONFIG — Streamlit Secrets (set in Streamlit Cloud dashboard)
# ══════════════════════════════════════════════════════════════
CS_API_KEY    = st.secrets["CS_API_KEY"]
CS_SECRET_KEY = st.secrets["CS_SECRET_KEY"]
CG_API_KEY    = st.secrets["CG_API_KEY"]
CS_QUOTE      = "INR"
TOP_N         = 7
 
COIN_MAP = {
    "bitcoin":"BTC","ethereum":"ETH","binancecoin":"BNB","solana":"SOL",
    "ripple":"XRP","cardano":"ADA","dogecoin":"DOGE","polkadot":"DOT",
    "avalanche-2":"AVAX","chainlink":"LINK","litecoin":"LTC","polygon":"MATIC",
    "uniswap":"UNI","stellar":"XLM","cosmos":"ATOM","algorand":"ALGO",
    "tron":"TRX","near":"NEAR","injective-protocol":"INJ","sui":"SUI",
    "pepe":"PEPE","shiba-inu":"SHIB","render-token":"RNDR","arbitrum":"ARB",
    "optimism":"OP","aptos":"APT","internet-computer":"ICP","floki":"FLOKI",
    "vechain":"VET","filecoin":"FIL",
}
 
W_CS_MOMENTUM=35; W_CS_SIGNAL=30; W_CS_SPREAD=20; W_CS_VOLUME=15
W_CG_1H=40;      W_CG_24H=30;    W_CG_MCAP=20;   W_CG_VOL24=10
CS_WEIGHT=0.60;  CG_WEIGHT=0.40
 
# ══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Crypto Screener",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)
 
# ── Mobile-optimised CSS ──
st.markdown("""
<style>
    .main { padding: 0.5rem; }
    .block-container { padding: 1rem 0.5rem; max-width: 100%; }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 1rem !important; }
    .stDataFrame { font-size: 12px; }
 
    .score-card {
        background: #0D0D1F;
        border-radius: 12px;
        padding: 12px;
        margin: 6px 0;
        border-left: 4px solid #00E676;
    }
    .score-card-sell {
        background: #0D0D1F;
        border-radius: 12px;
        padding: 12px;
        margin: 6px 0;
        border-left: 4px solid #FF1744;
    }
    .symbol { font-size: 1.1rem; font-weight: bold; color: #FFD700; }
    .score  { font-size: 1.3rem; font-weight: bold; }
    .signal-buy  { color: #00E676; font-weight: bold; }
    .signal-sell { color: #FF1744; font-weight: bold; }
    .signal-weak { color: #FFD740; font-weight: bold; }
    .metric-row { display: flex; justify-content: space-between; margin-top: 6px; font-size: 0.82rem; color: #AAAAAA; }
    .metric-val { color: #FFFFFF; font-weight: 500; }
    .exit-box { background: #1A1A2E; border-radius: 8px; padding: 8px; margin-top: 8px; font-size: 0.8rem; }
    .target { color: #00E676; } .stop { color: #FF1744; }
    .refresh-btn { width: 100%; }
    .header-box {
        background: linear-gradient(135deg, #050518, #0A0A2E);
        border-radius: 12px; padding: 16px; margin-bottom: 16px;
        text-align: center; border: 1px solid #1A1A3E;
    }
    .tab-header {
        background: #0A1A0A; border-radius: 8px;
        padding: 8px 12px; margin-bottom: 12px;
        font-weight: bold; font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════
#  API FUNCTIONS
# ══════════════════════════════════════════════════════════════
def _cs_signature(method, endpoint, params, epoch_time):
    ep = endpoint
    if method == "GET" and params:
        sep = '&' if '?' in ep else '?'
        ep  = ep + sep + urlencode(params)
        ep  = urllib.parse.unquote_plus(ep)
    msg          = method + ep + epoch_time
    secret_bytes = bytes.fromhex(CS_SECRET_KEY)
    private_key  = ed25519.Ed25519PrivateKey.from_private_bytes(secret_bytes)
    return private_key.sign(msg.encode("utf-8")).hex()
 
def cs_get(endpoint, params=None):
    params     = params or {}
    epoch_time = str(int(time.time() * 1000))
    sig        = _cs_signature("GET", endpoint, params, epoch_time)
    url = "https://coinswitch.co" + endpoint
    if params:
        url += ('&' if '?' in url else '?') + urlencode(params)
    headers = {
        "Content-Type":"application/json",
        "X-AUTH-APIKEY": CS_API_KEY,
        "X-AUTH-SIGNATURE": sig,
        "X-AUTH-EPOCH": epoch_time,
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()
 
@st.cache_data(ttl=300)
def fetch_cs_data():
    result = {}
    for exchange in ["coinswitchx", "binance"]:
        try:
            data = cs_get("/trade/api/v2/24hr/all-pairs/ticker", {"exchange": exchange})
            for sym, item in data.get("data", {}).items():
                if sym.upper().endswith(f"/{CS_QUOTE}"):
                    base = sym.upper().replace(f"/{CS_QUOTE}", "")
                    if base not in result:
                        result[base] = item
        except:
            continue
    return result
 
@st.cache_data(ttl=300)
def fetch_cg_data():
    key = CG_API_KEY.strip()
    if key.startswith("CG-"):
        base  = "https://api.coingecko.com/api/v3"
        hdrs  = {"accept":"application/json","x-cg-demo-api-key": key}
    else:
        base  = "https://pro-api.coingecko.com/api/v3"
        hdrs  = {"accept":"application/json","x-cg-pro-api-key": key}
    params = {
        "vs_currency":"inr","ids":",".join(COIN_MAP.keys()),
        "order":"market_cap_desc","per_page":100,
        "sparkline":False,"price_change_percentage":"1h,24h","precision":"full"
    }
    r = requests.get(f"{base}/coins/markets", params=params, headers=hdrs, timeout=20)
    r.raise_for_status()
    return {item["id"]: item for item in r.json()}
 
def _norm(val, vals, invert=False):
    mn, mx = min(vals), max(vals)
    if mx == mn: return 50.0
    s = (val - mn)/(mx - mn)*100
    return 100-s if invert else s
 
def compute_scores(cs_data, cg_data):
    rows = []
    for cg_id, cs_sym in COIN_MAP.items():
        cs = cs_data.get(cs_sym, {})
        cg = cg_data.get(gid := gg if (gg := gid if (gid := cg_id) else cg_id) else cg_id, {})
        cg = cg_data.get(cg_id, {})
        if not cs and not cg: continue
        cs_price   = float(cs.get("lastPrice",       0) or 0)
        cs_high    = float(cs.get("highPrice",        0) or 0)
        cs_low     = float(cs.get("lowPrice",         0) or 0)
        cs_vol     = float(cs.get("baseVolume",       0) or 0)
        cs_mom_pct = float(cs.get("percentageChange", 0) or 0)
        cg_vol24   = cg.get("total_volume") or 0
        cg_mcap    = cg.get("market_cap")   or 1
        cg_1h      = cg.get("price_change_percentage_1h_in_currency") or 0
        cg_24h     = cg.get("price_change_percentage_24h") or 0
        cg_rank    = cg.get("market_cap_rank") or 999
        price      = cs_price or (cg.get("current_price") or 0)
        high       = cs_high  or (cg.get("high_24h") or 0)
        low        = cs_low   or (cg.get("low_24h")  or 0)
        spread_pct = ((high-low)/low*100) if low else 0
        sig_score  = 50 + cs_mom_pct * 5
        sig_score  = max(0, min(100, sig_score))
        if cs_mom_pct >= 5:   cs_sig = "STRONG BUY"
        elif cs_mom_pct >= 2: cs_sig = "BUY"
        elif cs_mom_pct >= 0.5: cs_sig = "WEAK BUY"
        elif cs_mom_pct >= -0.5: cs_sig = "NEUTRAL"
        elif cs_mom_pct >= -2: cs_sig = "WEAK SELL"
        elif cs_mom_pct >= -5: cs_sig = "SELL"
        else: cs_sig = "STRONG SELL"
        rows.append({
            "symbol":cs_sym,"name":cg.get("name",cs_sym),"price":price,
            "high":high,"low":low,"volume":cs_vol,"vol_24h":cg_vol24,
            "market_cap":cg_mcap,"cg_1h":cg_1h,"cg_24h":cg_24h,
            "cs_mom_pct":cs_mom_pct,"cs_signal":cs_sig,"cs_strength":int(sig_score),
            "cg_rank":cg_rank,"spread_pct":spread_pct,
            "_cs_vol":cs_vol,"_cg_vol24":cg_vol24,"_cg_mcap":cg_mcap,
        })
    if not rows: return []
    cs_moms  = [r["cs_mom_pct"]  for r in rows]
    cs_sigs  = [r["cs_strength"] for r in rows]
    cs_sprds = [r["spread_pct"]  for r in rows]
    cs_vols  = [r["_cs_vol"]     for r in rows]
    cg_1hs   = [r["cg_1h"]      for r in rows]
    cg_24hs  = [r["cg_24h"]     for r in rows]
    cg_mcaps = [math.log(max(r["_cg_mcap"],1)) for r in rows]
    cg_vols  = [r["_cg_vol24"]   for r in rows]
    for i,r in enumerate(rows):
        cs_score = (_norm(cs_moms[i],cs_moms)*W_CS_MOMENTUM/100 +
                    _norm(cs_sigs[i],cs_sigs)*W_CS_SIGNAL/100 +
                    _norm(cs_sprds[i],cs_sprds,True)*W_CS_SPREAD/100 +
                    _norm(cs_vols[i],cs_vols)*W_CS_VOLUME/100)
        cg_score = (_norm(cg_1hs[i],cg_1hs)*W_CG_1H/100 +
                    _norm(cg_24hs[i],cg_24hs)*W_CG_24H/100 +
                    _norm(cg_mcaps[i],cg_mcaps)*W_CG_MCAP/100 +
                    _norm(cg_vols[i],cg_vols)*W_CG_VOL24/100)
        claude = round(cs_score*CS_WEIGHT + cg_score*CG_WEIGHT, 1)
        if claude>=75:   signal,strength="STRONG BUY","⬆⬆⬆ VERY HIGH"
        elif claude>=62: signal,strength="BUY","⬆⬆ HIGH"
        elif claude>=50: signal,strength="WEAK BUY","⬆ MODERATE"
        elif claude>=38: signal,strength="WEAK SELL","⬇ MODERATE"
        elif claude>=25: signal,strength="SELL","⬇⬇ HIGH"
        else:            signal,strength="STRONG SELL","⬇⬇⬇ VERY HIGH"
        if claude>=75:   tgt_pct,stp_pct,exit_type=4.0,1.5,"TRAIL STOP"
        elif claude>=62: tgt_pct,stp_pct,exit_type=3.0,1.2,"BOOK @ TARGET"
        elif claude>=50: tgt_pct,stp_pct,exit_type=2.0,1.0,"QUICK BOOK"
        elif claude>=38: tgt_pct,stp_pct,exit_type=1.5,0.8,"EXIT NOW"
        elif claude>=25: tgt_pct,stp_pct,exit_type=1.0,0.6,"CUT LOSS"
        else:            tgt_pct,stp_pct,exit_type=0.5,0.5,"URGENT EXIT"
        price = r["price"]
        r.update({
            "cs_subscore":round(cs_score,1),"cg_subscore":round(cg_score,1),
            "claude_score":claude,"signal":signal,"strength":strength,
            "exit_type":exit_type,
            "target_price":price*(1+tgt_pct/100),"stop_price":price*(1-stp_pct/100),
            "tgt_pct":tgt_pct,"stp_pct":stp_pct,
        })
    return sorted(rows, key=lambda x: x["claude_score"], reverse=True)
 
# ══════════════════════════════════════════════════════════════
#  FORMATTING
# ══════════════════════════════════════════════════════════════
def fmt_price(v):
    if not v: return "–"
    if v >= 1e5:    return f"₹{v/1e5:,.2f}L"
    if v >= 1000:   return f"₹{v:,.2f}"
    if v >= 1:      return f"₹{v:.4f}"
    if v >= 0.0001: return f"₹{v:.6f}"
    return f"₹{v:.8f}"
 
def fmt_pct(v):
    if v is None: return "–"
    return f"{'+'if v>0 else ''}{v:.2f}%"
 
def pct_color(v):
    if v is None: return "#AAAAAA"
    return "#00E676" if v > 0 else ("#FF1744" if v < 0 else "#AAAAAA")
 
def signal_emoji(sig):
    return {"STRONG BUY":"🟢🟢","BUY":"🟢","WEAK BUY":"🟡",
            "WEAK SELL":"🟠","SELL":"🔴","STRONG SELL":"🔴🔴"}.get(sig,"⚪")
 
def score_color(s):
    if s>=75: return "#00E676"
    if s>=62: return "#69F0AE"
    if s>=50: return "#FFD740"
    if s>=38: return "#FFAB40"
    if s>=25: return "#FF6D00"
    return "#FF1744"
 
def render_card(r, is_buy=True, rank=1):
    card_class = "score-card" if is_buy else "score-card-sell"
    border_color = "#00E676" if is_buy else "#FF1744"
    sc = score_color(r["claude_score"])
    pc1h = pct_color(r["cg_1h"])
    pc24h = pct_color(r["cg_24h"])
    pcmom = pct_color(r["cs_mom_pct"])
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣"]
    medal = medals[rank-1] if rank <= 7 else str(rank)
 
    st.markdown(f"""
    <div class="{card_class}" style="border-left-color:{border_color}">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
                <span class="symbol">{medal} {r['symbol']}</span>
                <span style="color:#AAAAAA;font-size:0.8rem;margin-left:8px">{r['name']}</span>
            </div>
            <div style="text-align:right">
                <div class="score" style="color:{sc}">{r['claude_score']}/100</div>
                <div style="font-size:0.75rem;color:#AAAAAA">Claude Score</div>
            </div>
        </div>
        <div class="metric-row">
            <span>💰 Price</span><span class="metric-val">{fmt_price(r['price'])}</span>
            <span>📊 Signal</span><span style="color:{sc};font-weight:bold">{signal_emoji(r['signal'])} {r['signal']}</span>
        </div>
        <div class="metric-row">
            <span>1H</span><span style="color:{pc1h}">{fmt_pct(r['cg_1h'])}</span>
            <span>24H</span><span style="color:{pc24h}">{fmt_pct(r['cg_24h'])}</span>
            <span>Mom%</span><span style="color:{pcmom}">{fmt_pct(r['cs_mom_pct'])}</span>
        </div>
        <div class="metric-row">
            <span>CS Score</span><span class="metric-val">{r['cs_subscore']}/100</span>
            <span>CG Score</span><span class="metric-val">{r['cg_subscore']}/100</span>
            <span>Rank</span><span class="metric-val">#{r['cg_rank']}</span>
        </div>
        <div class="exit-box">
            <span style="color:#FFD700;font-weight:bold">{r['exit_type']}</span>
            &nbsp;|&nbsp;
            <span class="target">🎯 {fmt_price(r['target_price'])} (+{r['tgt_pct']}%)</span>
            &nbsp;|&nbsp;
            <span class="stop">🛑 {fmt_price(r['stop_price'])} (-{r['stp_pct']}%)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════
def main():
    # Header
    now = datetime.now(IST).strftime("%d %b %Y  %H:%M IST")
    st.markdown(f"""
    <div class="header-box">
        <h1 style="color:#FFD700;margin:0">🚀 Crypto Screener</h1>
        <p style="color:#00BCD4;margin:4px 0 0 0;font-size:0.85rem">
            CoinSwitch PRO + CoinGecko · INR · {now}
        </p>
        <p style="color:#888;margin:2px 0 0 0;font-size:0.75rem">
            CS 60% [Mom 35%·Sig 30%·Sprd 20%·Vol 15%] + CG 40% [1H 40%·24H 30%·MCap 20%·Vol 10%]
        </p>
    </div>
    """, unsafe_allow_html=True)
 
    # Refresh button
    col1, col2 = st.columns([3,1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
 
    # Fetch data
    with st.spinner("📡 Fetching live data..."):
        try:
            cs_data = fetch_cs_data()
            cg_data = fetch_cg_data()
            scored  = compute_scores(cs_data, cg_data)
        except Exception as e:
            st.error(f"❌ Error fetching data: {e}")
            return
 
    if not scored:
        st.error("No data available.")
        return
 
    buys  = [r for r in scored if r["claude_score"] >= 50][:TOP_N]
    sells = [r for r in reversed(scored) if r["claude_score"] < 50][:TOP_N]
 
    # Stats bar
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📊 Coins", len(scored))
    c2.metric("🟢 Buys",  len([r for r in scored if r["claude_score"]>=50]))
    c3.metric("🔴 Sells", len([r for r in scored if r["claude_score"]<50]))
    c4.metric("🥇 Top",   scored[0]["symbol"] if scored else "–")
 
    st.markdown("---")
 
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🟢 BUY Signals", "🔴 SELL Signals", "📋 All Coins"])
 
    with tab1:
        st.markdown(f'<div class="tab-header" style="background:#002200;color:#00E676">🟢 TOP {len(buys)} BUY SIGNALS</div>', unsafe_allow_html=True)
        for i, r in enumerate(buys):
            render_card(r, is_buy=True, rank=i+1)
 
    with tab2:
        st.markdown(f'<div class="tab-header" style="background:#220000;color:#FF1744">🔴 TOP {len(sells)} SELL SIGNALS</div>', unsafe_allow_html=True)
        for i, r in enumerate(sells):
            render_card(r, is_buy=False, rank=i+1)
 
    with tab3:
        st.markdown('<div class="tab-header" style="background:#0A0A2A;color:#00BCD4">📋 ALL COINS — Sorted by Claude Score</div>', unsafe_allow_html=True)
        for i, r in enumerate(scored):
            is_buy = r["claude_score"] >= 50
            render_card(r, is_buy=is_buy, rank=i+1)
 
    st.markdown(f"""
    <p style="text-align:center;color:#444;font-size:0.7rem;margin-top:20px">
        Auto-refreshes every 5 min · Data: CoinSwitch PRO + CoinGecko · Last: {now}
    </p>
    """, unsafe_allow_html=True)
 
if __name__ == "__main__":
    main()

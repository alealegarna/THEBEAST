import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

# 1. KONFIGURASI HALAMAN & STYLE BLOOMBERG TERMINAL
st.set_page_config(page_title="IDX QUANT TERMINAL // INSTITUTIONAL V2", layout="wide", initial_sidebar_state="collapsed")

bloomberg_style = """
<style>
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3 { color: #FF9900 !important; font-family: 'Courier New', Courier, monospace; font-weight: bold; }
    div[data-testid="stTable"] { border: 1px solid #FF9900; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #111111; color: #FF9900; border-bottom: 2px solid #FF9900; padding: 8px; text-align: left; font-size: 13px; }
    td { border-bottom: 1px solid #222222; padding: 8px; font-size: 12px; color: #CCCCCC; }
    .metric-card { background-color: #0a0a0a; border: 1px solid #FF9900; padding: 12px; text-align: center; }
    .metric-title { color: #FF9900; font-size: 11px; letter-spacing: 1px; }
    .metric-value { font-size: 22px; font-weight: bold; margin-top: 5px; }
    .green-text { color: #00FF00; font-weight: bold; }
    .red-text { color: #FF0000; font-weight: bold; }
    .amber-text { color: #FF9900; font-weight: bold; }
    .status-box { padding: 10px; border: 1px solid #FF9900; background-color: #1a0f00; color: #FF9900; text-align: center; font-weight: bold; margin-bottom: 15px; }
</style>
"""
st.markdown(bloomberg_style, unsafe_allow_html=True)

# 2. WEB SCRAPER SAHAM
@st.cache_data(ttl=86400)
def ambil_daftar_saham(mode):
    if mode == "🔥 LQ45 (45 Saham Paling Likuid & Aktif)":
        return [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "UNTR.JK", "PGAS.JK", "GOTO.JK", 
            "BRIS.JK", "ANTM.JK", "ICBP.JK", "KLBF.JK", "PTBA.JK", "AMRT.JK", "CPIN.JK", "EXCL.JK", "INDF.JK", "INKP.JK", 
            "INCO.JK", "ITMG.JK", "MEDC.JK", "MDKA.JK", "PGEO.JK", "PTMP.JK", "SIDO.JK", "SMGR.JK", "UNVR.JK", "AKRA.JK", 
            "AMMN.JK", "ARTO.JK", "BRPT.JK", "BUKA.JK", "EMTK.JK", "ESSA.JK", "HRUM.JK", "INTP.JK", "MBMA.JK", "MTEL.JK", 
            "PTPP.JK", "SCMA.JK", "TOWR.JK", "WIKA.JK"
        ]
    elif mode == "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)":
        try:
            url = "https://id.wikipedia.org/wiki/Daftar_emiten_di_Bursa_Efek_Indonesia"
            tables = pd.read_html(url)
            tickers = []
            for df in tables:
                for col in df.columns:
                    if str(col).strip().lower() in ['kode', 'kode saham', 'ticker', 'emiten']:
                        t_list = df[col].dropna().astype(str).tolist()
                        for t in t_list:
                            clean_t = t.strip().upper()
                            if len(clean_t) == 4 and clean_t.isalpha():
                                tickers.append(clean_t + ".JK")
            if tickers:
                return sorted(list(set(tickers)))
        except Exception:
            pass
    return ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "ADRO.JK", "GOTO.JK", "BRIS.JK", "ANTM.JK"]

# 3. ADVANCED QUANTITATIVE INDICATORS
def hitung_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hitung_mfi(data, window=14):
    typical_price = (data['High'] + data['Low'] + data['Close']) / 3
    money_flow = typical_price * data['Volume']
    pos_flow = np.where(typical_price > typical_price.shift(1), money_flow, 0)
    neg_flow = np.where(typical_price < typical_price.shift(1), money_flow, 0)
    pos_sum = pd.Series(pos_flow).rolling(window=window).sum()
    neg_sum = pd.Series(neg_flow).rolling(window=window).sum()
    return 100 - (100 / (1 + (pos_sum / neg_sum)))

def hitung_atr(data, window=14):
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift())
    low_close = np.abs(data['Low'] - data['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(window=window).mean()

def hitung_obv(data):
    obv = (np.sign(data['Close'].diff()) * data['Volume']).fillna(0).cumsum()
    return obv

# 4. CORE ENGINE WITH KELLY CRITERION & ATR RISK MANAGEMENT
def analisa_pasar_masal(tickers, modal_total, progress_bar, status_text):
    hasil = []
    total_saham = len(tickers)
    tgl_data_terakhir = "N/A"
    
    for i, ticker in enumerate(tickers):
        progress_pct = int(((i + 1) / total_saham) * 100)
        progress_bar.progress(progress_pct)
        status_text.markdown(f"**> QUANT RADAR [{i+1}/{total_saham}]:** Analyzing `{ticker}`... *(Checking OBV Divergence & Kelly Sizing)*")
        
        try:
            saham = yf.Ticker(ticker)
            df = saham.history(period="6mo")
            
            # Anti-Phantom Bar
            df = df.dropna(subset=['Close', 'Volume'])
            df = df[df['Volume'] > 0] 
            
            if df.empty or len(df) < 50 or df['Close'].iloc[-1] <= 50:
                continue

            if tgl_data_terakhir == "N/A":
                tgl_data_terakhir = str(df.index[-1].date())

            info = saham.info
            close = df['Close'].iloc[-1]
            vol_last = df['Volume'].iloc[-1]
            vol_avg = df['Volume'].tail(20).mean()

            # Kalkulasi Indikator Lanjutan
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['RSI'] = hitung_rsi(df)
            df['MFI'] = hitung_mfi(df)
            df['ATR'] = hitung_atr(df)
            df['OBV'] = hitung_obv(df)
            
            atr_last = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (close * 0.03)
            rsi_last = df['RSI'].iloc[-1]
            mfi_last = df['MFI'].iloc[-1] if not pd.isna(df['MFI'].iloc[-1]) else 50
            
            # --- A. VALUE INVESTING (25 Poin) ---
            pe = info.get('trailingPE', 0) or 0
            pb = info.get('priceToBook', 0) or 0
            roe = (info.get('returnOnEquity', 0) or 0) * 100
            val_score = (10 if 0 < pe < 15 else 0) + (8 if 0 < pb < 2.0 else 0) + (7 if roe > 15 else 0)

            # --- B. ADVANCED BANDARMOLOGI: OBV & VOLUME ANOMALY (25 Poin) ---
            bandar_score = 0
            if vol_last > (vol_avg * 1.5) and close > df['Open'].iloc[-1]:
                bandar_score += 15
            # OBV Bullish Divergence (OBV Naik saat EMA turun/datar = Akumulasi Diam-diam)
            if df['OBV'].iloc[-1] > df['OBV'].tail(10).mean() and close >= df['Close'].tail(10).mean():
                bandar_score += 10

            # --- C. SWING & MONEY FLOW (35 Poin) ---
            swing_score = 0
            if close > df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]: swing_score += 15
            if 40 <= rsi_last <= 60: swing_score += 10
            if mfi_last > 50: swing_score += 10

            # --- D. CORPORATE ACTION PROXY (15 Poin) ---
            div_yield = (info.get('dividendYield', 0) or 0) * 100
            corp_score = 15 if div_yield > 5.0 else (10 if div_yield > 2.0 else 0)

            # --- TOTAL PROBABILITAS ---
            total_prob = val_score + bandar_score + swing_score + corp_score
            prob_desimal = total_prob / 100.0

            # --- DYNAMIC ATR RISK / REWARD ---
            # Target (Reward) = 2.5x ATR dari harga sekarang (Dynamic Resistance)
            target_price = close + (atr_last * 2.5)
            # Stop Loss (Risk) = 1.5x ATR di bawah harga sekarang (Dynamic Volatility Stop)
            stop_price = close - (atr_last * 1.5)
            
            peluang_naik_pct = ((target_price - close) / close) * 100
            risiko_turun_pct = ((close - stop_price) / close) * 100
            rr_ratio = peluang_naik_pct / risiko_turun_pct if risiko_turun_pct > 0 else 0

            # --- KELLY CRITERION POSITION SIZING (MANAJEMEN MODAL) ---
            # Rumus Kelly: W - ((1 - W) / R), di mana W = Probabilitas Menang, R = R:R Ratio
            if rr_ratio > 0:
                kelly_pct = prob_desimal - ((1.0 - prob_desimal) / rr_ratio)
            else:
                kelly_pct = 0
            
            # Kita gunakan "Half-Kelly" dan batasi maksimal 20% modal per saham demi keamanan (Institutional Rule)
            alokasi_pct = max(min(kelly_pct * 0.5 * 100, 20.0), 0.0)
            alokasi_rp = (alokasi_pct / 100.0) * modal_total

            # --- SINYAL ---
            if total_prob >= 70 and rr_ratio >= 1.5 and alokasi_pct > 5:
                sinyal = "STRONG BUY 🟢"
            elif total_prob >= 55:
                sinyal = "BUY / HOLD 🟡"
            else:
                sinyal = "WAIT / SELL 🔴"

            hasil.append({
                "Ticker": ticker.replace(".JK", ""),
                "Harga": f"Rp {int(close):,}",
                "Probabilitas": total_prob,
                "Sinyal": sinyal,
                "Beli Max (Rp)": f"Rp {int(alokasi_rp):,}" if alokasi_rp > 0 else "Rp 0",
                "Bobot (%)": f"{alokasi_pct:.1f}%",
                "Target (+)": f"Rp {int(target_price):,} (+{peluang_naik_pct:.1f}%)",
                "Stop Loss (-)": f"Rp {int(stop_price):,} (-{risiko_turun_pct:.1f}%)",
                "R:R Ratio": f"{rr_ratio:.2f}x",
                "PER": f"{pe:.1f}x" if pe > 0 else "N/A",
                "MFI (Flow)": f"{mfi_last:.1f}"
            })
            time.sleep(0.05)
            
        except Exception:
            continue
            
    return pd.DataFrame(hasil), tgl_data_terakhir

# 5. ANTARMUKA TERMINAL
st.markdown("<h1>> IDX QUANTITATIVE TERMINAL // INSTITUTIONAL GRADE V2.0</h1>", unsafe_allow_html=True)
st.markdown("<div class='status-box'>⚡ ENGINE V2 ACTIVE: Powered by On-Balance Volume (OBV) Accumulation, Dynamic ATR Stop-Loss, and Kelly Criterion Position Sizing.</div>", unsafe_allow_html=True)
st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    mode_pilihan = st.selectbox(
        "PILIH RUANG LINGKUP PEMANTAUAN PASAR:",
        [
            "🔥 LQ45 (45 Saham Paling Likuid & Aktif)",
            "🌌 SEMUA EMITEN BEI (~900+ Saham - Sapu Jagat)",
            "✍️ Input Manual Kustom"
        ]
    )
with col2:
    modal_input = st.number_input("TOTAL MODAL PORTFOLIO (Rp):", min_value=1000000, value=100000000, step=5000000, format="%d")
with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🚀 JALANKAN QUANT RADAR", use_container_width=True)

if mode_pilihan == "✍️ Input Manual Kustom":
    input_tickers = st.text_input("Ketik kode saham (pisahkan dengan koma):", "BBCA.JK, BBRI.JK, BMRI.JK, BBNI.JK")
    tickers_to_run = [t.strip().upper() + (".JK" if not t.strip().endswith(".JK") else "") for t in input_tickers.split(",") if t.strip()]
else:
    tickers_to_run = ambil_daftar_saham(mode_pilihan)

if run_btn:
    st.markdown("---")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    df_result, tgl_terakhir = analisa_pasar_masal(tickers_to_run, modal_input, progress_bar, status_text)
    
    progress_bar.empty()
    status_text.markdown(f"### ✅ ANALISA KUANTITATIF SELESAI! (Data EOD: **{tgl_terakhir}**)")
    
    if not df_result.empty:
        df_result = df_result.sort_values(by="Probabilitas", ascending=False)
        top_pick = df_result.iloc[0]
        
        st.markdown("### > TOP RECOMMENDED INSTITUTIONAL PICK")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-title">TOP TICKER</div><div class="metric-value amber-text">{top_pick["Ticker"]}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-title">PROBABILITAS NAIK</div><div class="metric-value green-text">{top_pick["Probabilitas"]}%</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-title">REKOMENDASI BELI</div><div class="metric-value green-text">{top_pick["Beli Max (Rp)"]}</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-title">BATAS STOP LOSS</div><div class="metric-value red-text">{top_pick["Stop Loss (-)"]}</div></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Fitur Download Trading Plan CSV
        csv_data = df_result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 DOWNLOAD TRADING PLAN (EXCEL / CSV)",
            data=csv_data,
            file_name=f"Trading_Plan_BEI_{tgl_terakhir}.csv",
            mime="text/csv",
        )
        
        st.markdown(f"### > INSTITUTIONAL TRADING PLAN TABLE ({len(df_result)} Saham)")
        
        def color_prob(val):
            color = '#00FF00' if val >= 70 else ('#FF9900' if val >= 55 else '#FF0000')
            return f'color: {color}; font-weight: bold;'
            
        styled_df = df_result.style.map(color_prob, subset=['Probabilitas'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
    else:
        st.error("❌ Tidak ada saham yang lolos filter.")

st.markdown("---")
st.markdown("<div style='font-size: 11px; color: #666;'>SYSTEM DISCLAIMER: Alokasi modal dihitung menggunakan rumus Half-Kelly Criterion yang disesuaikan dengan ATR volatilitas. Sistem membatasi risiko maksimal 20% per emiten. Tetap gunakan pertimbangan pribadi.</div>", unsafe_allow_html=True)

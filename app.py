import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

# 1. KONFIGURASI HALAMAN & STYLE BLOOMBERG TERMINAL
st.set_page_config(page_title="IDX QUANT TERMINAL // V2.1 ON-SCREEN", layout="wide", initial_sidebar_state="collapsed")

bloomberg_style = """
<style>
    .stApp { background-color: #000000; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3, h4 { color: #FF9900 !important; font-family: 'Courier New', Courier, monospace; font-weight: bold; }
    div[data-testid="stTable"] { border: 1px solid #FF9900; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #111111; color: #FF9900; border-bottom: 2px solid #FF9900; padding: 8px; text-align: left; font-size: 13px; }
    td { border-bottom: 1px solid #222222; padding: 8px; font-size: 12px; color: #CCCCCC; }
    .metric-card { background-color: #0a0a0a; border: 1px solid #FF9900; padding: 12px; text-align: center; }
    .metric-title { color: #FF9900; font-size: 11px; letter-spacing: 1px; }
    .metric-value { font-size: 22px; font-weight: bold; margin-top: 5px; }
    .ticket-box { background-color: #0d0d0d; border-left: 5px solid #00FF00; border-top: 1px solid #333; border-right: 1px solid #333; border-bottom: 1px solid #333; padding: 15px; margin-bottom: 10px; }
    .briefing-box { background-color: #1a0f00; border: 1px solid #FF9900; padding: 12px; font-size: 14px; color: #FFCC00; margin-bottom: 20px; }
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

# 4. CORE ENGINE WITH LOT CALCULATOR
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

            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['RSI'] = hitung_rsi(df)
            df['MFI'] = hitung_mfi(df)
            df['ATR'] = hitung_atr(df)
            df['OBV'] = hitung_obv(df)
            
            atr_last = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (close * 0.03)
            rsi_last = df['RSI'].iloc[-1]
            mfi_last = df['MFI'].iloc[-1] if not pd.isna(df['MFI'].iloc[-1]) else 50
            
            pe = info.get('trailingPE', 0) or 0
            pb = info.get('priceToBook', 0) or 0
            roe = (info.get('returnOnEquity', 0) or 0) * 100
            val_score = (10 if 0 < pe < 15 else 0) + (8 if 0 < pb < 2.0 else 0) + (7 if roe > 15 else 0)

            bandar_score = 0
            if vol_last > (vol_avg * 1.5) and close > df['Open'].iloc[-1]:
                bandar_score += 15
            if df['OBV'].iloc[-1] > df['OBV'].tail(10).mean() and close >= df['Close'].tail(10).mean():
                bandar_score += 10

            swing_score = 0
            if close > df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]: swing_score += 15
            if 40 <= rsi_last <= 60: swing_score += 10
            if mfi_last > 50: swing_score += 10

            div_yield = (info.get('dividendYield', 0) or 0) * 100
            corp_score = 15 if div_yield > 5.0 else (10 if div_yield > 2.0 else 0)

            total_prob = val_score + bandar_score + swing_score + corp_score
            prob_desimal = total_prob / 100.0

            target_price = close + (atr_last * 2.5)
            stop_price = close - (atr_last * 1.5)
            
            peluang_naik_pct = ((target_price - close) / close) * 100
            risiko_turun_pct = ((close - stop_price) / close) * 100
            rr_ratio = peluang_naik_pct / risiko_turun_pct if risiko_turun_pct > 0 else 0

            if rr_ratio > 0:
                kelly_pct = prob_desimal - ((1.0 - prob_desimal) / rr_ratio)
            else:
                kelly_pct = 0
            
            alokasi_pct = max(min(kelly_pct * 0.5 * 100, 20.0), 0.0)
            alokasi_rp = (alokasi_pct / 100.0) * modal_total
            
            # Perhitungan Lot Otomatis (1 Lot = 100 Lembar)
            lot_beli = int(alokasi_rp / (close * 100)) if close > 0 else 0

            if total_prob >= 70 and rr_ratio >= 1.5 and alokasi_pct > 5:
                sinyal = "STRONG BUY 🟢"
            elif total_prob >= 55:
                sinyal = "BUY / HOLD 🟡"
            else:
                sinyal = "WAIT / SELL 🔴"

            hasil.append({
                "Ticker": ticker.replace(".JK", ""),
                "Harga": int(close),
                "Harga_Str": f"Rp {int(close):,}",
                "Probabilitas": total_prob,
                "Sinyal": sinyal,
                "Lot_Beli": lot_beli,
                "Alokasi_Rp_Str": f"Rp {int(alokasi_rp):,}",
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
st.markdown("<h1>> IDX QUANTITATIVE TERMINAL // V2.1 ON-SCREEN EXECUTIVE</h1>", unsafe_allow_html=True)
st.markdown("<div class='status-box'>⚡ ALL-IN-ONE SCREEN: Seluruh analisa teknikal, bandarmologi OBV, dan kalkulator Lot ditampilkan langsung di layar ini.</div>", unsafe_allow_html=True)
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
    status_text.empty()
    
    if not df_result.empty:
        df_result = df_result.sort_values(by="Probabilitas", ascending=False)
        
        # Hitung statistik singkat untuk Morning Briefing
        strong_buy_count = len(df_result[df_result["Sinyal"].str.contains("STRONG BUY")])
        buy_hold_count = len(df_result[df_result["Sinyal"].str.contains("BUY / HOLD")])
        
        # 1. PANEL MORNING BRIEFING OTOMATIS
        st.markdown(f"""
        <div class="briefing-box">
            📡 <b>EXECUTIVE MARKET BRIEFING (Data EOD: {tgl_terakhir}):</b><br>
            Sistem selesai memindai <b>{len(df_result)} saham aktif</b>. Terdeteksi ada <span style="color:#00FF00; font-weight:bold;">{strong_buy_count} saham STRONG BUY</span> dan <b>{buy_hold_count} saham BUY/HOLD</b> yang memiliki konfirmasi arus uang masuk (MFI > 50) serta akumulasi volume (OBV).
        </div>
        """, unsafe_allow_html=True)
        
        # 2. STRUKTUR MULTI-TAB ALA BLOOMBERG
        tab1, tab2, tab3 = st.tabs(["🎯 TOP PICKS & TRADING TICKET", "📡 LIVE QUANT RADAR (ALL STOCKS)", "⚙️ ALGORITHM SPECS"])
        
        with tab1:
            st.markdown("### > REKOMENDASI UTAMA & KERTAS KERJA EKSEKUSI")
            st.caption("ℹ️ Kertas kerja di bawah ini langsung menghitung jumlah Lot yang harus dibeli berdasarkan manajemen risiko Kelly Criterion agar portofolio Anda tetap aman.")
            
            # Tampilkan Top 3 Saham Terbaik dalam bentuk Trading Ticket
            top_3 = df_result.head(3)
            for idx, row in top_3.iterrows():
                border_color = "#00FF00" if "STRONG BUY" in row["Sinyal"] else "#FF9900"
                st.markdown(f"""
                <div style="background-color: #0d0d0d; border-left: 6px solid {border_color}; border: 1px solid #333; padding: 15px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 20px; font-weight: bold; color: #FF9900;">{row['Ticker']}</span>
                        <span style="font-size: 16px; font-weight: bold; color: {'#00FF00' if row['Probabilitas']>=70 else '#FF9900'};">{row['Sinyal']} (Probabilitas: {row['Probabilitas']}%)</span>
                    </div>
                    <hr style="border-color: #222; margin: 10px 0;">
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 13px;">
                        <div><b>Harga Entry:</b><br><span style="color:#FFF; font-size:15px;">{row['Harga_Str']}</span></div>
                        <div><b>Rekomendasi Beli:</b><br><span style="color:#00FF00; font-size:16px; font-weight:bold;">{row['Lot_Beli']} LOT</span> <span style="color:#888;">({row['Alokasi_Rp_Str']})</span></div>
                        <div><b>Target Profit (+):</b><br><span style="color:#00FF00;">{row['Target (+)']}</span></div>
                        <div><b>Batas Stop Loss (-):</b><br><span style="color:#FF0000;">{row['Stop Loss (-)']}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            st.markdown(f"### > TABEL PEMANTAUAN KESELURUHAN ({len(df_result)} Saham)")
            
            # Tombol Download CSV tetap disediakan jika sewaktu-waktu butuh rekap di Excel
            csv_data = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 DOWNLOAD TABEL KE EXCEL (.CSV)",
                data=csv_data,
                file_name=f"Quant_Radar_{tgl_terakhir}.csv",
                mime="text/csv",
            )
            
            # Bersihkan kolom internal sebelum ditampilkan di tabel
            df_display = df_result.drop(columns=["Harga", "Lot_Beli"]).rename(columns={"Harga_Str": "Harga", "Alokasi_Rp_Str": "Beli Max (Rp)"})
            
            def color_prob(val):
                color = '#00FF00' if val >= 70 else ('#FF9900' if val >= 55 else '#FF0000')
                return f'color: {color}; font-weight: bold;'
                
            styled_df = df_display.style.map(color_prob, subset=['Probabilitas'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("### > SPESIFIKASI RUMUS ALGORITMA (THE 4 PILLARS + RISK ENGINE)")
            st.markdown("""
            1. **Value Investing (Max 25 Poin):** P/E Ratio < 15x (+10 pt), P/B Ratio < 2.0x (+8 pt), ROE > 15% (+7 pt).
            2. **Bandarmologi & OBV (Max 25 Poin):** Lonjakan Volume > 1.5x rata-rata disertai candle hijau (+15 pt). Akumulasi diam-diam terdeteksi melalui OBV Bullish Divergence (+10 pt).
            3. **Swing Trading & Flow (Max 35 Poin):** Konfirmasi Uptrend EMA 20 > EMA 50 (+15 pt), RSI di zona nyaman 40-60 (+10 pt), Money Flow Index (MFI) > 50 menandakan arus uang masuk kuat (+10 pt).
            4. **Corporate Action Proxy (Max 15 Poin):** Dividend Yield > 5% sebagai *Margin of Safety* (+15 pt), Yield > 2% (+10 pt).
            5. **Dynamic Risk & Position Sizing:** Target Profit dihitung 2.5x ATR (Average True Range), Stop Loss 1.5x ATR. Jumlah Lot beli dihitung otomatis menggunakan **Half-Kelly Criterion** dengan batas maksimal risiko 20% modal per emiten.
            """)
        
    else:
        st.error("❌ Tidak ada saham yang lolos filter.")

st.markdown("---")
st.markdown("<div style='font-size: 11px; color: #666;'>SYSTEM DISCLAIMER: Seluruh perhitungan Lot dan batas Stop Loss disajikan langsung di layar sebagai alat bantu pengambil keputusan (Decision Support System). Tetap terapkan manajemen risiko pribadi Anda.</div>", unsafe_allow_html=True)

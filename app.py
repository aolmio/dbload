import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import tempfile

# --- PWA & THEME CONFIG ---
st.set_page_config(page_title="Gold Inventory Pro", layout="wide", initial_sidebar_state="expanded")

# Injecting Meta Tags for PWA (Mobile Home Screen support)
st.markdown("""
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .main { background-color: transparent; }
    @media (max-width: 600px) {
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
        .stDataFrame { font-size: 12px; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- THEME TOGGLE LOGIC ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'

with st.sidebar:
    st.title("Settings")
    theme_choice = st.radio("Appearance", ["Light", "Dark"], index=1 if st.session_state.theme == "Dark" else 0)
    st.session_state.theme = theme_choice

# Apply Theme colors to UI and Charts
if st.session_state.theme == "Dark":
    chart_template = "plotly_dark"
    bg_css = "#0E1117"
    txt_css = "#FAFAFA"
else:
    chart_template = "plotly_white"
    bg_css = "#FFFFFF"
    txt_css = "#31333F"

st.markdown(f"<style>.stApp {{ background-color: {bg_css}; color: {txt_css}; }}</style>", unsafe_allow_html=True)

# --- HELPER FUNCTIONS (EXACT FROM ORIGINAL) ---
def format_burmese_weight(k, p, y):
    """Combines K/P/Y into a single readable Burmese string."""
    parts = []
    if k > 0: parts.append(f"{int(k)} ကျပ်")
    if p > 0: parts.append(f"{int(p)} ပဲ")
    if y > 0: parts.append(f"{y} ရွေး")
    return " ".join(parts) if parts else "0"

def get_normalized_totals(df_subset):
    """Calculates normalized K/P/Y for the dashboard."""
    tk = df_subset['Net_Kyat'].sum()
    tp = df_subset['Net_Pe'].sum()
    ty = df_subset['Net_Yway'].sum()
    
    extra_p = ty // 8
    final_y = round(ty % 8, 2)
    tp += extra_p
    extra_k = tp // 16
    final_p = round(tp % 16, 2)
    final_k = tk + extra_k
    return int(final_k), int(final_p), final_y

@st.cache_data
def load_data(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM items", conn)
    conn.close()
    
    df = df.rename(columns={
        'Net (ကျပ်) Net_kyat': 'Net_Kyat',
        'Net (ပဲ) Net_pae': 'Net_Pe',
        'Net (ရွေး) Net_yway': 'Net_Yway'
    })

    numeric_cols = ['qty_on_hand', 'weight_gram', 'Net_Kyat', 'Net_Pe', 'Net_Yway',
                    'smith_wage_kyat', 'smith_wage_pe', 'smith_wage_ywe',
                    'sale_wage_profit_kyat', 'sale_wage_profit_pe', 'sale_wage_profit_ywe']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'search_text' not in df.columns:
        df['search_text'] = df['item_code'].astype(str) + " " + df['item_name'].astype(str)

    df['Net Weight (Total)'] = df.apply(lambda row: format_burmese_weight(row['Net_Kyat'], row['Net_Pe'], row['Net_Yway']), axis=1)
    df['Smith Wage (Total)'] = df.apply(lambda row: format_burmese_weight(row['smith_wage_kyat'], row['smith_wage_pe'], row['smith_wage_ywe']), axis=1)
    df['Sale Profit (Total)'] = df.apply(lambda row: format_burmese_weight(row['sale_wage_profit_kyat'], row['sale_wage_profit_pe'], row['sale_wage_profit_ywe']), axis=1)
    return df

# --- MAIN APP LOGIC ---
st.title("💍 Gold Inventory PWA")

# FIXED: Removed 'type="db"' to allow all file selection on mobile browsers
uploaded_file = st.file_uploader("Upload Gold Database file", type=None)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name

    try:
        df = load_data(tmp_path)
        
        search_term = st.text_input("🔍 Search Inventory:", placeholder="Ring, Necklace...")
        mask = df.apply(lambda row: search_term.lower() in str(row.get('search_text', '')).lower() or 
                                    search_term.lower() in str(row.get('item_code', '')).lower() or 
                                    search_term.lower() in str(row.get('goldsmith_id', '')).lower(), axis=1)
        f_df = df[mask]

        st.write("---")
        tk, tp, ty = get_normalized_totals(f_df)
        
        m1, m2 = st.columns(2)
        m1.metric("In-Stock (Qty)", int(f_df['qty_on_hand'].sum()))
        m1.metric("Total Grams", f"{f_df['weight_gram'].sum():.3f} g")
        m2.metric("Net Weight", f"{tk} ကျပ် {tp} ပဲ {ty} ရွေး")
        m2.metric("Unique Items", len(f_df))

        show_charts = st.checkbox("Show Analysis", value=False)
        if show_charts and not f_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig_cat = px.bar(f_df.groupby('category')['qty_on_hand'].sum().reset_index(), 
                                 x='category', y='qty_on_hand', title="Qty by Category", template=chart_template)
                st.plotly_chart(fig_cat, use_container_width=True)
            with c2:
                fig_pie = px.pie(f_df, values='weight_gram', names='category', title="Weight Distribution", 
                                 hole=0.4, template=chart_template)
                st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("📋 Product List")
        display_cols = ['item_code', 'item_name', 'qty_on_hand', 'Net Weight (Total)', 'weight_gram', 'Smith Wage (Total)', 'Sale Profit (Total)', 'status']

        # ORIGINAL COLOR HIGHLIGHTING
        def highlight_text(val):
            if 'Smith' in str(val.name): return 'color: #FFB700; font-weight: bold;'
            if 'Sale' in str(val.name): return 'color: #00E676; font-weight: bold;'
            return ''

        st.dataframe(
            f_df[display_cols].style.apply(lambda x: [highlight_text(x) for _ in x], axis=0),
            use_container_width=True, height=400
        )

        st.divider()
        st.subheader("🔍 Item Deep Dive")
        selected_id = st.selectbox("Select Item Code:", options=df['item_code'].unique(), index=None, placeholder="Type item code...")
        
        if selected_id:
            detail = df[df['item_code'] == selected_id].iloc[0]
            d1, d2, d3 = st.columns(3)
            with d1:
                st.info(f"**Goldsmith:** {detail.get('goldsmith_id', 'N/A')}")
                st.write(f"**Item Name:** {detail.get('item_name', 'N/A')}")
            with d2:
                st.info(f"**Status:** {detail.get('status', 'N/A')}")
                st.write(f"**Purity:** {detail.get('purity', 'N/A')}")
            with d3:
                st.info(f"**Location:** {detail.get('location', 'N/A')}")
                st.write(f"**Date:** {detail.get('listed_date', 'N/A')}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    st.info("👋 Please upload your database file to start.")

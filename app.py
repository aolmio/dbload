import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import tempfile

# --- 1. PWA & THEME ENGINE CONFIG ---
# This must be the first Streamlit command
st.set_page_config(page_title="Gold Inventory Pro", layout="wide", initial_sidebar_state="expanded")

# Initialize Theme in Session State
if 'theme' not in st.session_state:
    st.session_state.theme = 'Dark'

# Sidebar Theme Toggle
with st.sidebar:
    st.title("📱 App Settings")
    theme_choice = st.radio("Appearance Mode", ["Light", "Dark"], 
                            index=1 if st.session_state.theme == "Dark" else 0)
    st.session_state.theme = theme_choice
    st.divider()

# Define Theme Colors
if st.session_state.theme == "Dark":
    bg_color = "#0E1117"
    text_color = "#FAFAFA"
    card_bg = "#262730"
    accent = "#FFB700"
    chart_theme = "plotly_dark"
else:
    bg_color = "#FFFFFF"
    text_color = "#31333F"
    card_bg = "#F0F2F6"
    accent = "#FF4B4B"
    chart_theme = "plotly_white"

# Inject Custom CSS for Mobile PWA and Themes
st.markdown(f"""
    <style>
    /* PWA Full Screen Fix */
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
    }}
    /* Responsive Metric Font Sizes for Mobile */
    [data-testid="stMetricValue"] {{
        font-size: 1.5rem !important;
        color: {accent};
    }}
    /* Mobile-friendly table font */
    .stDataFrame {{
        font-size: 12px;
    }}
    /* Style sidebar */
    [data-testid="stSidebar"] {{
        background-color: {card_bg};
    }}
    /* Custom button styling */
    .stButton>button {{
        width: 100%;
        border-radius: 10px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---
def format_burmese_weight(k, p, y):
    parts = []
    if k > 0: parts.append(f"{int(k)} ကျပ်")
    if p > 0: parts.append(f"{int(p)} ပဲ")
    if y > 0: parts.append(f"{y} ရွေး")
    return " ".join(parts) if parts else "0"

def get_normalized_totals(df_subset):
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

# --- 3. MAIN APP INTERFACE ---
st.title("💍 Gold Pro Mobile")

# MOBILE FIX: We use accept_multiple_files=False and a more generic type 
# to ensure mobile file pickers don't grey out the database file.
uploaded_file = st.file_uploader(
    "Select Gold Database (.db)", 
    type=["db", "sqlite", "sqlite3"], 
    help="On mobile, look in your 'Files' or 'Downloads' folder."
)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name

    try:
        df = load_data(tmp_path)
        
        # Search (Sticky top-like behavior)
        search_term = st.text_input("🔍 Search Item or Goldsmith:", placeholder="Type here...")
        
        mask = df.apply(lambda row: search_term.lower() in str(row.get('search_text', '')).lower() or 
                                    search_term.lower() in str(row.get('item_code', '')).lower() or 
                                    search_term.lower() in str(row.get('goldsmith_id', '')).lower(), axis=1)
        f_df = df[mask]

        # Mobile Metrics (2 columns for readability on small screens)
        tk, tp, ty = get_normalized_totals(f_df)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Items", len(f_df))
            st.metric("Total Grams", f"{f_df['weight_gram'].sum():.2f}g")
        with col2:
            st.metric("Stock Qty", int(f_df['qty_on_hand'].sum()))
            st.metric("BMS Weight", f"{tk}K {tp}P {ty}Y")

        # Charts with Theme Integration
        show_charts = st.sidebar.checkbox("Show Visual Charts", value=True)
        if show_charts and not f_df.empty:
            st.write("---")
            # Using the chart_theme variable defined in Step 1
            fig_cat = px.bar(f_df.groupby('category')['qty_on_hand'].sum().reset_index(), 
                             x='category', y='qty_on_hand', 
                             template=chart_theme, color_discrete_sequence=[accent])
            st.plotly_chart(fig_cat, use_container_width=True)

        # Inventory List
        st.subheader("📋 Product List")
        display_cols = ['item_code', 'item_name', 'qty_on_hand', 'Net Weight (Total)', 'status']
        st.dataframe(f_df[display_cols], use_container_width=True)

        # Detailed Lookup
        st.divider()
        selected_id = st.selectbox("Quick Detail Lookup:", options=df['item_code'].unique(), index=None)
        
        if selected_id:
            detail = df[df['item_code'] == selected_id].iloc[0]
            with st.expander("💎 Item Specifications", expanded=True):
                st.write(f"**Name:** {detail.get('item_name')}")
                st.write(f"**Goldsmith:** {detail.get('goldsmith_id')}")
                st.write(f"**Status:** {detail.get('status')}")
                st.write(f"**Weight:** {detail.get('Net Weight (Total)')}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
else:
    st.info("👋 Ready to work. Please upload your database file to view stock.")

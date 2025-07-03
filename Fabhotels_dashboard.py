import streamlit as st
import pandas as pd
import requests
from sqlalchemy import create_engine
import psycopg2 as psql


# --- Config from Secrets ---
OPENROUTER_API_KEY =st.secrets["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"]
REDSHIFT_URI = st.secrets["REDSHIFT_URI"]
MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

# --- Connect to Redshift ---
@st.cache_resource
def get_connection():
    return psql.connect(
        host="postgres-instance-1.fabhotels.com",
        database="analysisdata",
        user="readonly",
        password="ncmYtk8T447xHkgX"
    )
def run_sql(query):
    conn = get_connection()
    return pd.read_sql_query(query, conn)


# --- Get list of cities ---
@st.cache_data
def get_city_list():
    query = """
        SELECT DISTINCT property_city
        FROM mtd
        WHERE (property_name LIKE 'Fab%' OR property_name LIKE 'Oriva%')
        AND property_city NOT IN ('Gotham', 'daman11')
        ORDER BY property_city
    """
    return run_sql(query)["property_city"].tolist()

# --- City-level summary ---
def get_city_summary(start_date, end_date, city):
    query = f"""
        SELECT
            '{city}' AS city,
            SUM(grand_total / 1.12) AS revenue,
            COUNT(room_night_booking_id) AS room_nights,
            ROUND(SUM(grand_total / 1.12) / NULLIF(COUNT(room_night_booking_id), 0), 2) AS adr
        FROM mtd
        WHERE guest_status IN (1, 2)
          AND booking_source NOT IN (13, 19, 3, 4, 21, 24)
          AND (property_name LIKE 'Fab%' OR property_name LIKE 'Oriva%')
          AND property_city = '{city}'
          AND stay_date BETWEEN '{start_date}' AND '{end_date}'
    """
    return run_sql(query)

# --- Property-level breakdown ---
def get_city_property_table(start_date, end_date, city):
    query = f"""
        SELECT
            property_id,
            property_name,
            SUM(grand_total / 1.12) AS revenue,
            COUNT(room_night_booking_id) AS room_nights,
            ROUND(SUM(grand_total / 1.12) / NULLIF(COUNT(room_night_booking_id), 0), 2) AS adr
        FROM mtd
        WHERE guest_status IN (1, 2)
          AND booking_source NOT IN (13, 19, 3, 4, 21, 24)
          AND (property_name LIKE 'Fab%' OR property_name LIKE 'Oriva%')
          AND property_city = '{city}'
          AND stay_date BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY property_id, property_name
        ORDER BY revenue DESC
    """
    return run_sql(query)

# --- OpenRouter GPT insight ---
def generate_insight_openrouter(metrics_df):
    prompt = f"""You are a hotel analyst. Here is the city performance:
    Revenue: ₹{metrics_df['revenue'][0]:,.0f}
    Room Nights: {metrics_df['room_nights'][0]}
    ADR: ₹{metrics_df['adr'][0]:,.0f}
    Give a 2-3 line summary and any notable trend or issue."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourappdomain.com",  # Optional
        "X-Title": "Hotel KPI Assistant"
    }

    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    return result["choices"][0]["message"]["content"]

# --- UI Layout ---
st.set_page_config("📊 City Performance Dashboard", layout="wide")
st.title("📊 City-Level Performance Dashboard")

# --- Sidebar Filters ---
start_date = st.sidebar.date_input("Start Date", pd.to_datetime("2025-06-01"))
end_date = st.sidebar.date_input("End Date", pd.to_datetime("2025-06-30"))
selected_city = st.sidebar.selectbox("🏙️ Select a City", get_city_list())

# --- Load Data Button ---
if st.sidebar.button("🔄 Load City Data"):
    with st.spinner("Loading data..."):
        city_summary = get_city_summary(start_date, end_date, selected_city)
        property_table = get_city_property_table(start_date, end_date, selected_city)

    # --- City-Level Metrics ---
    st.markdown(f"## 📍 City: **{selected_city}**")
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Revenue", f"₹{city_summary['revenue'][0]:,.0f}")
    col2.metric("🛏️ Room Nights", f"{city_summary['room_nights'][0]:,}")
    col3.metric("📈 ADR", f"₹{city_summary['adr'][0]:,.0f}")

    # --- Property Table ---
    st.markdown("### 🏨 Property-wise Performance")
    st.dataframe(property_table, use_container_width=True)

    # --- AI Insight ---
    st.markdown("### 🤖 GPT Insight")

    with st.spinner("Analyzing with Mistral..."):
        insight = generate_insight_openrouter(city_summary)
        st.success(insight)


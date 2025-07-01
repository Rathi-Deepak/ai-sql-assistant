import streamlit as st
import pandas as pd
import requests
import re

# --- CONFIG ---
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

# --- UI SETUP ---
st.set_page_config(page_title="AI SQL Assistant", layout="centered")
st.title("🔍 Natural Language to SQL")
st.markdown("Ask your data question in plain English. We'll convert it to SQL. (Execution disabled for demo)")

question = st.text_input("💬 Enter your query:")

# --- Schema Context for the LLM ---
schema_context = """
You are working with a PostgreSQL table called `mtd` that stores hotel booking data.

✅ Columns of interest:
- stay_date, created_at, grand_total, booking_id, booking_source, ota_booking_source,
  room_night_booking_id, guest_status, property_city, property_name, property_id

✅ Filters & Inclusions:
- Only include records where:
    - guest_status IN (1, 2)
    - property_name starts with 'Fab' or 'Oriva'
    - property_city NOT IN ('Gotham')

✅ Revenue Logic:
- Use `grand_total / 1.12` as net revenue (excludes tax)

✅ Room Night Count:
- Count of room_night_booking_id

✅ ADR Logic:
- Net revenue / Count of room_night_booking_id

✅ Monthly Aggregation:
- Use DATE_TRUNC('month', stay_date) AS month to group data by month
- For sold data, use DATE_TRUNC('month', created_at) AS month instead

✅ Monthly Trend Analysis:
- To compare metrics over months, use stay_date or created_at (as applicable) and truncate to month
- Use CURRENT_DATE - INTERVAL '1 month', etc. for rolling periods

✅ Pivoting Monthly Metrics:
- Use ARRAY_AGG or CASE WHEN logic to show month-wise trends

✅ Channel Mapping Logic (for B2C aggregation):
- booking_source IN (2) → 'IS'
- ota_booking_source = 5 → 'BDC'
- ota_booking_source = 12 → 'Agoda'
- ota_booking_source IN (1, 2) → 'GoMMT'
- booking_source IN (6, 11, 15, 23) → 'Web/App'
- booking_source IN (1, 28) AND ota_booking_source NOT IN (1, 2, 5, 12) → 'OTA-Other'
- booking_source IN (13, 19) → 'Owner'

✅ B2C Revenue & Room Nights:
- Use above filters + exclude booking_source IN (13, 19, 3, 4, 21, 24)

✅ B2B Revenue & Room Nights:
- booking_source IN (3, 4, 21, 24)

✅ Sold Revenue & Room Nights:
- Based on created_at (not stay_date)
- Combine:
    - B2C bookings: booking_source NOT IN (13, 19, 3, 4, 21, 24)
    - Owner bookings: booking_source IN (13, 19) AND property_id IN (980831, 980015, 913204, 990439)

✅ Guest Status Mapping:
- 0 = Pending
- 1 = Checked-in
- 2 = Checked-out
- 3 = No-show
- 5 = Cancelled

📅 Time Range Defaults:
- If the user question does **not** mention any time period or date range:
    - Apply `stay_date >= '2025-01-01'` for most queries.
    - If the query is about **sold revenue** or uses `created_at`, apply `created_at >= '2025-01-01'`.

Only return safe, optimized **SELECT** statements. No DELETE/UPDATE. No explanations or markdown.
"""

if question:
    st.markdown("---")
    st.info("Generating SQL query from your input...")

    prompt = f"""
    {schema_context}

    Convert this question into an optimized SQL query:
    Question: {question}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        res.raise_for_status()
        response_json = res.json()

        raw_content = response_json["choices"][0]["message"]["content"]
        match = re.search(r"```sql\n(.*?)```", raw_content, re.DOTALL | re.IGNORECASE)
        sql_query_cleaned = str(match.group(1).strip() if match else raw_content.strip())

        if not sql_query_cleaned:
            st.error("❌ The model did not return any valid SQL. Please try rephrasing.")
        else:
            st.subheader("📄 Generated SQL")
            st.code(sql_query_cleaned, language="sql")
            st.caption("⚠️ SQL execution is disabled in this demo. Copy the query and use it in your own environment.")

    except Exception as e:
        st.error(f"❌ API Error: {e}")

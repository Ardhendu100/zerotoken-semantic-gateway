import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="ZeroToken Gateway Observability",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ ZeroToken Gateway — Real-time Semantic Cache Observability")
st.markdown("Sub-15ms Enterprise Multi-Tenant Gateway Metrics & Cost Savings Tracker")

def load_data():
    conn = sqlite3.connect("zerotoken_metrics.db")
    df = pd.read_sql_query("SELECT * FROM request_logs ORDER BY id DESC", conn)
    conn.close()
    return df

df = load_data()

if df.empty:
    st.info("No request logs recorded yet. Send requests to http://localhost:8000/v1/chat/completions to populate metrics!")
else:
    # Top KPI Bar
    col1, col2, col3, col4 = st.columns(4)
    
    total_requests = len(df)
    cache_hits = len(df[df['cache_status'] == 'HIT'])
    hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0.0
    avg_latency = df['latency_ms'].mean()
    total_saved = df['cost_saved_usd'].sum()

    col1.metric("Total Requests", f"{total_requests:,}")
    col2.metric("Cache Hit Rate", f"{hit_rate:.1f}%")
    col3.metric("Avg Latency", f"{avg_latency:.1f} ms")
    col4.metric("Cost Savings", f"${total_saved:.4f}")

    st.markdown("---")

    # Visualizations Section
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Latency Comparison (HIT vs MISS)")
        fig_lat = px.box(
            df, 
            x="cache_status", 
            y="latency_ms", 
            color="cache_status",
            labels={"cache_status": "Cache Status", "latency_ms": "Latency (ms)"},
            color_discrete_map={"HIT": "#00CC96", "MISS": "#EF553B", "BYPASS": "#FFA15A"}
        )
        st.plotly_chart(fig_lat, use_container_width=True)

    with col_chart2:
        st.subheader("Cache Status Distribution")
        fig_pie = px.pie(
            df, 
            names="cache_status", 
            color="cache_status",
            hole=0.4,
            color_discrete_map={"HIT": "#00CC96", "MISS": "#EF553B", "BYPASS": "#FFA15A"}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Detailed Logs Table
    st.subheader("Recent Request Logs")
    st.dataframe(
        df[["timestamp", "tenant_id", "cache_status", "latency_ms", "similarity_score", "cost_saved_usd"]],
        use_container_width=True
    )

    if st.button("🔄 Refresh Data"):
        st.rerun()
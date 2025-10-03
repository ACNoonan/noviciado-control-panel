import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Noviciado Attendance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# Force light theme
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: white;
    }
    [data-testid="stHeader"] {
        background-color: white;
    }
    [data-testid="stToolbar"] {
        background-color: white;
    }
    .stApp {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = Path("/app/data/attendance.db")

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

st.title("📊 Noviciado Club Attendance Dashboard")
st.markdown("---")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.rerun()

try:
    conn = get_db_connection()
    
    # Overall stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_members = conn.execute("""
            SELECT COUNT(DISTINCT phone_number) as count FROM attendance
        """).fetchone()['count']
        st.metric("Total Members", total_members)
    
    with col2:
        today = datetime.now().date()
        today_count = conn.execute("""
            SELECT COUNT(*) as count FROM attendance WHERE date = ?
        """, (today,)).fetchone()['count']
        st.metric("Today's Attendance", today_count)
    
    with col3:
        total_visits = conn.execute("""
            SELECT COUNT(*) as count FROM attendance
        """).fetchone()['count']
        st.metric("Total Check-ins", total_visits)
    
    with col4:
        total_messages = conn.execute("""
            SELECT COUNT(*) as count FROM messages
        """).fetchone()['count']
        st.metric("Total Messages", total_messages)
    
    st.markdown("---")
    
    # Recent attendance
    st.subheader("📅 Recent Attendance (Last 30 Days)")
    
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_df = pd.read_sql_query("""
        SELECT 
            date,
            contact_name,
            phone_number,
            first_message_time
        FROM attendance
        WHERE date >= ?
        ORDER BY date DESC, first_message_time DESC
    """, conn, params=(thirty_days_ago,))
    
    if not recent_df.empty:
        recent_df['date'] = pd.to_datetime(recent_df['date']).dt.strftime('%Y-%m-%d')
        recent_df['first_message_time'] = pd.to_datetime(recent_df['first_message_time']).dt.strftime('%H:%M:%S')
        recent_df.columns = ['Date', 'Name', 'Phone', 'First Check-in Time']
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.info("No attendance records yet.")
    
    st.markdown("---")
    
    # Daily attendance chart
    st.subheader("📈 Daily Attendance Trend")
    
    daily_df = pd.read_sql_query("""
        SELECT 
            date,
            COUNT(*) as count
        FROM attendance
        WHERE date >= ?
        GROUP BY date
        ORDER BY date
    """, conn, params=(thirty_days_ago,))
    
    if not daily_df.empty:
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        st.line_chart(daily_df.set_index('date')['count'])
    else:
        st.info("No data to display yet.")
    
    st.markdown("---")
    
    # Most active members
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏆 Most Active Members")
        top_members = pd.read_sql_query("""
            SELECT 
                contact_name as Name,
                COUNT(*) as Visits
            FROM attendance
            GROUP BY contact_name
            ORDER BY Visits DESC
            LIMIT 10
        """, conn)
        
        if not top_members.empty:
            st.dataframe(top_members, use_container_width=True, hide_index=True)
        else:
            st.info("No data yet.")
    
    with col2:
        st.subheader("💬 Most Messages Sent")
        top_messagers = pd.read_sql_query("""
            SELECT 
                contact_name as Name,
                COUNT(*) as Messages
            FROM messages
            GROUP BY contact_name
            ORDER BY Messages DESC
            LIMIT 10
        """, conn)
        
        if not top_messagers.empty:
            st.dataframe(top_messagers, use_container_width=True, hide_index=True)
        else:
            st.info("No data yet.")
    
    conn.close()
    
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.info("Make sure the attendance tracker is running and collecting data.")

st.markdown("---")
st.caption("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


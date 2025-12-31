import streamlit as st
import pandas as pd
import time
import plotly.express as px
from sentinel_engine import SentinelEngine
import ai_utils

st.set_page_config(
    page_title="SentinelLM Dashboard",
    page_icon="🛡️",
    layout="wide"
)

# Initialize Engine (Singleton)
@st.cache_resource
def get_engine():
    eng = SentinelEngine()
    # Auto-start for demo convenience
    eng.start_producer()
    eng.start_consumer()
    return eng

engine = get_engine()

# Sidebar
st.sidebar.title("🛡️ SentinelLM Control")
st.sidebar.markdown("---")

# Status Indicators
st.sidebar.subheader("System Status")
status_col1, status_col2 = st.sidebar.columns(2)
with status_col1:
    if engine.producer_running:
        st.success("Producer: ON")
    else:
        st.error("Producer: OFF")

with status_col2:
    if engine.consumer_running:
        st.success("Consumer: ON")
    else:
        st.error("Consumer: OFF")

st.sidebar.markdown("---")

# Controls
st.sidebar.subheader("Pipeline Controls")
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Start System"):
        engine.start_producer()
        engine.start_consumer()
        st.rerun()
with col2:
    if st.button("Stop System"):
        engine.stop_producer()
        engine.stop_consumer()
        engine.stop_processor()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Anomaly Injection")
if st.sidebar.button("🔥 Trigger Token Runaway"):
    engine.trigger_anomaly('token_runaway')
    st.sidebar.warning("Next event will have high token count!")

if st.sidebar.button("🔄 Trigger Infinite Loop"):
    engine.trigger_anomaly('loop_count')
    st.sidebar.warning("Next event will have high loop count!")

st.sidebar.markdown("---")
# Enable Local Processor by default for the demo so anomalies are generated locally
use_local_processor = st.sidebar.checkbox("Enable Local Processor (Simulate Flink)", value=True)
if use_local_processor:
    engine.start_processor()
else:
    engine.stop_processor()

# AI Voice Settings
st.sidebar.markdown("---")
enable_ai_voice = st.sidebar.checkbox("Enable AI Voice Alerts (Gemini + ElevenLabs)", value=True)

# Logs Expander
with st.sidebar.expander("System Logs", expanded=False):
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    
    new_logs = engine.get_logs()
    if new_logs:
        st.session_state.logs.extend(new_logs)
        st.session_state.logs = st.session_state.logs[-50:]
    
    for log in reversed(st.session_state.logs):
        st.text(log)

# Main Dashboard
st.title("SentinelLM: AI Agent Observability")
st.markdown("Real-time monitoring of AI Agent behavior and anomaly detection.")

# Metrics Row
m1, m2, m3 = st.columns(3)
m1.metric("Active Agents", "5")
m2.metric("Events Processed", "1,234")
m3.metric("Anomalies Detected", "12", delta="2")

# Live Feeds
col_events, col_anomalies = st.columns(2)

# We use session state to accumulate data for display
if 'events_df' not in st.session_state:
    st.session_state.events_df = pd.DataFrame(columns=['ts', 'node_name', 'model_name', 'tokens_used', 'step_index'])
if 'anomalies_df' not in st.session_state:
    # Initialize with columns for both schemas to be safe
    st.session_state.anomalies_df = pd.DataFrame(columns=['ts', 'node_name', 'reason', 'tokens_used', 'step_index', 'anomaly_type', 'total_tokens', 'loop_count'])

# Fetch new data
new_events = engine.get_recent_events()
new_anomalies = engine.get_recent_anomalies()

if new_events:
    new_df = pd.DataFrame(new_events)
    # Keep only relevant columns for display
    # Handle potential missing columns if schema changed mid-stream
    cols = ['ts', 'node_name', 'model_name', 'tokens_used', 'step_index']
    for c in cols:
        if c not in new_df.columns:
            new_df[c] = None
            
    display_df = new_df[cols]
    st.session_state.events_df = pd.concat([new_df, st.session_state.events_df]).head(20)

if new_anomalies:
    new_df = pd.DataFrame(new_anomalies)
    if not new_df.empty and not new_df.isna().all().all():
        st.session_state.anomalies_df = pd.concat([new_df, st.session_state.anomalies_df]).head(20)
        
        # AI Voice Alert Logic
        if enable_ai_voice:
            latest_anomaly = new_anomalies[-1] # Get the most recent one
            
            # Avoid duplicate alerts for the same trace_id in this session loop
            if 'last_alert_trace' not in st.session_state:
                st.session_state.last_alert_trace = None
            
            current_trace = latest_anomaly.get('trace_id')
            
            if current_trace != st.session_state.last_alert_trace:
                st.session_state.last_alert_trace = current_trace
                
                with st.spinner("Generating AI Alert..."):
                    # 1. Generate Summary with Gemini
                    summary = ai_utils.generate_anomaly_summary(latest_anomaly)
                    st.toast(f"AI Summary: {summary}", icon="🤖")
                    
                    # 2. Generate Audio with ElevenLabs
                    audio_bytes = ai_utils.text_to_speech(summary)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)

with col_events:
    st.subheader("📡 Live Agent Events")
    if not st.session_state.events_df.empty:
        st.dataframe(st.session_state.events_df[['node_name', 'model_name', 'tokens_used', 'step_index']], height=400)

with col_anomalies:
    st.subheader("🚨 Detected Anomalies")
    if not st.session_state.anomalies_df.empty:
        # Determine columns to display based on what's available in the dataframe
        available_cols = st.session_state.anomalies_df.columns.tolist()
        display_cols = []
        
        # New Schema Columns
        if 'anomaly_type' in available_cols: display_cols.append('anomaly_type')
        if 'total_tokens' in available_cols: display_cols.append('total_tokens')
        if 'loop_count' in available_cols: display_cols.append('loop_count')
        
        # Old Schema Columns (fallback)
        if not display_cols:
            if 'node_name' in available_cols: display_cols.append('node_name')
            if 'tokens_used' in available_cols: display_cols.append('tokens_used')
            if 'step_index' in available_cols: display_cols.append('step_index')
            
        # If still empty, show all
        if not display_cols:
            display_cols = available_cols

        st.dataframe(st.session_state.anomalies_df[display_cols], height=400)
        
        # Show latest alert detail
        latest = st.session_state.anomalies_df.iloc[0]
        st.error(f"Latest Alert: Anomaly Detected!")
        st.json(latest.to_dict())
    else:
        st.info("No anomalies detected yet.")

# Auto-refresh
time.sleep(1)
st.rerun()

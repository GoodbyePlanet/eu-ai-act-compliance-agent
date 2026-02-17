import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

def fetch_recent_session(email):
    try:
        response = requests.get(f"{API_URL}/sessions/recent", params={"user_email": email})
        if response.ok:
            return response.json()
    except Exception as e:
        st.error(f"Could not connect to backend to check recent sessions: {e}")
    return None

def fetch_session_history(email):
    try:
        response = requests.get(f"{API_URL}/sessions", params={"user_email": email})
        if response.ok:
            return response.json().get("sessions", [])
    except Exception:
        pass
    return []

def load_historical_session(session_id, email):
    try:
        response = requests.get(f"{API_URL}/sessions/{session_id}", params={"user_email": email})
        if response.ok:
            data = response.json()
            st.session_state.session_id = session_id
            st.session_state.ai_tool_name = data.get("ai_tool")
            st.session_state.tool_report_resp = data.get("summary")
            st.session_state.pdf_data = None
        else:
            st.error("Failed to load session data.")
    except Exception as e:
        st.error(f"Error loading session: {e}")

def run_assessment(payload):
    return requests.post(f"{API_URL}/run", json=payload)

def generate_pdf(session_id, email):
    return requests.get(f"{API_URL}/pdf", params={"session_id": session_id, "user_email": email})
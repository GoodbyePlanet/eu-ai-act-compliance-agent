import uuid

import requests
import streamlit as st

st.set_page_config(page_title="PD AI Tool Assessment Agent")
st.title("PD AI Tool Assessment Agent")

ai_tool = st.text_input("Write the name of the AI tool to assess", placeholder="e.g. Notion AI")

if st.button("Assess AI tool"):
    if not all([ai_tool]):
        st.warning("Please fill in name of the AI tool to assess.")
    else:
        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())

        payload = {"ai_tool": ai_tool, "session_id": st.session_state.session_id}
        response = requests.post("http://localhost:8000/run", json=payload)

        if response.ok:
            data = response.json()
            st.markdown(data["summary"], unsafe_allow_html=True)
        else:
            st.error("Failed to assess AI tool. Please try again.")

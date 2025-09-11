# views/genres/state.py
import streamlit as st

PLACEHOLDER = "— choose a root genre —"
CLEAR_FLAG  = "__clear_search_next__"
# state.py
CLEAR_FLAG_GENRES = "genres_clear_once"
CLEAR_FLAG_RADIO  = "radio_clear_once"

def on_root_change():
    sel = st.session_state.get("root_select", PLACEHOLDER)
    if sel and sel != PLACEHOLDER:
        st.session_state["genres_path"] = [sel]
        st.session_state.pop("genres_search_results", None)
        st.session_state.pop("genres_search_page", None)
        st.session_state[CLEAR_FLAG] = True

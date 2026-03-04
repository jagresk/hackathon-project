# dashboard.py
import sys
import os
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="Customertimes",
    layout="wide",
    initial_sidebar_state="collapsed",
)

VALID_USERNAME = "khatera"
VALID_PASSWORD = "12345"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "login_error" not in st.session_state:
    st.session_state.login_error = False

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
    iframe { border: none !important; display: block !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
def login_page():
    st.markdown("""
    <style>
        html, body, .stApp { background: #e8eaf6 !important; }

        /* ── Center everything in the viewport ── */
        .block-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 0 !important;
        }
        [data-testid="stVerticalBlock"] {
            width: 100%;
            max-width: 400px;
            margin: 0 auto;
        }

        /* ── Kill the stray form border box ── */
        [data-testid="stForm"] {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }

        /* ── Input labels ── */
        [data-testid="stTextInput"] label p {
            font-size: 0.78em !important;
            font-weight: 600 !important;
            color: #555 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* ── Input fields ── */
        [data-testid="stTextInput"] input {
            border-radius: 9px !important;
            border: 1.5px solid #e4e6f0 !important;
            padding: 11px 14px !important;
            font-size: 0.94em !important;
            background: #fafbff !important;
        }
        [data-testid="stTextInput"] input:focus {
            border-color: #1976d2 !important;
            box-shadow: 0 0 0 3px rgba(25,118,210,0.10) !important;
            background: #fff !important;
        }

        /* ── Password show/hide button — icon only, no blue fill ── */
        [data-testid="stTextInput"] button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #b0b8cc !important;
            padding: 0 10px !important;
            min-height: unset !important;
        }
        [data-testid="stTextInput"] button:hover {
            background: transparent !important;
            color: #1976d2 !important;
        }

        /* ── Submit button ── */
        [data-testid="stFormSubmitButton"] {
            display: flex;
            justify-content: center;
            margin-top: 4px;
        }
        [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #1976d2 0%, #42a5f5 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 9px !important;
            font-weight: 600 !important;
            font-size: 0.94em !important;
            padding: 11px 0 !important;
            width: 100% !important;
            box-shadow: 0 4px 14px rgba(25,118,210,0.25) !important;
            letter-spacing: 0.15px !important;
        }
        [data-testid="stFormSubmitButton"] button:hover {
            filter: brightness(1.07) !important;
        }

        /* ── Error message ── */
        [data-testid="stAlert"] {
            border-radius: 8px !important;
            font-size: 0.86em !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Branding block
    st.markdown("""
    <div style="
        background: white;
        border-radius: 20px;
        padding: 52px 44px 44px;
        box-shadow: 0 10px 48px rgba(25,118,210,0.10), 0 2px 12px rgba(0,0,0,0.06);
        text-align: center;
        margin-top: 60px;
    ">
        <div style="
            display: inline-flex; align-items: center; justify-content: center;
            width: 66px; height: 66px;
            background: linear-gradient(135deg, #1976d2 0%, #42a5f5 100%);
            border-radius: 16px; font-size: 1.65em; font-weight: 900;
            color: white; letter-spacing: -1px; margin-bottom: 20px;
            box-shadow: 0 6px 20px rgba(25,118,210,0.28);
        ">CT</div>
        <div style="font-size: 1.5em; font-weight: 700; color: #1976d2; margin-bottom: 6px;">
            Customertimes
        </div>
        <div style="font-size: 0.88em; color: #aaa; margin-bottom: 32px;">
            AI-Powered Predictive Maintenance
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.login_error:
        st.error("Incorrect username or password.")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Login to Dashboard")

    if submitted:
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.login_error = False
            st.rerun()
        else:
            st.session_state.login_error = True
            st.rerun()

    st.markdown("""
    <div style="text-align:center; font-size:0.75em; color:#ccc; margin-top:20px;">
        Hackathon Project — Secure Access Required
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
def dashboard():
    st.markdown("""
    <style>
        html, body, .stApp { background: #f0f2f5 !important; overflow: hidden; }

        /* Top bar via columns */
        [data-testid="stHorizontalBlock"] {
            background: linear-gradient(135deg, #1976d2 0%, #42a5f5 100%) !important;
            padding: 8px 20px !important;
            box-shadow: 0 2px 8px rgba(25,118,210,0.18) !important;
            align-items: center !important;
            gap: 0 !important;
        }
        [data-testid="stHorizontalBlock"] [data-testid="stVerticalBlock"] {
            padding: 0 !important;
            gap: 0 !important;
        }

        /* Logout button */
        [data-testid="stHorizontalBlock"] button {
            background: rgba(255,255,255,0.14) !important;
            color: white !important;
            border: 1px solid rgba(255,255,255,0.28) !important;
            border-radius: 5px !important;
            font-size: 0.78em !important;
            font-weight: 600 !important;
            padding: 4px 14px !important;
            min-height: unset !important;
            height: 28px !important;
            float: right;
        }
        [data-testid="stHorizontalBlock"] button:hover {
            background: rgba(255,255,255,0.24) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([0.05, 0.81, 0.14])
    with c1:
        st.markdown("""
        <div style="display:inline-flex;align-items:center;justify-content:center;
             width:32px;height:32px;background:rgba(255,255,255,0.2);
             border-radius:7px;font-size:0.85em;font-weight:900;color:white;letter-spacing:-0.5px;">
            CT
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(
            '<span style="font-size:0.95em;font-weight:700;color:white;">Customertimes</span>'
            '<span style="font-size:0.78em;color:rgba(255,255,255,0.72);margin-left:8px;">'
            'AI-Powered Predictive Maintenance — FANUC Cobot</span>',
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.rerun()

    timeline_path = os.path.join(os.path.dirname(__file__), "static", "sensor_timeline.html")

    @st.cache_data
    def load_timeline():
        with open(timeline_path, "r", encoding="utf-8") as f:
            return f.read()

    try:
        html_content = load_timeline()
    except FileNotFoundError:
        st.error("sensor_timeline.html not found — copy it into the static/ folder.")
        st.stop()

    components.html(html_content, height=900, scrolling=False)


# ── Entry point ───────────────────────────────────────────────────────────────
if st.session_state.authenticated:
    dashboard()
else:
    login_page()
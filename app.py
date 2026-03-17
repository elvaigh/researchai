"""ResearchAI — Main entry point"""
import streamlit as st
import sys, os

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _APP_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_APP_DIR, ".env"), override=False)

from utils.db import init_db, create_workspace, get_workspaces, get_user_by_id
from utils.auth import login_user, register_user

st.set_page_config(
    page_title="ResearchAI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ──────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Manrope:wght@300;400;500;600;700;800&display=swap');

/* ── Dark base — cover every surface Streamlit renders ── */
html, body { background:#0d0f14 !important; }
[class*="css"], [data-testid="stAppViewContainer"],
[data-testid="stApp"], .stApp,
.main, .main .block-container,
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"] > div {
  background:#0d0f14 !important;
  font-family:'Manrope',sans-serif;
}
.main .block-container {
  padding:1.6rem 2.2rem 3rem !important;
  max-width:1280px;
}
/* Expander body */
[data-testid="stExpander"] > div:last-child,
.streamlit-expanderContent {
  background:#0d0f14 !important;
  border:1px solid rgba(99,102,241,0.12) !important;
  border-top:none !important;
}
/* Popover / dropdown overlays */
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="select"] ul,
[role="listbox"] {
  background:#13161f !important;
  border:1px solid rgba(99,102,241,0.2) !important;
  color:#e0e7ff !important;
}
[role="option"] { background:#13161f !important; color:#e0e7ff !important; }
[role="option"]:hover { background:rgba(99,102,241,0.15) !important; }
/* Number inputs, checkboxes, radio */
.stNumberInput input, .stTextInput input, .stTextArea textarea {
  background:#0d0f14 !important; color:#e0e7ff !important;
}
[data-testid="stCheckbox"] label,
[data-testid="stRadio"] label,
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label {
  color:#9ca3af !important;
}
/* Checkbox / radio widget backgrounds */
[data-testid="stCheckbox"] > label > div,
[data-baseweb="checkbox"] {
  background:transparent !important;
}
/* st.status / st.spinner containers */
[data-testid="stStatusWidget"],
[data-testid="stAlert"],
div[class*="StatusWidget"] {
  background:#13161f !important;
  border:1px solid rgba(99,102,241,0.15) !important;
  color:#e0e7ff !important;
  border-radius:10px !important;
}
/* Multiselect */
[data-baseweb="tag"] {
  background:rgba(99,102,241,0.2) !important;
  color:#c7d2fe !important;
}
/* st.code blocks */
.stCode, [data-testid="stCodeBlock"], pre, code {
  background:#080a0f !important;
  color:#a5b4fc !important;
  border:1px solid rgba(99,102,241,0.15) !important;
  border-radius:8px !important;
}
/* Download / link buttons in main area */
.main [data-testid="stDownloadButton"] button,
.main [data-testid="stLinkButton"] a {
  background:#6366f1 !important;
  color:#fff !important;
  border:none !important;
  border-radius:10px !important;
  font-weight:600 !important;
}
.main [data-testid="stDownloadButton"] button:hover,
.main [data-testid="stLinkButton"] a:hover {
  background:#4f46e5 !important;
}
/* File uploader */
[data-testid="stFileUploadDropzone"] {
  background:#13161f !important;
  border:2px dashed rgba(99,102,241,0.3) !important;
  border-radius:12px !important;
  color:#9ca3af !important;
}
/* Dividers */
hr { border-color:rgba(99,102,241,0.1) !important; }
/* Scrollbar */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#0d0f14; }
::-webkit-scrollbar-thumb { background:rgba(99,102,241,0.3); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:rgba(99,102,241,0.6); }

/* Hide chrome */
#MainMenu,header,footer,[data-testid="stDecoration"],
[data-testid="stToolbar"],[data-testid="stStatusWidget"],
[data-testid="stHeader"]{display:none!important;}

/* Hide Streamlit auto-generated pages nav (the "app / chat / library…" list) */
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"],
section[data-testid="stSidebar"] ul,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] nav,
.st-emotion-cache-pbsa99,
[class*="stPageLink"] { display:none !important; }

/* ── Sidebar ────────────────────────────────────────── */
section[data-testid="stSidebar"]{
  background:#080a0f !important;
  border-right:1px solid rgba(255,255,255,0.05) !important;
  min-width:220px!important; max-width:320px!important;
  overflow-y:auto!important;
}
section[data-testid="stSidebar"]>div:first-child{padding:0!important;}

[data-testid="stSidebarResizeHandle"]{
  background:rgba(99,102,241,0.3)!important; width:3px!important;
}
[data-testid="stSidebarResizeHandle"]:hover{background:rgba(99,102,241,0.7)!important;}

/* Sidebar brand */
.sb-brand{
  padding:1.8rem 1.4rem 1.1rem;
  border-bottom:1px solid rgba(255,255,255,0.05);
}
.sb-logo{
  font-family:'Instrument Serif',serif;
  font-size:1.4rem; color:#e0e7ff;
  letter-spacing:-0.02em; line-height:1.1;
}
.sb-user{
  font-size:0.68rem; color:#4b5563;
  margin-top:0.3rem; text-transform:uppercase; letter-spacing:0.08em;
}

/* Sidebar section label */
.sb-label{
  font-size:0.6rem; font-weight:700; letter-spacing:0.15em;
  text-transform:uppercase; color:#374151!important;
  padding:1rem 1.4rem 0.3rem;
}

/* Sidebar nav buttons */
[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;
  color:#9ca3af!important; border:none!important;
  border-radius:8px!important; padding:0.65rem 1.1rem!important;
  font-size:0.9rem!important; font-weight:500!important;
  text-align:left!important; width:100%!important;
  transition:background .15s,color .15s!important;
  box-shadow:none!important; margin:2px 0!important;
}
[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(99,102,241,0.12)!important;
  color:#e0e7ff!important; transform:none!important; box-shadow:none!important;
}
[data-testid="stSidebar"] .stSelectbox>div>div{
  background:rgba(255,255,255,0.04)!important;
  border:1px solid rgba(255,255,255,0.08)!important;
  border-radius:8px!important; color:#e0e7ff!important; font-size:0.85rem!important;
}
[data-testid="stSidebar"] .stSelectbox label{display:none!important;}
[data-testid="stSidebar"] hr{
  border-color:rgba(255,255,255,0.05)!important; margin:0.5rem 1.2rem!important;
}
.signout-btn button{
  background:rgba(239,68,68,0.07)!important; color:#f87171!important;
  border:1px solid rgba(239,68,68,0.18)!important; border-radius:8px!important;
  font-size:0.85rem!important;
}
.signout-btn button:hover{background:rgba(239,68,68,0.15)!important;}

/* ── Page header ────────────────────────────────────── */
.app-header{
  background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 50%,#1a0533 100%);
  border-radius:16px; padding:1.8rem 2.2rem; margin-bottom:2rem;
  position:relative; overflow:hidden;
  border:1px solid rgba(99,102,241,0.2);
}
.app-header::before{
  content:''; position:absolute; inset:0;
  background:radial-gradient(ellipse at 80% 0%,rgba(99,102,241,0.2) 0%,transparent 60%);
}
.app-header h1{
  font-family:'Instrument Serif',serif!important;
  color:#f0f4ff!important; margin:0!important;
  font-size:2rem!important; letter-spacing:-0.02em!important;
  position:relative; font-weight:400!important;
}
.app-header p{
  color:rgba(199,210,254,0.65)!important;
  margin:0.4rem 0 0!important; font-size:0.88rem!important;
  position:relative; font-weight:400!important;
}

/* ── Cards ──────────────────────────────────────────── */
.card{
  background:#13161f; border-radius:14px;
  padding:1.4rem 1.7rem; margin-bottom:0.9rem;
  border:1px solid rgba(99,102,241,0.15);
  border-left:3px solid #6366f1;
  transition:border-color .2s, box-shadow .2s;
}
.card:hover{
  border-color:rgba(99,102,241,0.4);
  box-shadow:0 4px 24px rgba(99,102,241,0.1);
}
.card-title{
  font-size:0.97rem; font-weight:600; color:#e0e7ff;
  margin-bottom:0.4rem; line-height:1.45;
}
.card-meta{font-size:0.76rem; color:#6b7280; margin-bottom:0.5rem;}
.card-abstract{font-size:0.83rem; color:#9ca3af; line-height:1.7;}
.card-score{
  display:inline-flex; align-items:center; gap:4px;
  background:rgba(99,102,241,0.12); color:#818cf8;
  border-radius:6px; padding:2px 8px; font-size:0.7rem; font-weight:600;
}

/* ── Badges ─────────────────────────────────────────── */
.badge{display:inline-flex;align-items:center;border-radius:20px;padding:2px 9px;font-size:0.68rem;font-weight:600;margin-right:4px;}
.badge-indigo{background:rgba(99,102,241,0.15);color:#818cf8;}
.badge-green {background:rgba(16,185,129,0.12);color:#34d399;}
.badge-blue  {background:rgba(59,130,246,0.12);color:#60a5fa;}
.badge-gray  {background:rgba(107,114,128,0.15);color:#9ca3af;}

/* ── Buttons (main area) ────────────────────────────── */
.main .stButton>button{
  background:#6366f1!important; color:#fff!important;
  border:none!important; border-radius:10px!important;
  font-weight:600!important; font-size:0.85rem!important;
  padding:0.5rem 1.2rem!important; transition:all .18s!important;
}
.main .stButton>button:hover{
  background:#4f46e5!important; transform:translateY(-1px)!important;
  box-shadow:0 4px 16px rgba(99,102,241,0.4)!important;
}
.main .stButton>button[kind="secondary"]{
  background:rgba(99,102,241,0.1)!important; color:#818cf8!important;
  border:1px solid rgba(99,102,241,0.25)!important;
}
.main .stButton>button[kind="secondary"]:hover{background:rgba(99,102,241,0.2)!important;}

/* ── Inputs ─────────────────────────────────────────── */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea{
  background:#0d0f14!important; border:1.5px solid rgba(99,102,241,0.25)!important;
  border-radius:10px!important; color:#e0e7ff!important;
  font-family:'Manrope',sans-serif!important; font-size:0.88rem!important;
}
.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus{
  border-color:#6366f1!important;
  box-shadow:0 0 0 3px rgba(99,102,241,0.15)!important;
}

/* ── Tabs ───────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"]{background:transparent!important;border-bottom:1px solid rgba(99,102,241,0.15)!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#6b7280!important;font-size:0.875rem!important;font-weight:500!important;border-bottom:2px solid transparent!important;margin-bottom:-1px!important;padding:0.6rem 1.2rem!important;}
.stTabs [aria-selected="true"]{color:#818cf8!important;border-bottom-color:#6366f1!important;font-weight:600!important;}

/* ── Metrics ────────────────────────────────────────── */
[data-testid="metric-container"]{
  background:#13161f; border-radius:12px; padding:1rem 1.2rem!important;
  border:1px solid rgba(99,102,241,0.12);
}
[data-testid="metric-container"] [data-testid="stMetricLabel"]{font-size:0.72rem!important;font-weight:700!important;text-transform:uppercase!important;letter-spacing:.07em!important;color:#6b7280!important;}
[data-testid="metric-container"] [data-testid="stMetricValue"]{font-family:'Instrument Serif',serif!important;font-size:1.8rem!important;color:#e0e7ff!important;}

/* ── Select ─────────────────────────────────────────── */
.stSelectbox>div>div{background:#0d0f14!important;border:1.5px solid rgba(99,102,241,0.25)!important;border-radius:10px!important;color:#e0e7ff!important;}

/* ── Progress ───────────────────────────────────────── */
.stProgress>div>div>div{background:linear-gradient(90deg,#6366f1,#818cf8)!important;border-radius:4px!important;}

/* ── Expander ───────────────────────────────────────── */
.streamlit-expanderHeader{background:#13161f!important;border:1px solid rgba(99,102,241,0.15)!important;border-radius:10px!important;color:#e0e7ff!important;font-weight:600!important;}

/* ── Chat ───────────────────────────────────────────── */
.chat-user{background:linear-gradient(135deg,#4f46e5,#6366f1);color:#fff;padding:.85rem 1.2rem;border-radius:18px 18px 4px 18px;margin:.5rem 0 .5rem auto;max-width:72%;font-size:.87rem;line-height:1.65;box-shadow:0 2px 10px rgba(99,102,241,.3);}
.chat-ai{background:#13161f;color:#e0e7ff;padding:.85rem 1.2rem;border-radius:18px 18px 18px 4px;margin:.5rem 0;max-width:80%;font-size:.87rem;line-height:1.65;border-left:3px solid #6366f1;border:1px solid rgba(99,102,241,.15);}
.tldr-box{background:#0f1220;border-left:3px solid #6366f1;border-radius:10px;padding:.9rem 1.1rem;font-size:.83rem;color:#a5b4fc;margin:.6rem 0;line-height:1.7;border:1px solid rgba(99,102,241,.15);}

/* ── Divider ────────────────────────────────────────── */
hr{border-color:rgba(99,102,241,0.1)!important;}

/* ── Alerts ─────────────────────────────────────────── */
.stAlert{border-radius:10px!important;font-size:.875rem!important;}
</style>
""", unsafe_allow_html=True)

# ── DB init ────────────────────────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    st.error(f"⚠️ Database connection failed: {e}\n\nCheck your secrets / .env file.")
    st.stop()

# ── Session defaults ───────────────────────────────────────────────────────
_DEFAULTS = {
    "user": None, "workspace": None, "page": "search",
    "chat_session_id": None, "chat_messages": [],
    "current_review": None, "current_review_query": None,
    "generated_text": None, "generated_section": None,
    "editing_doc": None, "lr_fetched": [],
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Session persistence (URL param ?uid=) ──────────────────────────────────
def _persist(user):  st.query_params["uid"] = str(user["id"])
def _clear():        st.query_params.clear()

def _rehydrate():
    if st.session_state.user: return
    uid_str = st.query_params.get("uid", "")
    if not uid_str: return
    try:
        uid = int(uid_str)
        user = get_user_by_id(uid)
        if not user: _clear(); return
        st.session_state.user = user
        if not st.session_state.workspace:
            wss = get_workspaces(uid)
            st.session_state.workspace = wss[0] if wss else create_workspace(uid, "My Research")
    except Exception:
        _clear()

def _sidebar_visibility():
    if not st.session_state.user:
        st.markdown("""<style>
        section[data-testid="stSidebar"],
        section[data-testid="stSidebarCollapsedControl"]{display:none!important;}
        .block-container{padding-left:2rem!important;}
        </style>""", unsafe_allow_html=True)


# ── Auth page ──────────────────────────────────────────────────────────────
def render_auth():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:4rem 0 2.5rem;">
          <div style="font-size:3rem;margin-bottom:.8rem;">🔬</div>
          <div style="font-family:'Instrument Serif',serif;font-size:2.6rem;
                      color:#e0e7ff;letter-spacing:-.03em;line-height:1;">ResearchAI</div>
          <p style="color:#4b5563;margin-top:.6rem;font-size:.92rem;font-weight:400;">
            AI-powered academic research platform
          </p>
        </div>
        """, unsafe_allow_html=True)

        t1, t2 = st.tabs(["Sign In", "Create Account"])
        with t1:
            with st.form("login_form"):
                st.text_input("Email", placeholder="you@university.edu", key="li_email")
                st.text_input("Password", type="password", key="li_pass")
                if st.form_submit_button("Sign In →", use_container_width=True, type="primary"):
                    user, err = login_user(st.session_state.li_email, st.session_state.li_pass)
                    if user:
                        st.session_state.user = user
                        _persist(user); st.rerun()
                    else:
                        st.error(err or "Login failed.")
        with t2:
            with st.form("register_form"):
                st.text_input("Full Name", placeholder="Dr. Jane Smith", key="reg_name")
                st.text_input("Email", placeholder="you@university.edu", key="reg_email")
                st.text_input("Password", type="password", key="reg_pass")
                st.text_input("Confirm Password", type="password", key="reg_pass2")
                if st.form_submit_button("Create Account →", use_container_width=True, type="primary"):
                    if not all([st.session_state.reg_name, st.session_state.reg_email,
                                st.session_state.reg_pass, st.session_state.reg_pass2]):
                        st.warning("Please fill all fields.")
                    elif st.session_state.reg_pass != st.session_state.reg_pass2:
                        st.error("Passwords do not match.")
                    else:
                        user, err = register_user(st.session_state.reg_email,
                                                  st.session_state.reg_name,
                                                  st.session_state.reg_pass)
                        if user:
                            st.session_state.user = user
                            _persist(user); st.rerun()
                        else:
                            st.error(err or "Registration failed.")


# ── Sidebar ────────────────────────────────────────────────────────────────
def render_sidebar():
    user = st.session_state.user
    ws   = st.session_state.workspace
    with st.sidebar:
        st.markdown(f"""
        <div class="sb-brand">
          <div class="sb-logo">🔬 ResearchAI</div>
          <div class="sb-user">{user['username']}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="sb-label">Workspace</div>', unsafe_allow_html=True)
        workspaces = get_workspaces(user["id"])
        if not workspaces:
            nm = st.text_input("", placeholder="My Research Project", key="new_ws_sb")
            if st.button("➕ Create Workspace", use_container_width=True):
                if nm:
                    st.session_state.workspace = create_workspace(user["id"], nm)
                    st.rerun()
        else:
            ws_map = {w["name"]: w for w in workspaces}
            cur    = ws["name"] if ws and ws["name"] in ws_map else list(ws_map.keys())[0]
            sel    = st.selectbox("ws", list(ws_map.keys()),
                                  index=list(ws_map.keys()).index(cur),
                                  label_visibility="collapsed")
            if ws_map[sel]["id"] != (ws or {}).get("id"):
                st.session_state.workspace       = ws_map[sel]
                st.session_state.chat_session_id = None
                st.session_state.chat_messages   = []
                st.rerun()
            with st.expander("➕ New workspace"):
                nn = st.text_input("Name", key="new_ws_name")
                nd = st.text_input("Description", key="new_ws_desc")
                if st.button("Create", key="create_ws_btn"):
                    if nn:
                        st.session_state.workspace = create_workspace(user["id"], nn, nd)
                        st.rerun()

        st.markdown("---")
        st.markdown('<div class="sb-label">Navigation</div>', unsafe_allow_html=True)

        NAV = [
            ("🔍", "search",     "AI Search"),
            ("📚", "library",    "My Library"),
            ("💬", "chat",       "Chat with Papers"),
            ("📊", "review",     "Literature Review"),
            ("✍️",  "writer",    "AI Writer"),
            ("🔖", "references", "References"),
        ]
        cur_page = st.session_state.page
        for icon, key, label in NAV:
            active = cur_page == key
            if active:
                st.markdown(
                    '<div style="background:rgba(99,102,241,0.18);border-radius:8px;margin:2px 0;">',
                    unsafe_allow_html=True)
            if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key; st.rerun()
            if active:
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="signout-btn">', unsafe_allow_html=True)
        if st.button("🚪  Sign Out", use_container_width=True, key="signout_btn"):
            _clear()
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ── Router ─────────────────────────────────────────────────────────────────
def main():
    _rehydrate()
    _sidebar_visibility()
    if not st.session_state.user:
        render_auth(); return
    if not st.session_state.workspace:
        wss = get_workspaces(st.session_state.user["id"])
        st.session_state.workspace = wss[0] if wss else create_workspace(
            st.session_state.user["id"], "My Research")
    render_sidebar()
    page = st.session_state.page
    if page == "search":
        from pages.search     import render; render()
    elif page == "library":
        from pages.library    import render; render()
    elif page == "chat":
        from pages.chat       import render; render()
    elif page == "review":
        from pages.review     import render; render()
    elif page == "writer":
        from pages.writer     import render; render()
    elif page == "references":
        from pages.references import render; render()
    else:
        from pages.search     import render; render()

if __name__ == "__main__":
    main()
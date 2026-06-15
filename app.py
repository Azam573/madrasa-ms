"""
app.py — Smart Madrasa ERP
Main entry point: auth gate → sidebar nav → module routing.
Run: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Smart Madrasa ERP",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── imports after set_page_config ──
from db import bootstrap_schema, fetchone
from utils import inject_css, get_tenant_id, PALETTE
from auth import check_auth, logout, can_access, ROLE_PERMISSIONS

import dashboard, admission_module, finance_module, academic_module
import student_portal, attendance_module, reports_module
import settings_module, teacher_module, notice_module, print_module
from auth import render_user_management

# ──────────────────────────────────────────────────────────────────────────────
# Auth gate
# ──────────────────────────────────────────────────────────────────────────────
if not check_auth():
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Schema bootstrap (once per session)
# ──────────────────────────────────────────────────────────────────────────────
if "schema_ready" not in st.session_state:
    with st.spinner("ডেটাবেস প্রস্তুত করা হচ্ছে…"):
        ok = bootstrap_schema()
    if ok:
        st.session_state.schema_ready = True
        tid = st.session_state.get("tenant_id", 1)
        active = fetchone(
            "SELECT id FROM academic_sessions WHERE tenant_id=%s AND is_active=TRUE LIMIT 1",
            (tid,),
        )
        if active:
            st.session_state.active_session_id = active["id"]
    else:
        st.error("⚠️ ডেটাবেস কানেকশন ব্যর্থ। DATABASE_URL চেক করুন।")
        st.stop()

inject_css()

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Dashboard"

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
tid         = get_tenant_id()
role        = st.session_state.get("user_role", "staff")
user_name   = st.session_state.get("user_name", "ব্যবহারকারী")
madrasa     = st.session_state.get("madrasa_name", "Smart Madrasa")

# Unread notification badge
unread_row = fetchone(
    "SELECT COUNT(*) AS n FROM notifications WHERE tenant_id=%s AND is_read=FALSE",
    (tid,),
) if st.session_state.get("schema_ready") else None
unread_count = int(unread_row["n"]) if unread_row else 0

with st.sidebar:
    st.markdown(
        f"""<div style="padding:1rem 0 0.5rem;text-align:center">
            <div style="font-size:2.2rem">🕌</div>
            <div style="font-weight:700;font-size:0.95rem;color:#EAF4F8;margin-top:0.2rem">
                {madrasa}
            </div>
            <div style="font-size:0.7rem;color:rgba(234,244,248,0.55)">Smart Madrasa ERP</div>
        </div>
        <div style="background:rgba(255,255,255,0.1);border-radius:8px;
                    padding:0.5rem 0.75rem;margin:0.5rem 0;font-size:0.78rem;color:#EAF4F8">
            👤 {user_name}
            <span style="float:right;background:rgba(255,255,255,0.2);
                         border-radius:12px;padding:0.1rem 0.5rem;font-size:0.7rem">
                {role.title()}
            </span>
        </div>
        <hr style="border-color:rgba(255,255,255,0.15);margin:0.5rem 0">""",
        unsafe_allow_html=True,
    )

    ALL_NAV = {
        "🏠  ড্যাশবোর্ড":        "Dashboard",
        "🎓  ভর্তি ব্যবস্থাপনা":  "Admissions",
        "💰  ফি ও অর্থ":          "Finance",
        "📚  পরীক্ষা ও ফলাফল":   "Academics",
        "📅  উপস্থিতি":           "Attendance",
        "👨‍🏫  শিক্ষক ব্যবস্থাপনা": "Teachers",
        "📈  রিপোর্ট":            "Reports",
        f"📢  নোটিশ {'🔴' if unread_count else ''}": "Notice Board",
        "🏫  ছাত্র পোর্টাল":      "Student Portal",
        "👥  ব্যবহারকারী":        "User Management",
        "🖨️  প্রিন্ট সেন্টার":      "Print Center",
        "⚙️  সেটিংস":             "Settings",
    }

    for label, page_key in ALL_NAV.items():
        if not can_access(role, page_key):
            continue
        is_active = st.session_state.nav_page == page_key
        if st.button(label, key=f"nav_{page_key}", use_container_width=True):
            st.session_state.nav_page = page_key
            st.rerun()

    st.markdown(
        "<hr style='border-color:rgba(255,255,255,0.15);margin:0.75rem 0 0.5rem'>",
        unsafe_allow_html=True,
    )
    if st.button("🚪 লগআউট", use_container_width=True, key="logout_btn"):
        logout()

    st.markdown(
        f"""<div style="font-size:0.65rem;color:rgba(234,244,248,0.4);
                        text-align:center;padding:0.25rem 0">
            Tenant #{tid} · v2.0.0
        </div>""",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Page routing
# ──────────────────────────────────────────────────────────────────────────────
PAGE = st.session_state.nav_page

if not can_access(role, PAGE):
    st.error(f"⛔ আপনার এই পেজ দেখার অনুমতি নেই। (Role: {role})")
    st.stop()

ROUTES = {
    "Dashboard":       dashboard.render,
    "Admissions":      admission_module.render,
    "Finance":         finance_module.render,
    "Academics":       academic_module.render,
    "Attendance":      attendance_module.render,
    "Teachers":        teacher_module.render,
    "Reports":         reports_module.render,
    "Notice Board":    notice_module.render,
    "Student Portal":  student_portal.render,
    "User Management": render_user_management,
    "Print Center":    print_module.render,
    "Settings":        settings_module.render,
}

fn = ROUTES.get(PAGE)
if fn:
    fn()
else:
    st.error(f"অজানা পেজ: {PAGE}")

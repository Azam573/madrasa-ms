"""
auth.py — Multi-Tenant Login & Session Management
Role-based access: admin | staff | teacher | accountant
Demo mode: username=admin, password=admin123
"""

import streamlit as st
import hashlib
from db import get_connection, fetchone, fetchall
from utils import inject_css, PALETTE


# ──────────────────────────────────────────────────────────────────────────────
# Password helpers (SHA-256 for demo; use bcrypt in production)
# ──────────────────────────────────────────────────────────────────────────────

def _hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def _verify_password(pwd: str, stored_hash: str) -> bool:
    # Demo mode: stored_hash == 'demo_hash_admin123' → accept 'admin123'
    if stored_hash == "demo_hash_admin123":
        return pwd == "admin123"
    return _hash_password(pwd) == stored_hash


# ──────────────────────────────────────────────────────────────────────────────
# Auth DB helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_tenants():
    return fetchall("SELECT id, madrasa_name, slug FROM tenants ORDER BY madrasa_name")


def _authenticate(tenant_id: int, username: str, password: str):
    user = fetchone(
        """SELECT id, username, password_hash, role, full_name, is_active
           FROM app_users
           WHERE tenant_id=%s AND username=%s""",
        (tenant_id, username.strip()),
    )
    if not user:
        return None, "ব্যবহারকারী পাওয়া যায়নি।"
    if not user["is_active"]:
        return None, "এই অ্যাকাউন্টটি নিষ্ক্রিয়।"
    if not _verify_password(password, user["password_hash"]):
        return None, "পাসওয়ার্ড ভুল।"
    return user, None


def _create_user(tenant_id, username, password, role, full_name, email):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO app_users
                   (tenant_id, username, password_hash, role, full_name, email)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (tenant_id, username.strip(), _hash_password(password),
                 role, full_name.strip(), email.strip()),
            )
            uid = cur.fetchone()["id"]
        conn.commit()
        return True, uid
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _get_users(tenant_id):
    return fetchall(
        "SELECT id, username, role, full_name, email, is_active FROM app_users WHERE tenant_id=%s ORDER BY id",
        (tenant_id,),
    )


def _toggle_user(tenant_id, user_id, is_active):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_users SET is_active=%s WHERE id=%s AND tenant_id=%s",
                (is_active, user_id, tenant_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def _change_password(tenant_id, user_id, new_password):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_users SET password_hash=%s WHERE id=%s AND tenant_id=%s",
                (_hash_password(new_password), user_id, tenant_id),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Role-based access control
# ──────────────────────────────────────────────────────────────────────────────

ROLE_PERMISSIONS = {
    "admin":      ["Dashboard", "Admissions", "Finance", "Academics",
                   "Attendance", "Teachers", "Reports", "Notice Board",
                   "Student Portal", "Print Center", "Settings", "User Management"],
    "staff":      ["Dashboard", "Admissions", "Finance", "Attendance",
                   "Notice Board", "Student Portal", "Print Center"],
    "teacher":    ["Dashboard", "Academics", "Attendance", "Notice Board",
                   "Student Portal"],
    "accountant": ["Dashboard", "Finance", "Reports", "Student Portal", "Print Center"],
}

def can_access(role: str, page: str) -> bool:
    return page in ROLE_PERMISSIONS.get(role, [])


# ──────────────────────────────────────────────────────────────────────────────
# Login page UI
# ──────────────────────────────────────────────────────────────────────────────

def _login_page():
    inject_css()
    st.markdown(
        f"""<div style="max-width:420px;margin:3rem auto">
          <div style="text-align:center;margin-bottom:2rem">
            <div style="font-size:3.5rem">🕌</div>
            <h1 style="font-size:1.6rem;font-weight:700;color:{PALETTE['primary']};margin:0.5rem 0 0.25rem">
              Smart Madrasa ERP
            </h1>
            <p style="color:{PALETTE['muted']};font-size:0.85rem">
              আধুনিক মাদ্রাসা ব্যবস্থাপনা সিস্টেম
            </p>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Center the form
    _, col, _ = st.columns([1, 2, 1])
    with col:
        tenants = _get_tenants()
        if not tenants:
            st.error("কোনো মাদ্রাসা নিবন্ধিত নেই। ডেটাবেস সেটআপ চেক করুন।")
            return

        tenant_opts = {t["madrasa_name"]: t["id"] for t in tenants}

        with st.form("login_form"):
            st.markdown(
                f'<div style="background:{PALETTE["card"]};padding:1.5rem;'
                f'border-radius:12px;border:1px solid {PALETTE["border"]};'
                f'box-shadow:0 4px 20px rgba(15,76,92,0.12)">',
                unsafe_allow_html=True,
            )
            st.markdown("#### 🔐 লগইন করুন")

            selected_madrasa = st.selectbox("মাদ্রাসা নির্বাচন করুন", list(tenant_opts.keys()))
            username = st.text_input("ব্যবহারকারীর নাম", placeholder="admin")
            password = st.text_input("পাসওয়ার্ড", type="password", placeholder="••••••••")

            submitted = st.form_submit_button("🔐 লগইন", type="primary", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if submitted:
                if not username or not password:
                    st.error("ব্যবহারকারীর নাম ও পাসওয়ার্ড দিন।")
                    return

                tenant_id = tenant_opts[selected_madrasa]
                user, err = _authenticate(tenant_id, username, password)

                if err:
                    st.error(f"❌ {err}")
                else:
                    st.session_state["logged_in"]   = True
                    st.session_state["tenant_id"]   = tenant_id
                    st.session_state["user_id"]     = user["id"]
                    st.session_state["username"]    = user["username"]
                    st.session_state["user_role"]   = user["role"]
                    st.session_state["user_name"]   = user["full_name"] or user["username"]
                    st.session_state["madrasa_name"] = selected_madrasa
                    st.session_state["nav_page"]    = "Dashboard"
                    st.rerun()

        st.markdown(
            f'<div style="text-align:center;margin-top:1rem;'
            f'font-size:0.78rem;color:{PALETTE["muted"]};">'
            f'ডেমো: username=<b>admin</b> · password=<b>admin123</b></div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# User Management UI (admin only)
# ──────────────────────────────────────────────────────────────────────────────

def render_user_management():
    from utils import page_header, alert, divider
    tid  = st.session_state.get("tenant_id", 1)
    role = st.session_state.get("user_role", "staff")

    page_header("👥", "ব্যবহারকারী ব্যবস্থাপনা", "স্টাফ অ্যাকাউন্ট ও ভূমিকা পরিচালনা")

    if role != "admin":
        alert("⛔ শুধুমাত্র Admin এই পেজ দেখতে পারবেন।", "danger")
        return

    tab_list, tab_add, tab_pwd = st.tabs(["📋 ব্যবহারকারী তালিকা", "➕ নতুন ব্যবহারকারী", "🔑 পাসওয়ার্ড পরিবর্তন"])

    users = _get_users(tid)

    with tab_list:
        if not users:
            alert("কোনো ব্যবহারকারী নেই।", "info")
        else:
            ROLE_BADGE = {
                "admin":      "🔴 Admin",
                "staff":      "🟡 Staff",
                "teacher":    "🟢 Teacher",
                "accountant": "🔵 Accountant",
            }
            for u in users:
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.markdown(f"**{u['full_name'] or u['username']}**  \n`{u['username']}`")
                c2.markdown(ROLE_BADGE.get(u["role"], u["role"]))
                c3.markdown(u["email"] or "—")
                status_btn = "❌ নিষ্ক্রিয় করুন" if u["is_active"] else "✅ সক্রিয় করুন"
                if c4.button(status_btn, key=f"usr_tog_{u['id']}"):
                    _toggle_user(tid, u["id"], not u["is_active"])
                    st.rerun()
                st.markdown('<hr style="margin:0.4rem 0;border-color:#DDE3E7">', unsafe_allow_html=True)

    with tab_add:
        st.markdown("#### ➕ নতুন অ্যাকাউন্ট তৈরি করুন")
        with st.form("add_user_form"):
            c1, c2 = st.columns(2)
            new_username  = c1.text_input("ব্যবহারকারীর নাম *")
            new_full_name = c2.text_input("পূর্ণ নাম *")
            c3, c4 = st.columns(2)
            new_password = c3.text_input("পাসওয়ার্ড *", type="password")
            new_role     = c4.selectbox("ভূমিকা", ["staff", "teacher", "accountant", "admin"])
            new_email    = st.text_input("ইমেইল")

            if st.form_submit_button("✅ অ্যাকাউন্ট তৈরি করুন", type="primary"):
                if not new_username or not new_password or not new_full_name:
                    st.error("নাম, ব্যবহারকারী নাম ও পাসওয়ার্ড আবশ্যক।")
                elif len(new_password) < 6:
                    st.error("পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।")
                else:
                    ok, result = _create_user(tid, new_username, new_password,
                                               new_role, new_full_name, new_email)
                    if ok:
                        st.success(f"✅ অ্যাকাউন্ট তৈরি হয়েছে! ID: {result}")
                        st.rerun()
                    else:
                        st.error(f"ব্যর্থ: {result}")

    with tab_pwd:
        st.markdown("#### 🔑 পাসওয়ার্ড পরিবর্তন করুন")
        user_opts = {f"{u['full_name'] or u['username']} ({u['role']})": u["id"] for u in users}
        sel_user = st.selectbox("ব্যবহারকারী", list(user_opts.keys()))
        with st.form("pwd_form"):
            new_pwd1 = st.text_input("নতুন পাসওয়ার্ড", type="password")
            new_pwd2 = st.text_input("পাসওয়ার্ড নিশ্চিত করুন", type="password")
            if st.form_submit_button("🔑 পরিবর্তন করুন", type="primary"):
                if not new_pwd1 or not new_pwd2:
                    st.error("উভয় ঘর পূরণ করুন।")
                elif new_pwd1 != new_pwd2:
                    st.error("পাসওয়ার্ড মিলছে না।")
                elif len(new_pwd1) < 6:
                    st.error("পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।")
                else:
                    ok = _change_password(tid, user_opts[sel_user], new_pwd1)
                    if ok:
                        st.success("✅ পাসওয়ার্ড পরিবর্তন হয়েছে!")
                    else:
                        st.error("পরিবর্তন ব্যর্থ হয়েছে।")


# ──────────────────────────────────────────────────────────────────────────────
# Public API: check_auth()
# ──────────────────────────────────────────────────────────────────────────────

def check_auth() -> bool:
    """Returns True if user is logged in, else renders login page and returns False."""
    if st.session_state.get("logged_in"):
        return True
    _login_page()
    return False


def logout():
    for key in ["logged_in", "tenant_id", "user_id", "username",
                "user_role", "user_name", "madrasa_name", "nav_page",
                "active_session_id", "schema_ready"]:
        st.session_state.pop(key, None)
    st.rerun()

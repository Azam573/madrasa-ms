"""
settings_module.py — System configuration: tenant profile,
academic sessions, classes, and user management.
"""

import streamlit as st
from db import get_connection, fetchall, fetchone, execute
from utils import page_header, alert, divider, get_tenant_id


def _get_tenant(tid):
    return fetchone("SELECT * FROM tenants WHERE id=%s", (tid,))


def _update_tenant(tid, name, address, phone, email):
    execute(
        "UPDATE tenants SET madrasa_name=%s, address=%s, phone=%s, email=%s WHERE id=%s",
        (name, address, phone, email, tid),
    )


def _get_sessions(tid):
    return fetchall(
        "SELECT * FROM academic_sessions WHERE tenant_id=%s ORDER BY id DESC", (tid,)
    )


def _create_session(tid, name, start, end):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO academic_sessions (tenant_id, session_name, start_date, end_date, is_active)
                   VALUES (%s,%s,%s,%s,FALSE) RETURNING id""",
                (tid, name, start, end),
            )
            sid = cur.fetchone()["id"]
        conn.commit()
        return True, sid
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _set_active_session(tid, session_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE academic_sessions SET is_active=FALSE WHERE tenant_id=%s", (tid,))
            cur.execute(
                "UPDATE academic_sessions SET is_active=TRUE WHERE id=%s AND tenant_id=%s",
                (session_id, tid),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def _get_classes(tid):
    return fetchall(
        "SELECT * FROM classes WHERE tenant_id=%s ORDER BY class_numeric", (tid,)
    )


def _create_class(tid, name, numeric, section):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO classes (tenant_id, class_name, class_numeric, section)
                   VALUES (%s,%s,%s,%s) RETURNING id""",
                (tid, name, numeric, section),
            )
            cid = cur.fetchone()["id"]
        conn.commit()
        return True, cid
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def render():
    tid = get_tenant_id()
    page_header("⚙️", "Settings & Configuration", "Manage madrasa profile, sessions and classes")

    tab_profile, tab_sessions, tab_classes = st.tabs(
        ["🏫 Madrasa Profile", "📅 Academic Sessions", "🏛 Classes"]
    )

    # ── Madrasa Profile ──
    with tab_profile:
        tenant = _get_tenant(tid)
        if tenant:
            with st.form("profile_form"):
                st.markdown("##### 🏫 Madrasa Information")
                name    = st.text_input("Madrasa Name", value=tenant["madrasa_name"] or "")
                address = st.text_area("Address", value=tenant["address"] or "", height=68)
                c1, c2 = st.columns(2)
                phone   = c1.text_input("Phone", value=tenant["phone"] or "")
                email   = c2.text_input("Email", value=tenant["email"] or "")
                if st.form_submit_button("💾 Save Profile", type="primary"):
                    if not name.strip():
                        st.error("Madrasa name is required.")
                    else:
                        _update_tenant(tid, name.strip(), address.strip(), phone.strip(), email.strip())
                        st.success("Profile updated successfully!")

    # ── Academic Sessions ──
    with tab_sessions:
        sessions = _get_sessions(tid)
        st.markdown("##### 📅 Academic Sessions")
        if sessions:
            for s in sessions:
                col_name, col_status, col_btn = st.columns([3, 1, 1])
                col_name.markdown(f"**{s['session_name']}**  \n{str(s['start_date'] or '')} → {str(s['end_date'] or '')}")
                col_status.markdown(
                    "🟢 **Active**" if s["is_active"] else "⚪ Inactive"
                )
                if not s["is_active"]:
                    if col_btn.button("Set Active", key=f"sess_act_{s['id']}"):
                        if _set_active_session(tid, s["id"]):
                            # Store in session state
                            st.session_state["active_session_id"] = s["id"]
                            st.success(f"'{s['session_name']}' is now active.")
                            st.rerun()
        else:
            alert("No sessions yet. Create one below.", "info")

        divider()
        st.markdown("##### ➕ New Academic Session")
        with st.form("session_form"):
            s_name = st.text_input("Session Name", placeholder="e.g. 2025-2026")
            c1, c2 = st.columns(2)
            s_start = c1.date_input("Start Date", value=None)
            s_end   = c2.date_input("End Date", value=None)
            if st.form_submit_button("➕ Create Session", type="primary"):
                if not s_name.strip():
                    st.error("Session name required.")
                else:
                    ok, result = _create_session(tid, s_name.strip(), str(s_start), str(s_end))
                    if ok:
                        st.success(f"Session created! ID: {result}")
                        st.rerun()
                    else:
                        st.error(result)

    # ── Classes ──
    with tab_classes:
        classes = _get_classes(tid)
        st.markdown("##### 🏛 Existing Classes")
        if classes:
            rows = [
                {"ID": c["id"], "Class Name": c["class_name"],
                 "Order": c["class_numeric"], "Section": c.get("section") or "A"}
                for c in classes
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            alert("No classes yet.", "info")

        divider()
        st.markdown("##### ➕ Add Class")
        with st.form("class_form"):
            c1, c2, c3 = st.columns(3)
            c_name    = c1.text_input("Class Name", placeholder="e.g. Hifz-4")
            c_numeric = c2.number_input("Order/Numeric", min_value=1, value=1)
            c_section = c3.text_input("Section", value="A")
            if st.form_submit_button("➕ Add Class", type="primary"):
                if not c_name.strip():
                    st.error("Class name required.")
                else:
                    ok, result = _create_class(tid, c_name.strip(), int(c_numeric), c_section.strip() or "A")
                    if ok:
                        st.success(f"Class '{c_name}' added!")
                        st.rerun()
                    else:
                        st.error(result)

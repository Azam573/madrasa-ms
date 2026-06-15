"""
admission_module.py — Enterprise-grade multi-step admission form
and Admin approval panel for Smart Madrasa ERP.

Steps: 1) Personal Info  2) Enrollment Config  3) Review & Submit
Admin panel: assign roll numbers, activate students.
"""

import streamlit as st
from db import get_connection, fetchall, fetchone
from utils import (
    page_header, kpi_row, step_bar, badge, alert, divider,
    get_tenant_id, validate_mobile, validate_required,
)


# ──────────────────────────────────────────────────────────────────────────────
# Internal data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_sessions(tid):
    return fetchall(
        "SELECT id, session_name FROM academic_sessions WHERE tenant_id=%s ORDER BY id DESC",
        (tid,),
    )


def _get_classes(tid):
    return fetchall(
        "SELECT id, class_name, class_numeric FROM classes WHERE tenant_id=%s ORDER BY class_numeric",
        (tid,),
    )


def _get_active_session(tid):
    return fetchone(
        "SELECT id, session_name FROM academic_sessions WHERE tenant_id=%s AND is_active=TRUE LIMIT 1",
        (tid,),
    )


def _pending_enrollments(tid):
    return fetchall(
        """SELECT
            s.id AS student_id, s.name, s.father_name, s.mobile_no,
            s.status, s.created_at,
            e.id AS enrollment_id, e.roll_no, e.enrollment_status, e.monthly_fee,
            c.class_name, sess.session_name
        FROM students s
        JOIN student_enrollments e ON e.student_id = s.id AND e.tenant_id = s.tenant_id
        JOIN classes c ON c.id = e.class_id
        JOIN academic_sessions sess ON sess.id = e.session_id
        WHERE s.tenant_id = %s
          AND (s.status = 'pending' OR e.enrollment_status = 'pending')
        ORDER BY s.created_at DESC""",
        (tid,),
    )


def _active_students(tid):
    return fetchall(
        """SELECT
            s.id, s.name, s.father_name, s.mobile_no, s.status,
            e.roll_no, e.monthly_fee, e.enrollment_status,
            c.class_name, sess.session_name
        FROM students s
        JOIN student_enrollments e ON e.student_id = s.id AND e.tenant_id = s.tenant_id
        JOIN classes c ON c.id = e.class_id
        JOIN academic_sessions sess ON sess.id = e.session_id
        WHERE s.tenant_id = %s AND s.status = 'active'
        ORDER BY c.class_numeric, e.roll_no""",
        (tid,),
    )


def _admission_kpis(tid):
    total  = fetchone("SELECT COUNT(*) AS n FROM students WHERE tenant_id=%s", (tid,))
    active = fetchone("SELECT COUNT(*) AS n FROM students WHERE tenant_id=%s AND status='active'", (tid,))
    pend   = fetchone("SELECT COUNT(*) AS n FROM students WHERE tenant_id=%s AND status='pending'", (tid,))
    return (
        int(total["n"]) if total else 0,
        int(active["n"]) if active else 0,
        int(pend["n"]) if pend else 0,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 – Personal Information
# ──────────────────────────────────────────────────────────────────────────────

def _step_personal():
    st.markdown("#### 👤 Personal Information")
    c1, c2 = st.columns(2)
    name        = c1.text_input("Student Full Name *", placeholder="e.g. Muhammad Abdullah")
    father_name = c2.text_input("Father's Name *", placeholder="e.g. Muhammad Ibrahim")

    c3, c4 = st.columns(2)
    mobile_no = c3.text_input("Mobile Number", placeholder="01XXXXXXXXX")
    dob       = c4.date_input("Date of Birth", value=None)

    c5, c6 = st.columns(2)
    gender     = c5.selectbox("Gender", ["Male", "Female"])
    blood_grp  = c6.selectbox("Blood Group", ["—", "A+", "A−", "B+", "B−", "AB+", "AB−", "O+", "O−"])

    address = st.text_area("Present Address", height=68, placeholder="Village, Upazila, District")

    errors = []
    if not name.strip():   errors.append("Student name is required.")
    if not father_name.strip(): errors.append("Father's name is required.")
    if mobile_no and not validate_mobile(mobile_no):
        errors.append("Mobile number format is invalid (BD format expected).")

    return {
        "name": name.strip(),
        "father_name": father_name.strip(),
        "mobile_no": mobile_no.strip(),
        "dob": str(dob) if dob else None,
        "gender": gender,
        "blood_group": None if blood_grp == "—" else blood_grp,
        "present_address": address.strip(),
    }, errors


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 – Enrollment Configuration
# ──────────────────────────────────────────────────────────────────────────────

def _step_enrollment(tid):
    st.markdown("#### 📚 Enrollment Details")
    sessions = _get_sessions(tid)
    classes  = _get_classes(tid)

    if not sessions:
        alert("No academic session found. Please create one in Settings.", "warning")
        return None, ["No academic session available."]
    if not classes:
        alert("No class found. Please create classes in Settings.", "warning")
        return None, ["No class available."]

    sess_opts  = {s["session_name"]: s["id"] for s in sessions}
    class_opts = {c["class_name"]: c["id"] for c in classes}

    active_sess = _get_active_session(tid)
    default_sess = active_sess["session_name"] if active_sess else list(sess_opts.keys())[0]

    c1, c2 = st.columns(2)
    sel_sess  = c1.selectbox("Academic Session *", list(sess_opts.keys()),
                              index=list(sess_opts.keys()).index(default_sess))
    sel_class = c2.selectbox("Class *", list(class_opts.keys()))

    c3, c4 = st.columns(2)
    monthly_fee = c3.number_input("Monthly Fee (৳)", min_value=0, value=500, step=50)
    roll_no_placeholder = c4.text_input(
        "Roll No (optional — assign later)", placeholder="Leave blank for pending assignment"
    )

    roll_no = None
    if roll_no_placeholder.strip():
        try:
            roll_no = int(roll_no_placeholder)
        except ValueError:
            return None, ["Roll number must be a valid integer."]

    return {
        "session_id":  sess_opts[sel_sess],
        "class_id":    class_opts[sel_class],
        "monthly_fee": monthly_fee,
        "roll_no":     roll_no,
        "session_name": sel_sess,
        "class_name":   sel_class,
    }, []


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 – Review
# ──────────────────────────────────────────────────────────────────────────────

def _step_review(p_data, e_data):
    st.markdown("#### ✅ Review Before Submission")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        **Personal Details**
        | Field | Value |
        |---|---|
        | Name | {name} |
        | Father | {father_name} |
        | Mobile | {mobile_no} |
        | Gender | {gender} |
        | Blood Group | {blood_group} |
        | Address | {present_address} |
        """.format(**{k: v or "—" for k, v in p_data.items()}))
    with c2:
        st.markdown(f"""
        **Enrollment Details**
        | Field | Value |
        |---|---|
        | Session | {e_data['session_name']} |
        | Class | {e_data['class_name']} |
        | Monthly Fee | ৳ {e_data['monthly_fee']:,} |
        | Roll No | {e_data['roll_no'] or 'Pending'} |
        """)
    alert("Submission will save the student with <b>Pending</b> status. Admin must approve to activate.", "info")


# ──────────────────────────────────────────────────────────────────────────────
# DB write – atomic admission
# ──────────────────────────────────────────────────────────────────────────────

def _submit_admission(tid, p_data, e_data):
    conn = get_connection()
    if not conn:
        return False, "Database connection failed."
    try:
        with conn.cursor() as cur:
            # Insert student
            cur.execute(
                """INSERT INTO students
                   (tenant_id, name, father_name, mobile_no, date_of_birth,
                    gender, blood_group, present_address, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending')
                   RETURNING id""",
                (
                    tid, p_data["name"], p_data["father_name"],
                    p_data["mobile_no"] or None, p_data["dob"],
                    p_data["gender"], p_data["blood_group"],
                    p_data["present_address"],
                ),
            )
            student_id = cur.fetchone()["id"]

            # Insert enrollment
            cur.execute(
                """INSERT INTO student_enrollments
                   (tenant_id, student_id, session_id, class_id, roll_no,
                    monthly_fee, enrollment_status)
                   VALUES (%s,%s,%s,%s,%s,%s,'pending')""",
                (
                    tid, student_id,
                    e_data["session_id"], e_data["class_id"],
                    e_data["roll_no"], e_data["monthly_fee"],
                ),
            )
        conn.commit()
        return True, student_id
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Admin: Approve / Activate
# ──────────────────────────────────────────────────────────────────────────────

def _activate_student(tid, student_id, enrollment_id, roll_no):
    if not roll_no:
        return False, "Roll number is required to activate."
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE students SET status='active' WHERE id=%s AND tenant_id=%s",
                (student_id, tid),
            )
            cur.execute(
                """UPDATE student_enrollments
                   SET enrollment_status='active', roll_no=%s
                   WHERE id=%s AND tenant_id=%s""",
                (roll_no, enrollment_id, tid),
            )
        conn.commit()
        return True, None
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _reject_student(tid, student_id, enrollment_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE students SET status='inactive' WHERE id=%s AND tenant_id=%s",
                (student_id, tid),
            )
            cur.execute(
                "UPDATE student_enrollments SET enrollment_status='dropped' WHERE id=%s AND tenant_id=%s",
                (enrollment_id, tid),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    page_header("🎓", "Admission Management", "Register new students and manage approvals")

    total, active, pending = _admission_kpis(tid)
    kpi_row([
        {"label": "Total Students", "value": total,   "cls": ""},
        {"label": "Active",         "value": active,  "cls": "success"},
        {"label": "Pending Approval","value": pending, "cls": "warning"},
        {"label": "Inactive",       "value": total - active - pending, "cls": "danger"},
    ])

    tab_new, tab_pending, tab_list = st.tabs(
        ["➕ New Admission", "⏳ Pending Approvals", "📋 Student List"]
    )

    # ── Tab 1: Multi-step new admission ──
    with tab_new:
        # Step state
        if "adm_step" not in st.session_state:
            st.session_state.adm_step = 0
        if "adm_personal" not in st.session_state:
            st.session_state.adm_personal = {}
        if "adm_enroll" not in st.session_state:
            st.session_state.adm_enroll = {}

        step = st.session_state.adm_step
        step_bar(["Personal Info", "Enrollment", "Review & Submit"], step)

        with st.form("adm_form", clear_on_submit=False):
            if step == 0:
                p_data, errors = _step_personal()
                submitted = st.form_submit_button("Next →", type="primary")
                if submitted:
                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        st.session_state.adm_personal = p_data
                        st.session_state.adm_step = 1
                        st.rerun()

            elif step == 1:
                e_data, errors = _step_enrollment(tid)
                col_back, col_next = st.columns([1, 4])
                back = col_back.form_submit_button("← Back")
                nxt  = col_next.form_submit_button("Next →", type="primary")
                if back:
                    st.session_state.adm_step = 0
                    st.rerun()
                if nxt:
                    if errors:
                        for e in errors:
                            st.error(e)
                    elif e_data:
                        st.session_state.adm_enroll = e_data
                        st.session_state.adm_step = 2
                        st.rerun()

            elif step == 2:
                _step_review(st.session_state.adm_personal, st.session_state.adm_enroll)
                col_back, col_submit = st.columns([1, 4])
                back   = col_back.form_submit_button("← Back")
                submit = col_submit.form_submit_button("✅ Submit Admission", type="primary")
                if back:
                    st.session_state.adm_step = 1
                    st.rerun()
                if submit:
                    ok, result = _submit_admission(
                        tid,
                        st.session_state.adm_personal,
                        st.session_state.adm_enroll,
                    )
                    if ok:
                        st.success(f"✅ Student admitted! ID: {result}. Awaiting admin approval.")
                        st.session_state.adm_step = 0
                        st.session_state.adm_personal = {}
                        st.session_state.adm_enroll = {}
                        st.rerun()
                    else:
                        st.error(f"Submission failed: {result}")

    # ── Tab 2: Pending Approval Panel ──
    with tab_pending:
        st.markdown("#### ⏳ Pending Admissions — Assign Roll & Activate")
        rows = _pending_enrollments(tid)
        if not rows:
            alert("No pending admissions. All caught up! 🎉", "success")
        else:
            for row in rows:
                with st.expander(
                    f"**{row['name']}** — {row['class_name']} | {row['session_name']} | "
                    f"Applied: {str(row['created_at'])[:10]}"
                ):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"""
                        - **Father:** {row['father_name'] or '—'}
                        - **Mobile:** {row['mobile_no'] or '—'}
                        - **Monthly Fee:** ৳ {row['monthly_fee']:,.0f}
                        """)
                    with c2:
                        roll_key = f"roll_{row['enrollment_id']}"
                        new_roll = st.number_input(
                            "Assign Roll No", min_value=1, key=roll_key, value=1
                        )
                        col_a, col_r = st.columns(2)
                        if col_a.button("✅ Activate", key=f"act_{row['enrollment_id']}",
                                        type="primary"):
                            ok, err = _activate_student(
                                tid, row["student_id"], row["enrollment_id"], new_roll
                            )
                            if ok:
                                st.success("Student activated!")
                                st.rerun()
                            else:
                                st.error(err)
                        if col_r.button("❌ Reject", key=f"rej_{row['enrollment_id']}"):
                            if _reject_student(tid, row["student_id"], row["enrollment_id"]):
                                st.warning("Student rejected.")
                                st.rerun()

    # ── Tab 3: Active Student List ──
    with tab_list:
        st.markdown("#### 📋 Active Students")
        classes = _get_classes(tid)
        class_filter_opts = ["All Classes"] + [c["class_name"] for c in classes]
        sel_class = st.selectbox("Filter by Class", class_filter_opts, key="adm_class_filter")

        rows = _active_students(tid)
        if sel_class != "All Classes":
            rows = [r for r in rows if r["class_name"] == sel_class]

        if not rows:
            alert("No active students found for the selected filter.", "info")
        else:
            # Build display table
            data = []
            for r in rows:
                data.append({
                    "Roll": r["roll_no"] or "—",
                    "Name": r["name"],
                    "Father": r["father_name"] or "—",
                    "Class": r["class_name"],
                    "Session": r["session_name"],
                    "Fee (৳)": f"{r['monthly_fee']:,.0f}",
                    "Mobile": r["mobile_no"] or "—",
                })
            st.dataframe(data, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(data)} student(s)")

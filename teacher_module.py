"""
teacher_module.py — Teacher Management
Profiles, class/subject assignments, salary ledger, and performance overview.
"""

import streamlit as st
from datetime import date
from db import get_connection, fetchall, fetchone
from utils import page_header, kpi_row, alert, divider, get_tenant_id


# ──────────────────────────────────────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_teacher_tables():
    """Create teacher-specific tables if missing."""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id               SERIAL PRIMARY KEY,
                tenant_id        INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                name             TEXT NOT NULL,
                father_name      TEXT,
                mobile_no        TEXT,
                email            TEXT,
                nid_no           TEXT,
                designation      TEXT DEFAULT 'Teacher',
                joining_date     DATE,
                monthly_salary   NUMERIC(10,2) DEFAULT 0,
                qualification    TEXT,
                present_address  TEXT,
                status           TEXT DEFAULT 'active',
                photo_url        TEXT,
                created_at       TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS teacher_assignments (
                id          SERIAL PRIMARY KEY,
                tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                teacher_id  INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
                subject_id  INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
                session_id  INTEGER REFERENCES academic_sessions(id) ON DELETE SET NULL,
                is_class_teacher BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS teacher_salary (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                teacher_id      INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
                month_name      TEXT NOT NULL,
                year            INTEGER NOT NULL,
                basic_salary    NUMERIC(10,2) DEFAULT 0,
                bonus           NUMERIC(10,2) DEFAULT 0,
                deduction       NUMERIC(10,2) DEFAULT 0,
                net_salary      NUMERIC(10,2) GENERATED ALWAYS AS
                                    (basic_salary + bonus - deduction) STORED,
                payment_date    DATE,
                payment_method  TEXT DEFAULT 'cash',
                status          TEXT DEFAULT 'unpaid',
                remarks         TEXT,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(tenant_id, teacher_id, month_name, year)
            );
            """)
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def _get_teachers(tid):
    return fetchall(
        "SELECT * FROM teachers WHERE tenant_id=%s ORDER BY name", (tid,)
    )


def _teacher_kpis(tid):
    total  = fetchone("SELECT COUNT(*) AS n FROM teachers WHERE tenant_id=%s", (tid,))
    active = fetchone("SELECT COUNT(*) AS n FROM teachers WHERE tenant_id=%s AND status='active'", (tid,))
    sal    = fetchone(
        "SELECT COALESCE(SUM(monthly_salary),0) AS n FROM teachers WHERE tenant_id=%s AND status='active'",
        (tid,),
    )
    paid_this_month = fetchone(
        """SELECT COALESCE(SUM(net_salary),0) AS n FROM teacher_salary
           WHERE tenant_id=%s AND status='paid'
             AND EXTRACT(MONTH FROM payment_date)=EXTRACT(MONTH FROM CURRENT_DATE)
             AND EXTRACT(YEAR FROM payment_date)=EXTRACT(YEAR FROM CURRENT_DATE)""",
        (tid,),
    )
    return (
        int(total["n"]) if total else 0,
        int(active["n"]) if active else 0,
        float(sal["n"]) if sal else 0.0,
        float(paid_this_month["n"]) if paid_this_month else 0.0,
    )


def _create_teacher(tid, data):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO teachers
                   (tenant_id, name, father_name, mobile_no, email, nid_no,
                    designation, joining_date, monthly_salary, qualification,
                    present_address, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                   RETURNING id""",
                (tid, data["name"], data["father_name"], data["mobile"],
                 data["email"], data["nid"], data["designation"],
                 data["joining_date"], data["salary"],
                 data["qualification"], data["address"]),
            )
            tid_result = cur.fetchone()["id"]
        conn.commit()
        return True, tid_result
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _update_teacher_status(tid, teacher_id, status):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE teachers SET status=%s WHERE id=%s AND tenant_id=%s",
                (status, teacher_id, tid),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def _assign_class(tid, teacher_id, class_id, subject_id, session_id, is_class_teacher):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO teacher_assignments
                   (tenant_id, teacher_id, class_id, subject_id, session_id, is_class_teacher)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (tid, teacher_id, class_id, subject_id, session_id, is_class_teacher),
            )
        conn.commit()
        return True, None
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _get_assignments(tid, teacher_id):
    return fetchall(
        """SELECT ta.id, c.class_name, subj.subject_name,
                  sess.session_name, ta.is_class_teacher
           FROM teacher_assignments ta
           LEFT JOIN classes c ON c.id=ta.class_id
           LEFT JOIN subjects subj ON subj.id=ta.subject_id
           LEFT JOIN academic_sessions sess ON sess.id=ta.session_id
           WHERE ta.tenant_id=%s AND ta.teacher_id=%s
           ORDER BY ta.id DESC""",
        (tid, teacher_id),
    )


def _pay_salary(tid, teacher_id, month, year, basic, bonus, deduction, method, remarks):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO teacher_salary
                   (tenant_id, teacher_id, month_name, year, basic_salary,
                    bonus, deduction, payment_date, payment_method, status, remarks)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'paid',%s)
                   ON CONFLICT (tenant_id, teacher_id, month_name, year)
                   DO UPDATE SET basic_salary=%s, bonus=%s, deduction=%s,
                     payment_date=%s, payment_method=%s, status='paid', remarks=%s
                   RETURNING id""",
                (tid, teacher_id, month, year, basic, bonus, deduction,
                 date.today(), method, remarks,
                 basic, bonus, deduction, date.today(), method, remarks),
            )
        conn.commit()
        return True, None
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _salary_history(tid, teacher_id):
    return fetchall(
        """SELECT month_name, year, basic_salary, bonus, deduction,
                  net_salary, payment_date, status, payment_method
           FROM teacher_salary
           WHERE tenant_id=%s AND teacher_id=%s
           ORDER BY year DESC, id DESC""",
        (tid, teacher_id),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    _ensure_teacher_tables()
    page_header("👨‍🏫", "Teacher Management", "প্রোফাইল, ক্লাস অ্যাসাইনমেন্ট ও বেতন ব্যবস্থাপনা")

    total, active, monthly_bill, paid_this_month = _teacher_kpis(tid)
    kpi_row([
        {"label": "মোট শিক্ষক",       "value": total,               "cls": ""},
        {"label": "কর্মরত",           "value": active,              "cls": "success"},
        {"label": "মাসিক বেতন বিল",   "value": f"৳{monthly_bill:,.0f}", "cls": "accent"},
        {"label": "এ মাসে পরিশোধ",   "value": f"৳{paid_this_month:,.0f}", "cls": "success"},
    ])

    tab_list, tab_add, tab_assign, tab_salary = st.tabs([
        "📋 শিক্ষক তালিকা", "➕ নতুন শিক্ষক", "📚 ক্লাস অ্যাসাইনমেন্ট", "💰 বেতন"
    ])

    teachers = _get_teachers(tid)
    teacher_map = {t["name"]: t for t in teachers}

    # ── তালিকা ──
    with tab_list:
        if not teachers:
            alert("কোনো শিক্ষক নেই। নতুন শিক্ষক যোগ করুন।", "info")
        else:
            search = st.text_input("🔍 নাম বা মোবাইল দিয়ে খুঁজুন", key="tch_search")
            filtered = [
                t for t in teachers
                if not search or search.lower() in (t["name"] or "").lower()
                or search in (t["mobile_no"] or "")
            ]

            for t in filtered:
                status_icon = "🟢" if t["status"] == "active" else "🔴"
                with st.expander(f"{status_icon} **{t['name']}** — {t['designation']} | ৳{float(t['monthly_salary'] or 0):,.0f}/মাস"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.markdown(f"""
                        - **পিতার নাম:** {t['father_name'] or '—'}
                        - **মোবাইল:** {t['mobile_no'] or '—'}
                        - **ইমেইল:** {t['email'] or '—'}
                        - **NID:** {t['nid_no'] or '—'}
                        """)
                    with c2:
                        st.markdown(f"""
                        - **যোগদান:** {str(t['joining_date']) if t['joining_date'] else '—'}
                        - **যোগ্যতা:** {t['qualification'] or '—'}
                        - **ঠিকানা:** {t['present_address'] or '—'}
                        """)
                    with c3:
                        if t["status"] == "active":
                            if st.button("❌ নিষ্ক্রিয়", key=f"deact_{t['id']}"):
                                _update_teacher_status(tid, t["id"], "inactive")
                                st.rerun()
                        else:
                            if st.button("✅ সক্রিয়", key=f"act_{t['id']}"):
                                _update_teacher_status(tid, t["id"], "active")
                                st.rerun()

    # ── নতুন শিক্ষক ──
    with tab_add:
        st.markdown("#### ➕ নতুন শিক্ষক যোগ করুন")
        with st.form("teacher_form"):
            c1, c2 = st.columns(2)
            name        = c1.text_input("পূর্ণ নাম *", placeholder="মুহাম্মাদ আব্দুল্লাহ")
            father_name = c2.text_input("পিতার নাম")
            c3, c4 = st.columns(2)
            mobile = c3.text_input("মোবাইল", placeholder="01XXXXXXXXX")
            email  = c4.text_input("ইমেইল")
            c5, c6 = st.columns(2)
            designation = c5.selectbox("পদবী", ["Teacher", "Head Teacher", "Assistant Teacher",
                                                  "Hafiz", "Qari", "Mufti", "Other"])
            salary = c6.number_input("মাসিক বেতন (৳)", min_value=0, value=8000, step=500)
            c7, c8 = st.columns(2)
            joining_date = c7.date_input("যোগদানের তারিখ", value=date.today())
            nid          = c8.text_input("NID নম্বর")
            qualification = st.text_input("শিক্ষাগত যোগ্যতা", placeholder="দাওরায়ে হাদীস, ফাজিল ইত্যাদি")
            address = st.text_area("বর্তমান ঠিকানা", height=60)

            if st.form_submit_button("✅ শিক্ষক যোগ করুন", type="primary"):
                if not name.strip():
                    st.error("নাম আবশ্যক।")
                else:
                    ok, result = _create_teacher(tid, {
                        "name": name.strip(), "father_name": father_name.strip(),
                        "mobile": mobile.strip(), "email": email.strip(),
                        "nid": nid.strip(), "designation": designation,
                        "joining_date": str(joining_date), "salary": salary,
                        "qualification": qualification.strip(),
                        "address": address.strip(),
                    })
                    if ok:
                        st.success(f"✅ শিক্ষক যোগ হয়েছে! ID: {result}")
                        st.rerun()
                    else:
                        st.error(result)

    # ── ক্লাস অ্যাসাইনমেন্ট ──
    with tab_assign:
        st.markdown("#### 📚 শিক্ষককে ক্লাস ও বিষয় দিন")
        if not teachers:
            alert("প্রথমে শিক্ষক যোগ করুন।", "warning")
        else:
            sel_tch = st.selectbox("শিক্ষক নির্বাচন", list(teacher_map.keys()), key="asgn_tch")
            tch = teacher_map[sel_tch]

            sessions = fetchall(
                "SELECT id, session_name FROM academic_sessions WHERE tenant_id=%s ORDER BY id DESC", (tid,)
            )
            classes  = fetchall(
                "SELECT id, class_name FROM classes WHERE tenant_id=%s ORDER BY class_numeric", (tid,)
            )
            subjects = fetchall(
                "SELECT id, subject_name FROM subjects WHERE tenant_id=%s ORDER BY id", (tid,)
            )

            if sessions and classes:
                with st.form("assign_form"):
                    sess_map = {s["session_name"]: s["id"] for s in sessions}
                    cls_map  = {c["class_name"]: c["id"] for c in classes}
                    subj_map = {s["subject_name"]: s["id"] for s in subjects} if subjects else {}

                    c1, c2 = st.columns(2)
                    sel_sess = c1.selectbox("সেশন", list(sess_map.keys()))
                    sel_cls  = c2.selectbox("ক্লাস", list(cls_map.keys()))
                    sel_subj = st.selectbox("বিষয়", ["— বিষয় নির্বাচন করুন —"] + list(subj_map.keys()))
                    is_ct    = st.checkbox("ক্লাস টিচার হিসেবে নিয়োগ করুন")

                    if st.form_submit_button("✅ অ্যাসাইন করুন", type="primary"):
                        subj_id = subj_map.get(sel_subj) if sel_subj != "— বিষয় নির্বাচন করুন —" else None
                        ok, err = _assign_class(
                            tid, tch["id"], cls_map[sel_cls], subj_id,
                            sess_map[sel_sess], is_ct
                        )
                        if ok:
                            st.success("অ্যাসাইনমেন্ট সম্পন্ন!")
                            st.rerun()
                        else:
                            st.error(err)

            divider()
            st.markdown(f"**{sel_tch}-এর বর্তমান অ্যাসাইনমেন্ট**")
            assignments = _get_assignments(tid, tch["id"])
            if assignments:
                rows = [
                    {
                        "ক্লাস":    a["class_name"] or "—",
                        "বিষয়":    a["subject_name"] or "—",
                        "সেশন":    a["session_name"] or "—",
                        "ক্লাস টিচার": "✅" if a["is_class_teacher"] else "—",
                    }
                    for a in assignments
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                alert("কোনো অ্যাসাইনমেন্ট নেই।", "info")

    # ── বেতন ──
    with tab_salary:
        st.markdown("#### 💰 বেতন প্রদান")
        if not teachers:
            alert("প্রথমে শিক্ষক যোগ করুন।", "warning")
        else:
            active_teachers = [t for t in teachers if t["status"] == "active"]
            if not active_teachers:
                alert("কোনো সক্রিয় শিক্ষক নেই।", "warning")
            else:
                sal_map = {t["name"]: t for t in active_teachers}
                sel_sal = st.selectbox("শিক্ষক", list(sal_map.keys()), key="sal_tch")
                tch2    = sal_map[sel_sal]

                with st.form("salary_form"):
                    from utils import months_list, current_year
                    c1, c2 = st.columns(2)
                    month = c1.selectbox("মাস", months_list())
                    year  = c2.number_input("বছর", min_value=2020, max_value=2040,
                                             value=current_year())
                    c3, c4, c5 = st.columns(3)
                    basic     = c3.number_input("মূল বেতন", min_value=0,
                                                 value=int(tch2["monthly_salary"] or 0), step=500)
                    bonus     = c4.number_input("বোনাস", min_value=0, value=0, step=100)
                    deduction = c5.number_input("কর্তন", min_value=0, value=0, step=100)

                    net = basic + bonus - deduction
                    st.markdown(f"**নেট বেতন: ৳{net:,.0f}**")

                    method  = st.selectbox("পেমেন্ট পদ্ধতি", ["Cash", "bKash", "Nagad", "Bank"])
                    remarks = st.text_input("মন্তব্য")

                    if st.form_submit_button("✅ বেতন পরিশোধ করুন", type="primary"):
                        ok, err = _pay_salary(
                            tid, tch2["id"], month, int(year),
                            basic, bonus, deduction, method.lower(), remarks
                        )
                        if ok:
                            st.success(f"✅ {sel_sal}-এর {month} {int(year)} বেতন পরিশোধ!")
                            st.rerun()
                        else:
                            st.error(err)

                divider()
                st.markdown(f"**{sel_sal}-এর বেতনের ইতিহাস**")
                hist = _salary_history(tid, tch2["id"])
                if hist:
                    rows = [
                        {
                            "মাস":      f"{r['month_name']} {r['year']}",
                            "মূল":      f"৳{float(r['basic_salary'] or 0):,.0f}",
                            "বোনাস":   f"৳{float(r['bonus'] or 0):,.0f}",
                            "কর্তন":   f"৳{float(r['deduction'] or 0):,.0f}",
                            "নেট":     f"৳{float(r['net_salary'] or 0):,.0f}",
                            "পরিশোধ":  str(r["payment_date"]) if r["payment_date"] else "—",
                            "অবস্থা":  "✅ পরিশোধিত" if r["status"] == "paid" else "⏳ বাকি",
                        }
                        for r in hist
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                    total_paid = sum(float(r["net_salary"] or 0) for r in hist if r["status"] == "paid")
                    st.caption(f"মোট পরিশোধিত: ৳{total_paid:,.0f}")
                else:
                    alert("কোনো বেতন রেকর্ড নেই।", "info")

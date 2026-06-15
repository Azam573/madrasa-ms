"""
attendance_module.py — Daily roll call, bulk attendance entry,
monthly summary and leave management for Smart Madrasa ERP.
"""

import streamlit as st
from datetime import date, timedelta
from db import get_connection, fetchall, fetchone
from utils import (
    page_header, kpi_row, alert, divider, get_tenant_id,
)


# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
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


def _get_enrolled_students(tid, session_id, class_id):
    return fetchall(
        """SELECT s.id AS student_id, s.name, e.roll_no, e.id AS enrollment_id
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           WHERE s.tenant_id=%s AND e.session_id=%s AND e.class_id=%s
             AND e.enrollment_status='active' AND s.status='active'
           ORDER BY e.roll_no NULLS LAST, s.name""",
        (tid, session_id, class_id),
    )


def _get_attendance_for_date(tid, date_str, class_id, session_id):
    """Returns dict: enrollment_id → status"""
    rows = fetchall(
        """SELECT a.enrollment_id, a.status
           FROM attendance a
           JOIN student_enrollments e ON e.id=a.enrollment_id
           WHERE a.tenant_id=%s AND a.date=%s AND e.class_id=%s AND e.session_id=%s""",
        (tid, date_str, class_id, session_id),
    )
    return {r["enrollment_id"]: r["status"] for r in rows}


def _monthly_attendance_summary(tid, class_id, session_id, year, month):
    return fetchall(
        """SELECT s.name, e.roll_no, e.id AS enrollment_id,
                  COUNT(CASE WHEN a.status='present' THEN 1 END) AS present,
                  COUNT(CASE WHEN a.status='absent'  THEN 1 END) AS absent,
                  COUNT(CASE WHEN a.status='late'    THEN 1 END) AS late,
                  COUNT(a.id) AS total_marked
           FROM student_enrollments e
           JOIN students s ON s.id=e.student_id
           LEFT JOIN attendance a ON a.enrollment_id=e.id
             AND a.tenant_id=e.tenant_id
             AND EXTRACT(YEAR FROM a.date)=%s
             AND EXTRACT(MONTH FROM a.date)=%s
           WHERE e.tenant_id=%s AND e.class_id=%s AND e.session_id=%s
             AND e.enrollment_status='active' AND s.status='active'
           GROUP BY s.name, e.roll_no, e.id
           ORDER BY e.roll_no NULLS LAST, s.name""",
        (year, month, tid, class_id, session_id),
    )


def _class_daily_attendance_dates(tid, class_id, session_id):
    """All dates attendance was taken for a class."""
    rows = fetchall(
        """SELECT DISTINCT a.date FROM attendance a
           JOIN student_enrollments e ON e.id=a.enrollment_id
           WHERE a.tenant_id=%s AND e.class_id=%s AND e.session_id=%s
           ORDER BY a.date DESC LIMIT 30""",
        (tid, class_id, session_id),
    )
    return [r["date"] for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# DB write — bulk save attendance (atomic)
# ──────────────────────────────────────────────────────────────────────────────

def _save_attendance_bulk(tid, date_str, records: list[dict]):
    """
    records = [{"enrollment_id": int, "status": str}, ...]
    Uses INSERT ... ON CONFLICT DO UPDATE for idempotency.
    """
    conn = get_connection()
    if not conn:
        return False, "DB connection failed."
    try:
        with conn.cursor() as cur:
            for rec in records:
                cur.execute(
                    """INSERT INTO attendance (tenant_id, enrollment_id, date, status)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (enrollment_id, date)
                       DO UPDATE SET status=EXCLUDED.status""",
                    (tid, rec["enrollment_id"], date_str, rec["status"]),
                )
        conn.commit()
        return True, len(records)
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Heatmap HTML (30-day attendance calendar strip)
# ──────────────────────────────────────────────────────────────────────────────

def _attendance_heatmap_html(present, absent, late, total):
    pct = round(present / total * 100, 1) if total else 0
    color = "#2E7D32" if pct >= 75 else ("#F57F17" if pct >= 50 else "#C62828")
    bar_w = max(0, min(100, pct))
    return f"""
    <div style="background:#F7F9FA;border:1px solid #DDE3E7;border-radius:10px;padding:1rem;margin-bottom:0.5rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
        <span style="font-weight:600;color:#1A2332">Attendance Rate</span>
        <span style="font-size:1.5rem;font-weight:700;color:{color}">{pct}%</span>
      </div>
      <div style="background:#DDE3E7;border-radius:20px;height:10px;overflow:hidden">
        <div style="background:{color};height:100%;width:{bar_w}%;border-radius:20px;transition:width 0.5s"></div>
      </div>
      <div style="display:flex;gap:1.5rem;margin-top:0.75rem;font-size:0.8rem">
        <span>🟢 Present: <strong>{present}</strong></span>
        <span>🔴 Absent: <strong>{absent}</strong></span>
        <span>🟡 Late: <strong>{late}</strong></span>
        <span>📅 Marked: <strong>{total}</strong></span>
      </div>
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Main render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    page_header("📅", "Attendance Management", "Daily roll call and monthly tracking")

    sessions = _get_sessions(tid)
    classes  = _get_classes(tid)

    if not sessions:
        alert("No academic session found. Create one in Settings.", "warning")
        return
    if not classes:
        alert("No classes found. Create classes in Settings.", "warning")
        return

    sess_map  = {s["session_name"]: s["id"] for s in sessions}
    class_map = {c["class_name"]: c["id"] for c in classes}

    # ── Global filters (top bar — 1 click) ──
    cf1, cf2, cf3 = st.columns(3)
    sel_sess  = cf1.selectbox("Session",  list(sess_map.keys()), key="att_sess")
    sel_class = cf2.selectbox("Class",    list(class_map.keys()), key="att_class")
    att_date  = cf3.date_input("Date",    value=date.today(), key="att_date")

    session_id = sess_map[sel_sess]
    class_id   = class_map[sel_class]
    students   = _get_enrolled_students(tid, session_id, class_id)

    # Quick KPIs
    today_str = str(att_date)
    today_att = _get_attendance_for_date(tid, today_str, class_id, session_id)
    present_today = sum(1 for v in today_att.values() if v == "present")
    absent_today  = sum(1 for v in today_att.values() if v == "absent")
    late_today    = sum(1 for v in today_att.values() if v == "late")
    not_marked    = len(students) - len(today_att)

    kpi_row([
        {"label": "Total Students", "value": len(students),    "cls": ""},
        {"label": "Present",        "value": present_today,    "cls": "success"},
        {"label": "Absent",         "value": absent_today,     "cls": "danger"},
        {"label": "Late",           "value": late_today,       "cls": "warning"},
        {"label": "Not Marked",     "value": not_marked,       "cls": ""},
    ])

    tab_roll, tab_monthly, tab_student = st.tabs([
        "📋 Daily Roll Call", "📊 Monthly Summary", "👤 Student Report"
    ])

    # ── Tab 1: Daily Roll Call ──
    with tab_roll:
        st.markdown(f"#### 📋 Attendance for **{sel_class}** — {att_date.strftime('%d %B %Y')}")

        if not students:
            alert("No active students in this class/session.", "info")
        else:
            STATUS_OPTIONS = ["present", "absent", "late", "holiday"]
            STATUS_EMOJI   = {"present": "🟢", "absent": "🔴", "late": "🟡", "holiday": "⚪"}

            # Build form with per-student status selector
            with st.form("roll_call_form"):
                records = []
                # Header row
                hc1, hc2, hc3 = st.columns([1, 3, 2])
                hc1.markdown("**Roll**")
                hc2.markdown("**Student Name**")
                hc3.markdown("**Status**")
                st.markdown("<hr style='margin:0.25rem 0'>", unsafe_allow_html=True)

                for stu in students:
                    existing = today_att.get(stu["enrollment_id"], "present")
                    c1, c2, c3 = st.columns([1, 3, 2])
                    c1.markdown(f"`{stu['roll_no'] or '—'}`")
                    c2.markdown(stu["name"])
                    status = c3.selectbox(
                        "Status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(existing),
                        key=f"att_{stu['enrollment_id']}",
                        label_visibility="collapsed",
                    )
                    records.append({"enrollment_id": stu["enrollment_id"], "status": status})

                submitted = st.form_submit_button("💾 Save Attendance", type="primary")
                if submitted:
                    ok, result = _save_attendance_bulk(tid, today_str, records)
                    if ok:
                        st.success(f"✅ Attendance saved for {result} students!")
                        st.rerun()
                    else:
                        st.error(f"Failed: {result}")

            # Bulk quick-set buttons (outside form)
            divider()
            st.markdown("**⚡ Quick Set All**")
            qc1, qc2, qc3 = st.columns(3)
            if qc1.button("🟢 Mark All Present", use_container_width=True):
                bulk = [{"enrollment_id": s["enrollment_id"], "status": "present"} for s in students]
                ok, r = _save_attendance_bulk(tid, today_str, bulk)
                if ok:
                    st.success("All marked present!")
                    st.rerun()
            if qc2.button("⚪ Mark Holiday", use_container_width=True):
                bulk = [{"enrollment_id": s["enrollment_id"], "status": "holiday"} for s in students]
                ok, r = _save_attendance_bulk(tid, today_str, bulk)
                if ok:
                    st.success("Marked as holiday.")
                    st.rerun()
            if qc3.button("🔴 Mark All Absent", use_container_width=True):
                bulk = [{"enrollment_id": s["enrollment_id"], "status": "absent"} for s in students]
                ok, r = _save_attendance_bulk(tid, today_str, bulk)
                if ok:
                    st.warning("All marked absent.")
                    st.rerun()

            # Recent attendance dates
            divider()
            recent_dates = _class_daily_attendance_dates(tid, class_id, session_id)
            if recent_dates:
                st.markdown("**📅 Recently Marked Dates**")
                st.markdown(", ".join([str(d) for d in recent_dates[:10]]))

    # ── Tab 2: Monthly Summary ──
    with tab_monthly:
        st.markdown("#### 📊 Monthly Attendance Report")
        mc1, mc2 = st.columns(2)
        sel_year  = mc1.number_input("Year",  min_value=2020, max_value=2040,
                                      value=date.today().year, key="att_yr")
        sel_month = mc2.selectbox("Month",
                                   list(range(1, 13)),
                                   index=date.today().month - 1,
                                   format_func=lambda m: date(2000, m, 1).strftime("%B"),
                                   key="att_month")

        if st.button("🔄 Generate Report", type="primary", key="gen_monthly"):
            summary = _monthly_attendance_summary(
                tid, class_id, session_id, int(sel_year), int(sel_month)
            )
            if not summary:
                alert("No attendance data for selected period.", "info")
            else:
                import pandas as pd
                # Aggregate KPIs
                total_present = sum(int(r["present"] or 0) for r in summary)
                total_absent  = sum(int(r["absent"]  or 0) for r in summary)
                total_late    = sum(int(r["late"]    or 0) for r in summary)
                total_days    = sum(int(r["total_marked"] or 0) for r in summary)

                kpi_row([
                    {"label": "Total Present Records", "value": total_present, "cls": "success"},
                    {"label": "Total Absent Records",  "value": total_absent,  "cls": "danger"},
                    {"label": "Late Records",          "value": total_late,    "cls": "warning"},
                ])

                rows = []
                for r in summary:
                    total_m = int(r["total_marked"] or 0)
                    pres_m  = int(r["present"] or 0)
                    pct     = round(pres_m / total_m * 100, 1) if total_m else 0
                    rows.append({
                        "Roll":      r["roll_no"] or "—",
                        "Name":      r["name"],
                        "Present":   pres_m,
                        "Absent":    int(r["absent"] or 0),
                        "Late":      int(r["late"] or 0),
                        "Days Marked": total_m,
                        "Rate %":    f"{pct}%",
                        "Status":    "✅ Good" if pct >= 75 else ("⚠️ Low" if pct >= 50 else "❌ Critical"),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)

                # Chart: top/bottom attendance
                df = pd.DataFrame(rows)
                df["Rate"] = df["Rate %"].str.replace("%", "").astype(float)
                st.markdown("**Attendance Rate Distribution**")
                st.bar_chart(
                    df.set_index("Name")[["Rate"]],
                    height=280, color="#0F4C5C"
                )

    # ── Tab 3: Student-level Report ──
    with tab_student:
        st.markdown("#### 👤 Individual Student Attendance")
        if not students:
            alert("No students in this class/session.", "info")
        else:
            stu_map = {f"Roll {s['roll_no'] or '?'} — {s['name']}": s for s in students}
            sel_stu = st.selectbox("Select Student", list(stu_map.keys()), key="att_stu")
            stu = stu_map[sel_stu]

            # Full attendance log
            logs = fetchall(
                """SELECT date, status FROM attendance
                   WHERE tenant_id=%s AND enrollment_id=%s
                   ORDER BY date DESC LIMIT 90""",
                (tid, stu["enrollment_id"]),
            )

            if not logs:
                alert("No attendance records for this student.", "info")
            else:
                total = len(logs)
                present = sum(1 for l in logs if l["status"] == "present")
                absent  = sum(1 for l in logs if l["status"] == "absent")
                late    = sum(1 for l in logs if l["status"] == "late")

                st.markdown(
                    _attendance_heatmap_html(present, absent, late, total),
                    unsafe_allow_html=True,
                )

                import pandas as pd
                df = pd.DataFrame([
                    {
                        "Date":   str(l["date"]),
                        "Day":    l["date"].strftime("%A"),
                        "Status": l["status"].title(),
                        "Icon":   {"present": "🟢", "absent": "🔴",
                                   "late": "🟡", "holiday": "⚪"}.get(l["status"], "—"),
                    }
                    for l in logs
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)

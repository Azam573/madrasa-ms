"""
student_portal.py — Next-Gen Student/Parent Portal.
Shows payment history, academic progress charts, and due alerts.
Self-contained UI with minimal inputs (3-Click Rule).
"""

import streamlit as st
from db import fetchall, fetchone
from utils import (
    page_header, kpi_row, alert, divider, badge,
    get_tenant_id, get_grade, PALETTE,
)

# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _search_student(tid, query: str):
    q = f"%{query}%"
    return fetchall(
        """SELECT s.id, s.name, s.father_name, s.mobile_no, s.status,
                  e.roll_no, e.monthly_fee, e.enrollment_id,
                  c.class_name, sess.session_name, e.id AS enrollment_id
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND s.status='active'
             AND (s.name ILIKE %s OR s.mobile_no ILIKE %s OR CAST(e.roll_no AS TEXT) ILIKE %s)
           ORDER BY c.class_numeric, e.roll_no
           LIMIT 10""",
        (tid, q, q, q),
    )


def _get_student_by_id(tid, student_id):
    return fetchone(
        """SELECT s.id, s.name, s.father_name, s.mother_name, s.mobile_no,
                  s.date_of_birth, s.gender, s.blood_group, s.present_address,
                  s.status, s.created_at,
                  e.roll_no, e.monthly_fee, e.enrollment_status, e.enrolled_at,
                  e.id AS enrollment_id, e.session_id,
                  c.class_name, c.id AS class_id, sess.session_name
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND s.id=%s AND s.status='active'
           LIMIT 1""",
        (tid, student_id),
    )


def _payment_history(tid, student_id):
    return fetchall(
        """SELECT v.voucher_no, v.month_name, v.year, v.amount,
                  v.fund_type, v.status, v.due_date, v.paid_at,
                  p.amount_paid, p.payment_method, p.receipt_no, p.payment_date
           FROM fee_vouchers v
           LEFT JOIN fee_payments p ON p.voucher_id=v.id AND p.tenant_id=v.tenant_id
           WHERE v.tenant_id=%s AND v.student_id=%s
           ORDER BY v.year DESC, v.id DESC""",
        (tid, student_id),
    )


def _due_vouchers(tid, student_id):
    return fetchall(
        """SELECT voucher_no, month_name, year, amount, fund_type, due_date, status
           FROM fee_vouchers
           WHERE tenant_id=%s AND student_id=%s AND status IN ('unpaid','partial')
           ORDER BY year, id""",
        (tid, student_id),
    )


def _academic_progress(tid, enrollment_id):
    """Returns per-exam aggregate marks for chart."""
    return fetchall(
        """SELECT ex.exam_name,
                  SUM(sm.total_obtained) AS obtained,
                  SUM(subj.full_marks)   AS full_marks,
                  ROUND(SUM(sm.total_obtained)::numeric / NULLIF(SUM(subj.full_marks),0) * 100, 1) AS pct
           FROM student_marks sm
           JOIN exams ex ON ex.id=sm.exam_id
           JOIN subjects subj ON subj.id=sm.subject_id
           WHERE sm.tenant_id=%s AND sm.enrollment_id=%s
           GROUP BY ex.id, ex.exam_name, ex.exam_date
           ORDER BY ex.exam_date""",
        (tid, enrollment_id),
    )


def _subject_performance(tid, enrollment_id):
    """Latest marks per subject across all exams."""
    return fetchall(
        """SELECT subj.subject_name,
                  MAX(sm.total_obtained) AS best,
                  MIN(sm.total_obtained) AS worst,
                  ROUND(AVG(sm.total_obtained)::numeric,1) AS avg,
                  subj.full_marks
           FROM student_marks sm
           JOIN subjects subj ON subj.id=sm.subject_id
           WHERE sm.tenant_id=%s AND sm.enrollment_id=%s AND sm.is_absent=FALSE
           GROUP BY subj.id, subj.subject_name, subj.full_marks
           ORDER BY subj.id""",
        (tid, enrollment_id),
    )


def _fee_trend(tid, student_id):
    """Monthly paid amounts for bar chart."""
    rows = fetchall(
        """SELECT month_name, year, SUM(amount) AS amount
           FROM fee_vouchers
           WHERE tenant_id=%s AND student_id=%s AND status='paid'
           GROUP BY month_name, year
           ORDER BY year, MIN(id)""",
        (tid, student_id),
    )
    return rows


def _attendance_summary(tid, enrollment_id):
    total   = fetchone("SELECT COUNT(*) AS n FROM attendance WHERE tenant_id=%s AND enrollment_id=%s",
                       (tid, enrollment_id))
    present = fetchone("SELECT COUNT(*) AS n FROM attendance WHERE tenant_id=%s AND enrollment_id=%s AND status='present'",
                       (tid, enrollment_id))
    absent  = fetchone("SELECT COUNT(*) AS n FROM attendance WHERE tenant_id=%s AND enrollment_id=%s AND status='absent'",
                       (tid, enrollment_id))
    total_n   = int(total["n"])   if total else 0
    present_n = int(present["n"]) if present else 0
    absent_n  = int(absent["n"])  if absent else 0
    pct = round(present_n / total_n * 100, 1) if total_n else 0
    return total_n, present_n, absent_n, pct


# ──────────────────────────────────────────────────────────────────────────────
# Profile card HTML
# ──────────────────────────────────────────────────────────────────────────────

def _profile_card_html(stu):
    status_color = "#2E7D32" if stu["status"] == "active" else "#C62828"
    return f"""
    <div style="background:#0F4C5C;border-radius:12px;padding:1.25rem 1.5rem;color:white;margin-bottom:1rem">
      <div style="display:flex;align-items:center;gap:1rem">
        <div style="width:56px;height:56px;background:rgba(255,255,255,0.15);border-radius:50%;
                    display:flex;align-items:center;justify-content:center;font-size:1.6rem">
          👤
        </div>
        <div style="flex:1">
          <div style="font-size:1.15rem;font-weight:700">{stu['name']}</div>
          <div style="font-size:0.82rem;opacity:0.8">Father: {stu['father_name'] or '—'}</div>
          <div style="font-size:0.82rem;opacity:0.8">{stu['class_name']} · {stu['session_name']}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:1.5rem;font-weight:700">#{stu['roll_no'] or '—'}</div>
          <div style="font-size:0.75rem;opacity:0.7">Roll No</div>
          <div style="margin-top:0.3rem;background:rgba(255,255,255,0.15);
                      padding:0.2rem 0.7rem;border-radius:20px;font-size:0.75rem;font-weight:600">
            {stu['status'].upper()}
          </div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-top:1rem;
                  padding-top:1rem;border-top:1px solid rgba(255,255,255,0.15)">
        <div style="text-align:center">
          <div style="font-weight:600">৳{stu['monthly_fee']:,.0f}</div>
          <div style="font-size:0.7rem;opacity:0.7">Monthly Fee</div>
        </div>
        <div style="text-align:center">
          <div style="font-weight:600">{stu['mobile_no'] or '—'}</div>
          <div style="font-size:0.7rem;opacity:0.7">Mobile</div>
        </div>
        <div style="text-align:center">
          <div style="font-weight:600">{str(stu['enrolled_at'])[:10]}</div>
          <div style="font-size:0.7rem;opacity:0.7">Enrolled</div>
        </div>
      </div>
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Main render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    page_header("🏫", "Student Portal", "View fees, results and academic progress")

    # ── Student search / selection ──
    if "portal_student_id" not in st.session_state:
        st.session_state.portal_student_id = None

    col_search, col_clear = st.columns([4, 1])
    with col_search:
        query = st.text_input(
            "🔍 Search by Name, Mobile or Roll No",
            placeholder="Type at least 2 characters…",
            key="portal_search"
        )
    with col_clear:
        st.markdown("<div style='margin-top:1.7rem'>", unsafe_allow_html=True)
        if st.button("✖ Clear", key="portal_clear"):
            st.session_state.portal_student_id = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Search results
    if query and len(query) >= 2 and not st.session_state.portal_student_id:
        results = _search_student(tid, query)
        if results:
            st.markdown("**Search Results:**")
            for r in results:
                btn_label = f"**{r['name']}** — {r['class_name']} | Roll: {r['roll_no'] or '—'} | {r['session_name']}"
                if st.button(btn_label, key=f"sel_{r['id']}"):
                    st.session_state.portal_student_id = r["id"]
                    st.rerun()
        else:
            alert("No active student found matching your search.", "warning")
        return

    if not st.session_state.portal_student_id:
        alert("Search for a student above to view their portal.", "info")
        return

    # ── Student found — load full profile ──
    stu = _get_student_by_id(tid, st.session_state.portal_student_id)
    if not stu:
        alert("Student not found or not active.", "danger")
        st.session_state.portal_student_id = None
        return

    st.markdown(_profile_card_html(stu), unsafe_allow_html=True)

    # ── Due alerts (shown prominently) ──
    dues = _due_vouchers(tid, stu["id"])
    if dues:
        total_due = sum(float(d["amount"]) for d in dues)
        st.markdown(
            f'<div class="alert alert-danger">⚠️ <strong>Fee Alert:</strong> '
            f'{len(dues)} unpaid voucher(s) totalling <strong>৳{total_due:,.0f}</strong>. '
            f'Please pay before the due date to avoid penalties.</div>',
            unsafe_allow_html=True,
        )

    # ── Main content tabs ──
    tab_fees, tab_academic, tab_attendance, tab_profile = st.tabs([
        "💳 Fee History", "📊 Academic Progress", "📅 Attendance", "👤 Profile"
    ])

    # ── Tab 1: Fee History ──
    with tab_fees:
        # Due alerts table
        if dues:
            st.markdown("#### ⚠️ Pending Dues")
            due_rows = []
            for d in dues:
                due_rows.append({
                    "Voucher": d["voucher_no"],
                    "Month": f"{d['month_name']} {d['year']}",
                    "Fund": d["fund_type"].replace("_", " ").title(),
                    "Amount": f"৳{float(d['amount']):,.0f}",
                    "Due Date": str(d["due_date"]) if d["due_date"] else "—",
                    "Status": d["status"].upper(),
                })
            st.dataframe(due_rows, use_container_width=True, hide_index=True)
            divider()

        # Full payment history
        st.markdown("#### 📜 Complete Payment History")
        payments = _payment_history(tid, stu["id"])
        if not payments:
            alert("No payment records found.", "info")
        else:
            paid_total   = sum(float(p["amount_paid"] or 0) for p in payments if p["status"] == "paid")
            billed_total = sum(float(p["amount"]) for p in payments)
            kpi_row([
                {"label": "Total Billed",   "value": f"৳{billed_total:,.0f}", "cls": ""},
                {"label": "Total Paid",     "value": f"৳{paid_total:,.0f}",   "cls": "success"},
                {"label": "Outstanding",    "value": f"৳{billed_total - paid_total:,.0f}", "cls": "danger"},
                {"label": "Vouchers",       "value": len(payments), "cls": ""},
            ])

            rows = []
            for p in payments:
                rows.append({
                    "Voucher": p["voucher_no"],
                    "Month": f"{p['month_name']} {p['year']}",
                    "Fund": p["fund_type"].replace("_", " ").title(),
                    "Amount": f"৳{float(p['amount']):,.0f}",
                    "Status": p["status"].upper(),
                    "Paid On": str(p["payment_date"]) if p["payment_date"] else "—",
                    "Method": (p["payment_method"] or "—").title(),
                    "Receipt": p["receipt_no"] or "—",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

            # Fee trend chart
            divider()
            st.markdown("**📈 Monthly Payment Trend**")
            trend = _fee_trend(tid, stu["id"])
            if trend:
                import pandas as pd
                df = pd.DataFrame([
                    {"Period": f"{r['month_name'][:3]} {r['year']}", "Amount (৳)": float(r["amount"])}
                    for r in trend
                ])
                st.bar_chart(df.set_index("Period"), color=PALETTE["success"], height=240)

    # ── Tab 2: Academic Progress ──
    with tab_academic:
        progress = _academic_progress(tid, stu["enrollment_id"])
        subj_perf = _subject_performance(tid, stu["enrollment_id"])

        if not progress:
            alert("No exam results available yet.", "info")
        else:
            st.markdown("#### 📊 Exam-wise Performance")
            kpi_data = []
            for p in progress:
                grade, gpa = get_grade(float(p["pct"] or 0))
                kpi_data.append({
                    "label": p["exam_name"],
                    "value": f"{p['pct']}%",
                    "cls": "success" if float(p["pct"] or 0) >= 50 else "danger",
                })
            kpi_row(kpi_data)

            # Progress line chart
            import pandas as pd
            df = pd.DataFrame([
                {"Exam": p["exam_name"], "Percentage (%)": float(p["pct"] or 0)}
                for p in progress
            ])
            st.line_chart(df.set_index("Exam"), color=PALETTE["primary"], height=260)

            # Detailed table
            st.markdown("**Detailed Result Summary**")
            result_rows = []
            for p in progress:
                pct = float(p["pct"] or 0)
                grade, gpa = get_grade(pct)
                result_rows.append({
                    "Exam": p["exam_name"],
                    "Obtained": p["obtained"],
                    "Full Marks": p["full_marks"],
                    "Percentage": f"{pct:.1f}%",
                    "Grade": grade,
                    "GPA": f"{gpa:.2f}",
                })
            st.dataframe(result_rows, use_container_width=True, hide_index=True)

        if subj_perf:
            divider()
            st.markdown("#### 📚 Subject-wise Average Performance")
            import pandas as pd
            sdf = pd.DataFrame([
                {
                    "Subject": s["subject_name"],
                    "Avg": float(s["avg"] or 0),
                    "Best": int(s["best"] or 0),
                    "Worst": int(s["worst"] or 0),
                    "Full": int(s["full_marks"]),
                    "Avg %": round(float(s["avg"] or 0) / int(s["full_marks"]) * 100, 1),
                }
                for s in subj_perf
            ])
            st.dataframe(sdf, use_container_width=True, hide_index=True)
            st.bar_chart(sdf.set_index("Subject")[["Avg %"]], color=PALETTE["accent"], height=240)

    # ── Tab 3: Attendance ──
    with tab_attendance:
        total, present, absent, pct = _attendance_summary(tid, stu["enrollment_id"])
        kpi_row([
            {"label": "Total Days",  "value": total,   "cls": ""},
            {"label": "Present",     "value": present, "cls": "success"},
            {"label": "Absent",      "value": absent,  "cls": "danger"},
            {"label": "Attendance %","value": f"{pct}%",
             "cls": "success" if pct >= 75 else "danger"},
        ])
        if pct < 75 and total > 0:
            alert("⚠️ Attendance below 75%. This may affect exam eligibility.", "warning")

        daily = fetchall(
            """SELECT date, status FROM attendance
               WHERE tenant_id=%s AND enrollment_id=%s
               ORDER BY date DESC LIMIT 60""",
            (tid, stu["enrollment_id"]),
        )
        if daily:
            import pandas as pd
            adf = pd.DataFrame([
                {"Date": str(r["date"]), "Status": r["status"].title()}
                for r in daily
            ])
            st.dataframe(adf, use_container_width=True, hide_index=True)
        else:
            alert("No attendance records found.", "info")

    # ── Tab 4: Profile ──
    with tab_profile:
        st.markdown("#### 👤 Student Profile Details")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            **Personal Information**

            | Field | Value |
            |---|---|
            | Full Name | {stu['name']} |
            | Father's Name | {stu['father_name'] or '—'} |
            | Mother's Name | {stu.get('mother_name') or '—'} |
            | Mobile | {stu['mobile_no'] or '—'} |
            | Date of Birth | {str(stu['date_of_birth']) if stu.get('date_of_birth') else '—'} |
            | Gender | {stu['gender'] or '—'} |
            | Blood Group | {stu.get('blood_group') or '—'} |
            | Address | {stu['present_address'] or '—'} |
            """)
        with c2:
            st.markdown(f"""
            **Enrollment Information**

            | Field | Value |
            |---|---|
            | Class | {stu['class_name']} |
            | Session | {stu['session_name']} |
            | Roll No | {stu['roll_no'] or 'Not assigned'} |
            | Monthly Fee | ৳{stu['monthly_fee']:,.0f} |
            | Status | {stu['status'].title()} |
            | Enrolled On | {str(stu['enrolled_at'])[:10]} |
            | Student ID | #{stu['id']} |
            """)

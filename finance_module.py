"""
finance_module.py — Fee collection, digital voucher generation,
and Multi-Fund Ledgers (General, Zakat, Lillah Boarding).
"""

import streamlit as st
from datetime import date, datetime
from db import get_connection, fetchall, fetchone
from utils import (
    page_header, kpi_row, badge, alert, divider,
    get_tenant_id, months_list, current_year,
)

# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _active_students(tid):
    return fetchall(
        """SELECT s.id, s.name, s.father_name, s.mobile_no,
                  e.id AS enrollment_id, e.roll_no, e.monthly_fee,
                  c.class_name, sess.session_name, sess.id AS session_id
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND s.status='active' AND e.enrollment_status='active'
           ORDER BY c.class_numeric, e.roll_no""",
        (tid,),
    )


def _vouchers_for_student(tid, student_id):
    return fetchall(
        """SELECT v.id, v.voucher_no, v.month_name, v.year, v.amount,
                  v.fund_type, v.status, v.issue_date, v.due_date, v.paid_at,
                  v.remarks
           FROM fee_vouchers v
           WHERE v.tenant_id=%s AND v.student_id=%s
           ORDER BY v.year DESC, v.id DESC""",
        (tid, student_id),
    )


def _ledger_summary(tid, fund_type=None, year=None):
    params = [tid]
    clauses = ["tenant_id=%s"]
    if fund_type and fund_type != "All":
        clauses.append("fund_type=%s")
        params.append(fund_type.lower().replace(" ", "_"))
    if year:
        clauses.append("year=%s")
        params.append(year)
    where = " AND ".join(clauses)

    total_billed = fetchone(
        f"SELECT COALESCE(SUM(amount),0) AS n FROM fee_vouchers WHERE {where}", tuple(params)
    )
    paid = fetchone(
        f"SELECT COALESCE(SUM(amount),0) AS n FROM fee_vouchers WHERE {where} AND status='paid'", tuple(params)
    )
    unpaid = fetchone(
        f"SELECT COALESCE(SUM(amount),0) AS n FROM fee_vouchers WHERE {where} AND status='unpaid'", tuple(params)
    )
    partial = fetchone(
        f"SELECT COALESCE(SUM(amount),0) AS n FROM fee_vouchers WHERE {where} AND status='partial'", tuple(params)
    )
    count = fetchone(
        f"SELECT COUNT(*) AS n FROM fee_vouchers WHERE {where}", tuple(params)
    )
    return {
        "billed":  float(total_billed["n"]),
        "paid":    float(paid["n"]),
        "unpaid":  float(unpaid["n"]),
        "partial": float(partial["n"]),
        "count":   int(count["n"]),
    }


def _recent_payments(tid, limit=20):
    return fetchall(
        """SELECT p.id, p.amount_paid, p.payment_date, p.payment_method, p.receipt_no,
                  v.voucher_no, v.month_name, v.year, v.fund_type,
                  s.name AS student_name, c.class_name
           FROM fee_payments p
           JOIN fee_vouchers v ON v.id=p.voucher_id
           JOIN students s ON s.id=v.student_id
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           WHERE p.tenant_id=%s
           ORDER BY p.created_at DESC LIMIT %s""",
        (tid, limit),
    )


def _next_voucher_no(tid):
    row = fetchone(
        "SELECT COUNT(*) AS n FROM fee_vouchers WHERE tenant_id=%s", (tid,)
    )
    n = int(row["n"]) + 1 if row else 1
    return f"VCH-{tid:03d}-{n:05d}"


def _monthly_collection(tid, year):
    rows = fetchall(
        """SELECT month_name, SUM(amount) AS total
           FROM fee_vouchers
           WHERE tenant_id=%s AND year=%s AND status='paid'
           GROUP BY month_name
           ORDER BY MIN(id)""",
        (tid, year),
    )
    return {r["month_name"]: float(r["total"]) for r in rows}


def _fund_breakdown(tid, year):
    rows = fetchall(
        """SELECT fund_type, SUM(amount) AS total
           FROM fee_vouchers
           WHERE tenant_id=%s AND year=%s AND status='paid'
           GROUP BY fund_type""",
        (tid, year),
    )
    return {r["fund_type"]: float(r["total"]) for r in rows}


# ──────────────────────────────────────────────────────────────────────────────
# Voucher generation (atomic)
# ──────────────────────────────────────────────────────────────────────────────

def _create_voucher(tid, enrollment_id, student_id, month, year, amount, fund_type, due_date, remarks):
    voucher_no = _next_voucher_no(tid)
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            # Check duplicate
            cur.execute(
                """SELECT id FROM fee_vouchers
                   WHERE tenant_id=%s AND student_id=%s AND month_name=%s AND year=%s AND fund_type=%s""",
                (tid, student_id, month, year, fund_type),
            )
            if cur.fetchone():
                return False, f"Voucher for {month} {year} ({fund_type}) already exists for this student."
            cur.execute(
                """INSERT INTO fee_vouchers
                   (tenant_id, enrollment_id, student_id, voucher_no, issue_date,
                    due_date, month_name, year, amount, fund_type, status, remarks)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'unpaid',%s)
                   RETURNING id, voucher_no""",
                (tid, enrollment_id, student_id, voucher_no,
                 date.today(), due_date, month, year, amount, fund_type, remarks),
            )
            row = cur.fetchone()
        conn.commit()
        return True, row
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _collect_payment(tid, voucher_id, amount_paid, method, notes):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            # Fetch voucher
            cur.execute(
                "SELECT amount, status FROM fee_vouchers WHERE id=%s AND tenant_id=%s",
                (voucher_id, tid),
            )
            v = cur.fetchone()
            if not v:
                return False, "Voucher not found."
            if v["status"] == "paid":
                return False, "This voucher is already fully paid."

            receipt_no = f"RCP-{tid:03d}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cur.execute(
                """INSERT INTO fee_payments
                   (tenant_id, voucher_id, amount_paid, payment_date,
                    payment_method, receipt_no, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (tid, voucher_id, amount_paid, date.today(), method, receipt_no, notes),
            )
            # Update voucher status
            new_status = "paid" if float(amount_paid) >= float(v["amount"]) else "partial"
            cur.execute(
                "UPDATE fee_vouchers SET status=%s, paid_at=NOW() WHERE id=%s AND tenant_id=%s",
                (new_status, voucher_id, tid),
            )
        conn.commit()
        return True, receipt_no
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Voucher HTML display
# ──────────────────────────────────────────────────────────────────────────────

def _voucher_html(student_name, father_name, class_name, voucher_no,
                  month, year, amount, fund_type, due_date, madrasa_name="Demo Madrasa"):
    fund_label = {"general": "General Fund", "zakat": "Zakat Fund",
                  "lillah_boarding": "Lillah Boarding Fund"}.get(fund_type, fund_type.title())
    return f"""
    <div class="voucher">
      <div class="vch-header">
        <div style="font-size:1.1rem;font-weight:700;color:#0F4C5C">{madrasa_name}</div>
        <div style="font-size:0.75rem;color:#6B7A8D">Fee Payment Voucher</div>
      </div>
      <div class="vch-row"><span>Voucher No</span><strong>{voucher_no}</strong></div>
      <div class="vch-row"><span>Student</span><span>{student_name}</span></div>
      <div class="vch-row"><span>Father</span><span>{father_name}</span></div>
      <div class="vch-row"><span>Class</span><span>{class_name}</span></div>
      <div class="vch-row"><span>Month</span><span>{month} {year}</span></div>
      <div class="vch-row"><span>Fund</span><span>{fund_label}</span></div>
      <div class="vch-row"><span>Due Date</span><span>{due_date}</span></div>
      <div class="vch-row vch-total"><span>Amount Due</span><span>৳ {amount:,.0f}</span></div>
      <div style="margin-top:1rem;font-size:0.72rem;color:#6B7A8D;text-align:center">
        Please pay before the due date. Keep this voucher as proof.
      </div>
    </div>
    """


# ──────────────────────────────────────────────────────────────────────────────
# Main render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    page_header("💰", "Finance & Fee Management", "Collect fees, issue vouchers, track ledgers")

    yr = current_year()
    summary = _ledger_summary(tid, year=yr)
    kpi_row([
        {"label": f"Total Billed {yr}",    "value": f"৳{summary['billed']:,.0f}",  "cls": ""},
        {"label": "Collected",              "value": f"৳{summary['paid']:,.0f}",    "cls": "success"},
        {"label": "Outstanding",            "value": f"৳{summary['unpaid']:,.0f}",  "cls": "danger"},
        {"label": "Partial",                "value": f"৳{summary['partial']:,.0f}", "cls": "warning"},
        {"label": "Total Vouchers",         "value": summary["count"],              "cls": ""},
    ])

    tab_collect, tab_voucher, tab_ledger, tab_history = st.tabs([
        "💳 Collect Fee", "🧾 Issue Voucher", "📒 Ledger", "📜 Payment History"
    ])

    students = _active_students(tid)
    student_map = {f"{s['name']} — {s['class_name']} (Roll {s['roll_no'] or '—'})": s
                   for s in students}

    # ── Tab 1: Collect Fee ──
    with tab_collect:
        st.markdown("#### 💳 Record Fee Payment")
        if not students:
            alert("No active students found. Please activate students via Admission module.", "warning")
        else:
            sel_label = st.selectbox("Select Student", ["— Choose —"] + list(student_map.keys()),
                                     key="fc_student")
            if sel_label != "— Choose —":
                stu = student_map[sel_label]
                vouchers = _vouchers_for_student(tid, stu["id"])
                unpaid = [v for v in vouchers if v["status"] in ("unpaid", "partial")]

                if not unpaid:
                    alert("No pending vouchers for this student. Issue a voucher first.", "info")
                else:
                    vch_opts = {
                        f"{v['voucher_no']} | {v['month_name']} {v['year']} | ৳{v['amount']:,.0f} [{v['status']}]": v
                        for v in unpaid
                    }
                    sel_vch_label = st.selectbox("Select Voucher", list(vch_opts.keys()), key="fc_vch")
                    sel_vch = vch_opts[sel_vch_label]

                    with st.form("collect_form"):
                        c1, c2 = st.columns(2)
                        amount_paid = c1.number_input(
                            "Amount Paid (৳)", min_value=1.0,
                            value=float(sel_vch["amount"]), step=50.0
                        )
                        method = c2.selectbox("Payment Method", ["Cash", "bKash", "Nagad", "Bank Transfer"])
                        notes = st.text_input("Notes (optional)", placeholder="Any remarks")
                        submitted = st.form_submit_button("✅ Record Payment", type="primary")
                        if submitted:
                            ok, result = _collect_payment(
                                tid, sel_vch["id"], amount_paid, method.lower(), notes
                            )
                            if ok:
                                st.success(f"Payment recorded! Receipt No: **{result}**")
                                st.rerun()
                            else:
                                st.error(result)

    # ── Tab 2: Issue Voucher ──
    with tab_voucher:
        st.markdown("#### 🧾 Generate Fee Voucher")
        if not students:
            alert("No active students to issue vouchers.", "warning")
        else:
            sel_label2 = st.selectbox("Select Student", ["— Choose —"] + list(student_map.keys()),
                                      key="iv_student")
            if sel_label2 != "— Choose —":
                stu2 = student_map[sel_label2]

                with st.form("voucher_form"):
                    c1, c2, c3 = st.columns(3)
                    month     = c1.selectbox("Month", months_list())
                    year      = c2.number_input("Year", min_value=2020, max_value=2040, value=yr)
                    fund_type = c3.selectbox("Fund Type",
                                             ["general", "zakat", "lillah_boarding"],
                                             format_func=lambda x: x.replace("_", " ").title())

                    c4, c5 = st.columns(2)
                    amount   = c4.number_input("Amount (৳)", min_value=1.0,
                                               value=float(stu2["monthly_fee"]), step=50.0)
                    due_date = c5.date_input("Due Date", value=date.today())
                    remarks  = st.text_input("Remarks (optional)")

                    submitted2 = st.form_submit_button("🖨 Generate Voucher", type="primary")
                    if submitted2:
                        ok, result = _create_voucher(
                            tid, stu2["enrollment_id"], stu2["id"],
                            month, int(year), amount, fund_type, str(due_date), remarks
                        )
                        if ok:
                            st.success(f"Voucher created: **{result['voucher_no']}**")
                            # Show printable voucher
                            st.markdown(
                                _voucher_html(
                                    stu2["name"], stu2["father_name"] or "—",
                                    stu2["class_name"], result["voucher_no"],
                                    month, int(year), amount, fund_type, str(due_date),
                                ),
                                unsafe_allow_html=True,
                            )
                        else:
                            st.error(result)

                # Show existing vouchers for selected student
                divider()
                st.markdown(f"**Voucher History — {stu2['name']}**")
                vouchers = _vouchers_for_student(tid, stu2["id"])
                if vouchers:
                    rows = []
                    for v in vouchers:
                        status_map = {"paid": "success", "unpaid": "danger",
                                      "partial": "warning", "waived": "muted"}
                        rows.append({
                            "Voucher No": v["voucher_no"],
                            "Month": f"{v['month_name']} {v['year']}",
                            "Fund": v["fund_type"].replace("_", " ").title(),
                            "Amount": f"৳{v['amount']:,.0f}",
                            "Status": v["status"].upper(),
                            "Due": str(v["due_date"] or "—"),
                        })
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    alert("No vouchers yet for this student.", "info")

    # ── Tab 3: Ledger ──
    with tab_ledger:
        st.markdown("#### 📒 Multi-Fund Ledger")
        c1, c2 = st.columns(2)
        ledger_year = c1.number_input("Year", min_value=2020, max_value=2040,
                                       value=yr, key="ledger_yr")
        fund_filter = c2.selectbox("Fund", ["All", "General", "Zakat", "Lillah Boarding"],
                                    key="ledger_fund")

        fund_key_map = {
            "All": None, "General": "general",
            "Zakat": "zakat", "Lillah Boarding": "lillah_boarding"
        }
        summ = _ledger_summary(tid, fund_type=fund_key_map[fund_filter], year=int(ledger_year))
        kpi_row([
            {"label": "Total Billed",  "value": f"৳{summ['billed']:,.0f}",  "cls": ""},
            {"label": "Paid",          "value": f"৳{summ['paid']:,.0f}",    "cls": "success"},
            {"label": "Unpaid",        "value": f"৳{summ['unpaid']:,.0f}",  "cls": "danger"},
            {"label": "Partial",       "value": f"৳{summ['partial']:,.0f}", "cls": "warning"},
        ])

        divider()
        st.markdown("**📊 Monthly Collection Chart**")
        monthly = _monthly_collection(tid, int(ledger_year))
        if monthly:
            import pandas as pd
            months = months_list()
            df = pd.DataFrame({
                "Month": months,
                "Collected (৳)": [monthly.get(m, 0) for m in months],
            })
            st.bar_chart(df.set_index("Month"), color="#0F4C5C", height=280)
        else:
            alert("No payment data for the selected period.", "info")

        divider()
        st.markdown("**📊 Fund-wise Breakdown**")
        breakdown = _fund_breakdown(tid, int(ledger_year))
        if breakdown:
            import pandas as pd
            fund_labels = {"general": "General", "zakat": "Zakat", "lillah_boarding": "Lillah Boarding"}
            df2 = pd.DataFrame([
                {"Fund": fund_labels.get(k, k), "Amount (৳)": v}
                for k, v in breakdown.items()
            ])
            st.dataframe(df2, use_container_width=True, hide_index=True)
        else:
            alert("No fund data yet.", "info")

        divider()
        st.markdown("**📋 Detailed Voucher Ledger**")
        params = [tid]
        fund_clause = ""
        if fund_key_map[fund_filter]:
            fund_clause = "AND v.fund_type=%s "
            params.append(fund_key_map[fund_filter])
        params.append(int(ledger_year))

        ledger_rows = fetchall(
            f"""SELECT s.name, c.class_name, v.voucher_no, v.month_name,
                       v.amount, v.fund_type, v.status, v.issue_date
                FROM fee_vouchers v
                JOIN students s ON s.id=v.student_id
                JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
                JOIN classes c ON c.id=e.class_id
                WHERE v.tenant_id=%s {fund_clause} AND v.year=%s
                ORDER BY v.issue_date DESC LIMIT 200""",
            tuple(params),
        )
        if ledger_rows:
            display = []
            for r in ledger_rows:
                display.append({
                    "Student": r["name"],
                    "Class": r["class_name"],
                    "Voucher": r["voucher_no"],
                    "Month": r["month_name"],
                    "Fund": r["fund_type"].replace("_", " ").title(),
                    "Amount": f"৳{r['amount']:,.0f}",
                    "Status": r["status"].upper(),
                    "Issued": str(r["issue_date"]),
                })
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            alert("No ledger entries for selected filters.", "info")

    # ── Tab 4: Payment History ──
    with tab_history:
        st.markdown("#### 📜 Recent Payment History")
        recent = _recent_payments(tid, limit=50)
        if not recent:
            alert("No payments recorded yet.", "info")
        else:
            rows = []
            for r in recent:
                rows.append({
                    "Date": str(r["payment_date"]),
                    "Student": r["student_name"],
                    "Class": r["class_name"],
                    "Voucher": r["voucher_no"],
                    "Month": f"{r['month_name']} {r['year']}",
                    "Fund": r["fund_type"].replace("_", " ").title(),
                    "Paid (৳)": f"৳{r['amount_paid']:,.0f}",
                    "Method": r["payment_method"].title(),
                    "Receipt": r["receipt_no"],
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption(f"Showing last {len(rows)} transactions")

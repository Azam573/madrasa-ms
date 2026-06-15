"""
print_module.py — প্রিন্টযোগ্য ডকুমেন্ট সেন্টার
১. ফি ভাউচার (৩ কপি — অফিস / অভিভাবক / ব্যাংক)
২. টাকা জমার রিসিট (Money Receipt)
৩. শিক্ষক বেতন স্লিপ (Salary Slip)
৪. মার্কশিট (HTML → Print/PDF)

সব ডকুমেন্ট browser print / Ctrl+P দিয়ে PDF সেভ করা যাবে।
"""

import streamlit as st
from datetime import date
from db import fetchall, fetchone
from utils import page_header, alert, divider, get_tenant_id, get_grade

# ──────────────────────────────────────────────────────────────────────────────
# Shared print CSS (injected once per document)
# ──────────────────────────────────────────────────────────────────────────────

PRINT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Amiri:wght@400;700&display=swap');
.print-wrap { font-family:'Inter',sans-serif; color:#1A2332; }
.print-wrap table { border-collapse:collapse; width:100%; }
.print-wrap td, .print-wrap th {
    border:1px solid #ccc; padding:5px 8px; font-size:12px;
}
.print-wrap th { background:#0F4C5C; color:white; font-weight:600; }
.print-wrap .no-border td { border:none; padding:3px 6px; }
@media print {
    .stApp > header, section[data-testid="stSidebar"],
    .stButton, .stSelectbox, .stTextInput,
    [data-testid="stToolbar"], footer { display:none !important; }
    .print-wrap { margin:0; padding:0; }
}
</style>
"""

def _inject_print_css():
    st.markdown(PRINT_CSS, unsafe_allow_html=True)

def _print_button(doc_id: str):
    """JavaScript print trigger for a specific div."""
    st.markdown(
        f"""<button onclick="
            var w=window.open('','_blank');
            var c=document.getElementById('{doc_id}').innerHTML;
            w.document.write('<html><head><title>Print</title>"
            +"<style>body{{font-family:Inter,sans-serif;margin:20px}}"
            +"table{{border-collapse:collapse;width:100%}}"
            +"td,th{{border:1px solid #ccc;padding:5px 8px;font-size:12px}}"
            +"th{{background:#0F4C5C;color:white}}"
            +"</style></head><body>'+c+'</body></html>');
            w.document.close(); w.print();"
            style="background:#0F4C5C;color:white;border:none;padding:0.5rem 1.5rem;
                   border-radius:8px;font-weight:600;cursor:pointer;font-size:0.9rem;
                   margin-bottom:1rem">
            🖨️ প্রিন্ট করুন / PDF সেভ করুন
        </button>""",
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Helper — tenant info
# ──────────────────────────────────────────────────────────────────────────────

def _tenant_info(tid):
    t = fetchone("SELECT * FROM tenants WHERE id=%s", (tid,))
    return t or {"madrasa_name": "Smart Madrasa", "address": "", "phone": "", "email": ""}

# ──────────────────────────────────────────────────────────────────────────────
# ১. ফি ভাউচার — ৩ কপি
# ──────────────────────────────────────────────────────────────────────────────

def _fee_voucher_html(tenant, student, voucher, copy_label, bg_color):
    fund_labels = {
        "general": "সাধারণ ফান্ড",
        "zakat": "যাকাত ফান্ড",
        "lillah_boarding": "লিল্লাহ বোর্ডিং ফান্ড",
    }
    fund = fund_labels.get(voucher.get("fund_type", "general"), "সাধারণ ফান্ড")
    status_color = "#2E7D32" if voucher["status"] == "paid" else "#C62828"
    status_text  = "পরিশোধিত ✓" if voucher["status"] == "paid" else "অপরিশোধিত"

    return f"""
    <div style="border:2px solid #0F4C5C;border-radius:10px;padding:16px;
                background:{bg_color};margin-bottom:8px;page-break-inside:avoid">

      <!-- হেডার -->
      <table class="no-border" style="margin-bottom:8px">
        <tr>
          <td style="width:70%">
            <div style="font-size:17px;font-weight:700;color:#0F4C5C">
              🕌 {tenant['madrasa_name']}
            </div>
            <div style="font-size:11px;color:#555">
              {tenant.get('address','') or ''} | ☎ {tenant.get('phone','') or ''}
            </div>
          </td>
          <td style="text-align:right;vertical-align:top">
            <div style="background:#0F4C5C;color:white;padding:4px 10px;
                        border-radius:6px;font-size:11px;font-weight:600">
              {copy_label}
            </div>
            <div style="font-size:10px;color:#777;margin-top:4px">
              ভাউচার নং: <strong>{voucher['voucher_no']}</strong>
            </div>
          </td>
        </tr>
      </table>

      <div style="border-top:2px dashed #0F4C5C;margin:6px 0;padding-top:8px">
        <div style="text-align:center;font-size:13px;font-weight:700;
                    color:#0F4C5C;margin-bottom:8px">
          ফি পরিশোধ ভাউচার
        </div>
      </div>

      <!-- ছাত্রের তথ্য -->
      <table class="no-border" style="margin-bottom:8px;font-size:12px">
        <tr>
          <td style="width:50%"><strong>ছাত্রের নাম:</strong> {student['name']}</td>
          <td><strong>পিতার নাম:</strong> {student.get('father_name') or '—'}</td>
        </tr>
        <tr>
          <td><strong>শ্রেণী:</strong> {student.get('class_name','')}</td>
          <td><strong>রোল নং:</strong> {student.get('roll_no') or '—'}</td>
        </tr>
        <tr>
          <td><strong>সেশন:</strong> {student.get('session_name','')}</td>
          <td><strong>মোবাইল:</strong> {student.get('mobile_no') or '—'}</td>
        </tr>
      </table>

      <!-- ভাউচার বিবরণ -->
      <table style="margin-bottom:8px;font-size:12px">
        <tr>
          <th>বিবরণ</th><th>মাস</th><th>ফান্ড</th>
          <th>পরিমাণ</th><th>শেষ তারিখ</th><th>অবস্থা</th>
        </tr>
        <tr>
          <td>মাসিক বেতন</td>
          <td>{voucher.get('month_name','')} {voucher.get('year','')}</td>
          <td>{fund}</td>
          <td style="font-weight:700">৳ {float(voucher['amount']):,.0f}</td>
          <td>{str(voucher.get('due_date','')) or '—'}</td>
          <td style="color:{status_color};font-weight:700">{status_text}</td>
        </tr>
      </table>

      <!-- মোট -->
      <table class="no-border" style="font-size:13px">
        <tr>
          <td style="width:60%">
            {f"<span style='color:#2E7D32;font-size:11px'>পরিশোধের তারিখ: {str(voucher.get('paid_at',''))[:10]}</span>"
             if voucher['status']=='paid' else
             f"<span style='color:#C62828;font-size:11px'>⚠ শেষ তারিখের মধ্যে পরিশোধ করুন</span>"}
          </td>
          <td style="text-align:right">
            <strong style="font-size:15px;color:#0F4C5C">
              মোট: ৳ {float(voucher['amount']):,.0f} টাকা
            </strong>
          </td>
        </tr>
      </table>

      <!-- স্বাক্ষর -->
      <table class="no-border" style="margin-top:16px;font-size:11px">
        <tr>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:30px;padding-top:4px">
              অভিভাবকের স্বাক্ষর
            </div>
          </td>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:30px;padding-top:4px">
              ক্যাশিয়ারের স্বাক্ষর
            </div>
          </td>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:30px;padding-top:4px">
              প্রধান শিক্ষকের স্বাক্ষর
            </div>
          </td>
        </tr>
      </table>

      <div style="text-align:center;font-size:10px;color:#888;margin-top:6px">
        ইস্যু তারিখ: {str(voucher.get('issue_date', date.today()))} |
        এই ভাউচার মাদ্রাসা কর্তৃপক্ষ কর্তৃক ইস্যুকৃত
      </div>
    </div>"""


def _render_fee_voucher(tid):
    st.markdown("#### 📄 ফি ভাউচার — ৩ কপি (অফিস / অভিভাবক / ব্যাংক)")

    students = fetchall(
        """SELECT s.id, s.name, s.father_name, s.mobile_no,
                  e.id AS enrollment_id, e.roll_no,
                  c.class_name, sess.session_name
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND s.status='active' AND e.enrollment_status='active'
           ORDER BY c.class_numeric, e.roll_no""",
        (tid,),
    )
    if not students:
        alert("কোনো সক্রিয় ছাত্র নেই।", "warning")
        return

    stu_map = {f"{s['name']} — {s['class_name']} (Roll {s['roll_no'] or '—'})": s for s in students}
    sel = st.selectbox("ছাত্র নির্বাচন করুন", list(stu_map.keys()), key="fv_stu")
    stu = stu_map[sel]

    vouchers = fetchall(
        """SELECT * FROM fee_vouchers
           WHERE tenant_id=%s AND student_id=%s
           ORDER BY year DESC, id DESC LIMIT 20""",
        (tid, stu["id"]),
    )
    if not vouchers:
        alert("এই ছাত্রের কোনো ভাউচার নেই।", "info")
        return

    vch_map = {
        f"{v['voucher_no']} | {v['month_name']} {v['year']} | ৳{float(v['amount']):,.0f} [{v['status'].upper()}]": v
        for v in vouchers
    }
    sel_vch = st.selectbox("ভাউচার নির্বাচন", list(vch_map.keys()), key="fv_vch")
    voucher = vch_map[sel_vch]
    tenant  = _tenant_info(tid)

    _print_button("fee_voucher_print")
    st.markdown(
        f"""<div id="fee_voucher_print" class="print-wrap">
          <div style="text-align:center;font-size:11px;color:#888;margin-bottom:10px">
            ✂ -------- কেটে নিন -------- ✂ -------- কেটে নিন -------- ✂
          </div>
          {_fee_voucher_html(tenant, stu, voucher, "📋 অফিস কপি", "#EAF4F8")}
          <div style="text-align:center;font-size:11px;color:#888;margin:6px 0">
            ✂ -------- কেটে নিন -------- ✂
          </div>
          {_fee_voucher_html(tenant, stu, voucher, "👨‍👩‍👦 অভিভাবক কপি", "#FFF8E1")}
          <div style="text-align:center;font-size:11px;color:#888;margin:6px 0">
            ✂ -------- কেটে নিন -------- ✂
          </div>
          {_fee_voucher_html(tenant, stu, voucher, "🏦 ব্যাংক কপি", "#F3F9F3")}
        </div>""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ২. মানি রিসিট (টাকা জমার রিসিট)
# ──────────────────────────────────────────────────────────────────────────────

def _money_receipt_html(tenant, student, payment, voucher):
    return f"""
    <div style="max-width:560px;margin:0 auto;border:3px double #0F4C5C;
                border-radius:12px;padding:20px;font-family:Inter,sans-serif;
                background:white">

      <!-- হেডার -->
      <div style="text-align:center;border-bottom:2px solid #0F4C5C;padding-bottom:12px;margin-bottom:12px">
        <div style="font-size:22px;font-weight:700;color:#0F4C5C">
          🕌 {tenant['madrasa_name']}
        </div>
        <div style="font-size:11px;color:#666;margin-top:3px">
          {tenant.get('address','') or ''} | ☎ {tenant.get('phone','') or ''}
        </div>
        <div style="margin-top:10px;font-size:16px;font-weight:700;
                    background:#0F4C5C;color:white;padding:5px 20px;
                    border-radius:20px;display:inline-block;letter-spacing:1px">
          টাকা জমার রিসিট
        </div>
      </div>

      <!-- রিসিট নং ও তারিখ -->
      <table class="no-border" style="font-size:12px;margin-bottom:12px">
        <tr>
          <td><strong>রিসিট নং:</strong>
            <span style="color:#0F4C5C;font-weight:700"> {payment['receipt_no']}</span>
          </td>
          <td style="text-align:right"><strong>তারিখ:</strong> {str(payment['payment_date'])}</td>
        </tr>
      </table>

      <!-- ছাত্রের তথ্য বক্স -->
      <div style="background:#F7F9FA;border:1px solid #DDE3E7;border-radius:8px;
                  padding:10px 14px;margin-bottom:12px;font-size:12px">
        <table class="no-border">
          <tr>
            <td style="width:50%"><strong>ছাত্রের নাম:</strong> {student['name']}</td>
            <td><strong>পিতার নাম:</strong> {student.get('father_name') or '—'}</td>
          </tr>
          <tr>
            <td><strong>শ্রেণী:</strong> {student.get('class_name','')}</td>
            <td><strong>রোল নং:</strong> {student.get('roll_no') or '—'}</td>
          </tr>
          <tr>
            <td><strong>মোবাইল:</strong> {student.get('mobile_no') or '—'}</td>
            <td><strong>সেশন:</strong> {student.get('session_name','')}</td>
          </tr>
        </table>
      </div>

      <!-- পেমেন্ট বিবরণ -->
      <table style="font-size:12px;margin-bottom:12px">
        <tr>
          <th>বিবরণ</th><th>মাস/বছর</th><th>ভাউচার নং</th>
          <th>পেমেন্ট পদ্ধতি</th><th style="text-align:right">পরিমাণ</th>
        </tr>
        <tr>
          <td>মাসিক বেতন / ফি</td>
          <td>{voucher.get('month_name','')} {voucher.get('year','')}</td>
          <td>{voucher.get('voucher_no','')}</td>
          <td>{payment.get('payment_method','cash').title()}</td>
          <td style="text-align:right;font-weight:700">
            ৳ {float(payment['amount_paid']):,.0f}
          </td>
        </tr>
      </table>

      <!-- মোট টাকার বক্স -->
      <div style="background:#0F4C5C;color:white;border-radius:8px;
                  padding:12px 16px;margin-bottom:16px;text-align:center">
        <div style="font-size:11px;opacity:0.8;margin-bottom:4px">মোট গৃহীত পরিমাণ</div>
        <div style="font-size:24px;font-weight:700">
          ৳ {float(payment['amount_paid']):,.2f} টাকা
        </div>
        <div style="font-size:11px;opacity:0.8;margin-top:4px">
          ({_amount_in_words(int(payment['amount_paid']))} টাকা)
        </div>
      </div>

      <!-- স্বাক্ষর -->
      <table class="no-border" style="font-size:11px;margin-top:8px">
        <tr>
          <td style="width:50%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              গ্রাহকের স্বাক্ষর
            </div>
          </td>
          <td style="width:50%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              ক্যাশিয়ার/অনুমোদনকারীর স্বাক্ষর ও সিল
            </div>
          </td>
        </tr>
      </table>

      <div style="text-align:center;font-size:10px;color:#999;margin-top:12px;
                  border-top:1px dashed #ccc;padding-top:8px">
        এই রিসিটটি সংগ্রহে রাখুন · ইস্যুকারী: {tenant['madrasa_name']}
      </div>
    </div>"""


def _amount_in_words(amount: int) -> str:
    """Simple Bangla amount-in-words for common amounts."""
    ones = ["", "এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "নয়",
            "দশ", "এগারো", "বারো", "তেরো", "চৌদ্দ", "পনেরো", "ষোল", "সতেরো",
            "আঠারো", "উনিশ"]
    tens  = ["", "", "বিশ", "ত্রিশ", "চল্লিশ", "পঞ্চাশ", "ষাট", "সত্তর",
             "আশি", "নব্বই"]

    if amount == 0:
        return "শূন্য"
    if amount < 0:
        return "ঋণাত্মক " + _amount_in_words(-amount)

    result = ""
    if amount >= 1000:
        result += _amount_in_words(amount // 1000) + " হাজার "
        amount %= 1000
    if amount >= 100:
        result += ones[amount // 100] + " শত "
        amount %= 100
    if amount >= 20:
        result += tens[amount // 10] + " "
        amount %= 10
    if amount > 0:
        result += ones[amount] + " "

    return result.strip()


def _render_money_receipt(tid):
    st.markdown("#### 🧾 টাকা জমার রিসিট (Money Receipt)")

    students = fetchall(
        """SELECT s.id, s.name, s.father_name, s.mobile_no,
                  e.roll_no, c.class_name, sess.session_name
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND s.status='active'
           ORDER BY c.class_numeric, e.roll_no""",
        (tid,),
    )
    if not students:
        alert("কোনো ছাত্র নেই।", "warning")
        return

    stu_map = {f"{s['name']} — {s['class_name']} (Roll {s['roll_no'] or '—'})": s for s in students}
    sel = st.selectbox("ছাত্র নির্বাচন", list(stu_map.keys()), key="mr_stu")
    stu = stu_map[sel]

    payments = fetchall(
        """SELECT p.*, v.voucher_no, v.month_name, v.year, v.fund_type
           FROM fee_payments p
           JOIN fee_vouchers v ON v.id=p.voucher_id
           WHERE p.tenant_id=%s AND v.student_id=%s
           ORDER BY p.created_at DESC LIMIT 20""",
        (tid, stu["id"]),
    )
    if not payments:
        alert("এই ছাত্রের কোনো পেমেন্ট রেকর্ড নেই।", "info")
        return

    pay_map = {
        f"{p['receipt_no']} | {p['month_name']} {p['year']} | ৳{float(p['amount_paid']):,.0f} | {str(p['payment_date'])}": p
        for p in payments
    }
    sel_pay = st.selectbox("পেমেন্ট/রিসিট নির্বাচন", list(pay_map.keys()), key="mr_pay")
    payment = pay_map[sel_pay]

    voucher = fetchone(
        "SELECT * FROM fee_vouchers WHERE voucher_no=%s AND tenant_id=%s",
        (payment["voucher_no"], tid),
    ) or {}
    tenant = _tenant_info(tid)

    _print_button("money_receipt_print")
    st.markdown(
        f'<div id="money_receipt_print" class="print-wrap">'
        f'{_money_receipt_html(tenant, stu, payment, voucher)}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ৩. বেতন স্লিপ (Salary Slip)
# ──────────────────────────────────────────────────────────────────────────────

def _salary_slip_html(tenant, teacher, salary):
    net = float(salary.get("net_salary") or
                (float(salary["basic_salary"]) + float(salary["bonus"]) - float(salary["deduction"])))
    return f"""
    <div style="max-width:580px;margin:0 auto;border:2px solid #0F4C5C;
                border-radius:12px;padding:20px;font-family:Inter,sans-serif;
                background:white">

      <!-- হেডার -->
      <div style="text-align:center;border-bottom:2px solid #0F4C5C;
                  padding-bottom:12px;margin-bottom:14px">
        <div style="font-size:20px;font-weight:700;color:#0F4C5C">
          🕌 {tenant['madrasa_name']}
        </div>
        <div style="font-size:11px;color:#666">
          {tenant.get('address','') or ''} | ☎ {tenant.get('phone','') or ''}
        </div>
        <div style="margin-top:10px;font-size:15px;font-weight:700;
                    background:#0F4C5C;color:white;padding:4px 20px;
                    border-radius:20px;display:inline-block">
          বেতন স্লিপ — {salary['month_name']} {salary['year']}
        </div>
      </div>

      <!-- শিক্ষকের তথ্য -->
      <div style="background:#F7F9FA;border:1px solid #DDE3E7;border-radius:8px;
                  padding:10px 14px;margin-bottom:14px;font-size:12px">
        <table class="no-border">
          <tr>
            <td style="width:50%"><strong>নাম:</strong> {teacher['name']}</td>
            <td><strong>পদবী:</strong> {teacher.get('designation','Teacher')}</td>
          </tr>
          <tr>
            <td><strong>যোগদান:</strong> {str(teacher.get('joining_date','')) or '—'}</td>
            <td><strong>মোবাইল:</strong> {teacher.get('mobile_no','') or '—'}</td>
          </tr>
          <tr>
            <td><strong>যোগ্যতা:</strong> {teacher.get('qualification','') or '—'}</td>
            <td><strong>NID:</strong> {teacher.get('nid_no','') or '—'}</td>
          </tr>
        </table>
      </div>

      <!-- বেতনের হিসাব -->
      <table style="font-size:13px;margin-bottom:14px">
        <tr><th colspan="2" style="text-align:left">আয় (Earnings)</th></tr>
        <tr>
          <td>মূল বেতন (Basic Salary)</td>
          <td style="text-align:right;font-weight:600">৳ {float(salary['basic_salary']):,.2f}</td>
        </tr>
        <tr>
          <td>বোনাস / ভাতা (Bonus/Allowance)</td>
          <td style="text-align:right;color:#2E7D32">৳ {float(salary['bonus'] or 0):,.2f}</td>
        </tr>
        <tr style="background:#FFF8E1">
          <td style="font-weight:700">মোট আয়</td>
          <td style="text-align:right;font-weight:700">
            ৳ {float(salary['basic_salary'])+float(salary['bonus'] or 0):,.2f}
          </td>
        </tr>
        <tr><th colspan="2" style="text-align:left">কর্তন (Deductions)</th></tr>
        <tr>
          <td>মোট কর্তন</td>
          <td style="text-align:right;color:#C62828">৳ {float(salary['deduction'] or 0):,.2f}</td>
        </tr>
      </table>

      <!-- নেট বেতন বক্স -->
      <div style="background:#0F4C5C;color:white;border-radius:8px;
                  padding:12px 16px;text-align:center;margin-bottom:16px">
        <div style="font-size:11px;opacity:0.8;margin-bottom:4px">নেট বেতন (Net Salary)</div>
        <div style="font-size:26px;font-weight:700">৳ {net:,.2f} টাকা</div>
        <div style="font-size:11px;opacity:0.8;margin-top:4px">
          ({_amount_in_words(int(net))} টাকা মাত্র)
        </div>
      </div>

      <!-- পেমেন্ট তথ্য -->
      <table class="no-border" style="font-size:12px;margin-bottom:16px">
        <tr>
          <td><strong>পেমেন্ট পদ্ধতি:</strong>
            {salary.get('payment_method','cash').title()}</td>
          <td style="text-align:right"><strong>পরিশোধের তারিখ:</strong>
            {str(salary.get('payment_date','')) or '—'}</td>
        </tr>
        {"<tr><td colspan='2'><strong>মন্তব্য:</strong> " + (salary.get('remarks','') or '') + "</td></tr>"
         if salary.get('remarks') else ""}
      </table>

      <!-- স্বাক্ষর -->
      <table class="no-border" style="font-size:11px">
        <tr>
          <td style="width:50%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              শিক্ষকের স্বাক্ষর ও তারিখ
            </div>
          </td>
          <td style="width:50%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              প্রধান শিক্ষক / কর্তৃপক্ষের সিল ও স্বাক্ষর
            </div>
          </td>
        </tr>
      </table>

      <div style="text-align:center;font-size:10px;color:#999;
                  margin-top:12px;border-top:1px dashed #ccc;padding-top:8px">
        এই স্লিপটি গোপনীয় · {tenant['madrasa_name']} কর্তৃক ইস্যুকৃত
      </div>
    </div>"""


def _render_salary_slip(tid):
    st.markdown("#### 💼 শিক্ষক বেতন স্লিপ (Salary Slip)")

    # Check teacher table exists
    teachers = fetchall(
        "SELECT * FROM teachers WHERE tenant_id=%s AND status='active' ORDER BY name",
        (tid,),
    )
    if not teachers:
        alert("কোনো সক্রিয় শিক্ষক নেই। প্রথমে শিক্ষক যোগ করুন।", "warning")
        return

    tch_map = {t["name"]: t for t in teachers}
    sel_tch = st.selectbox("শিক্ষক নির্বাচন", list(tch_map.keys()), key="ss_tch")
    tch = tch_map[sel_tch]

    salaries = fetchall(
        """SELECT * FROM teacher_salary
           WHERE tenant_id=%s AND teacher_id=%s AND status='paid'
           ORDER BY year DESC, id DESC LIMIT 24""",
        (tid, tch["id"]),
    )
    if not salaries:
        alert("এই শিক্ষকের কোনো বেতন পরিশোধের রেকর্ড নেই।", "info")
        return

    sal_map = {
        f"{s['month_name']} {s['year']} — ৳{float(s['net_salary'] or 0):,.0f}": s
        for s in salaries
    }
    sel_sal = st.selectbox("বেতন মাস নির্বাচন", list(sal_map.keys()), key="ss_sal")
    salary  = sal_map[sel_sal]
    tenant  = _tenant_info(tid)

    _print_button("salary_slip_print")
    st.markdown(
        f'<div id="salary_slip_print" class="print-wrap">'
        f'{_salary_slip_html(tenant, tch, salary)}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ৪. মার্কশিট প্রিন্ট
# ──────────────────────────────────────────────────────────────────────────────

def _marksheet_print_html(tenant, student, exam_name, session_name,
                           marks_list, total_obt, total_full, pct, grade, gpa, rank):
    grade_color = "#2E7D32" if grade not in ("D","F") else "#C62828"
    rows = ""
    for m in marks_list:
        obt = int(m.get("total_obtained") or 0)
        pm  = int(m.get("pass_marks") or 33)
        is_abs = m.get("is_absent", False)
        res_color = "#C62828" if (is_abs or obt < pm) else "#2E7D32"
        result    = "ABS" if is_abs else ("PASS" if obt >= pm else "FAIL")
        rows += f"""<tr>
          <td>{m['subject_name']}</td>
          <td style="text-align:center">{m['full_marks']}</td>
          <td style="text-align:center">{m['pass_marks']}</td>
          <td style="text-align:center">{'ABS' if is_abs else m.get('written_obtained',0)}</td>
          <td style="text-align:center">{'—' if is_abs else m.get('mcq_obtained',0)}</td>
          <td style="text-align:center">{'—' if is_abs else m.get('practical_obtained',0)}</td>
          <td style="text-align:center;font-weight:700">{'ABS' if is_abs else obt}</td>
          <td style="text-align:center;color:{res_color};font-weight:700">{result}</td>
        </tr>"""

    return f"""
    <div style="max-width:680px;margin:0 auto;border:2px solid #0F4C5C;
                border-radius:12px;padding:20px;font-family:Inter,sans-serif;background:white">

      <!-- হেডার -->
      <div style="text-align:center;border-bottom:2px solid #0F4C5C;
                  padding-bottom:12px;margin-bottom:14px">
        <div style="font-size:20px;font-weight:700;color:#0F4C5C">
          🕌 {tenant['madrasa_name']}
        </div>
        <div style="font-size:11px;color:#666">{tenant.get('address','') or ''}</div>
        <div style="margin-top:8px;font-size:15px;font-weight:700;
                    background:#0F4C5C;color:white;padding:4px 20px;
                    border-radius:20px;display:inline-block">
          পরীক্ষার মার্কশিট — {exam_name}
        </div>
        <div style="font-size:12px;color:#555;margin-top:4px">সেশন: {session_name}</div>
      </div>

      <!-- ছাত্রের তথ্য -->
      <div style="background:#F7F9FA;border:1px solid #DDE3E7;border-radius:8px;
                  padding:10px 14px;margin-bottom:14px;font-size:12px">
        <table class="no-border">
          <tr>
            <td style="width:50%"><strong>ছাত্রের নাম:</strong> {student['name']}</td>
            <td><strong>পিতার নাম:</strong> {student.get('father_name') or '—'}</td>
          </tr>
          <tr>
            <td><strong>শ্রেণী:</strong> {student.get('class_name','')}</td>
            <td><strong>রোল নং:</strong> {student.get('roll_no') or '—'}</td>
          </tr>
          <tr>
            <td><strong>সেশন:</strong> {session_name}</td>
            <td><strong>মেধাক্রম:</strong> {rank}</td>
          </tr>
        </table>
      </div>

      <!-- মার্কস টেবিল -->
      <table style="font-size:12px;margin-bottom:14px">
        <tr>
          <th style="text-align:left">বিষয়</th>
          <th>পূর্ণমান</th><th>পাশমান</th>
          <th>রচনামূলক</th><th>MCQ</th><th>ব্যবহারিক</th>
          <th>মোট</th><th>ফলাফল</th>
        </tr>
        {rows}
        <tr style="background:#EAF4F8;font-weight:700">
          <td>সর্বমোট</td>
          <td style="text-align:center">{total_full}</td>
          <td colspan="4"></td>
          <td style="text-align:center">{total_obt}</td>
          <td></td>
        </tr>
      </table>

      <!-- ফলাফল সারাংশ -->
      <div style="display:flex;gap:16px;margin-bottom:16px">
        <div style="flex:1;background:#F7F9FA;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:11px;color:#666">মোট প্রাপ্ত</div>
          <div style="font-size:20px;font-weight:700;color:#0F4C5C">{total_obt}/{total_full}</div>
        </div>
        <div style="flex:1;background:#F7F9FA;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:11px;color:#666">শতকরা</div>
          <div style="font-size:20px;font-weight:700;color:#0F4C5C">{pct:.1f}%</div>
        </div>
        <div style="flex:1;background:{grade_color};border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:11px;color:rgba(255,255,255,0.8)">গ্রেড</div>
          <div style="font-size:20px;font-weight:700;color:white">{grade}</div>
        </div>
        <div style="flex:1;background:#F7F9FA;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:11px;color:#666">GPA</div>
          <div style="font-size:20px;font-weight:700;color:#0F4C5C">{gpa:.2f}</div>
        </div>
        <div style="flex:1;background:#F7F9FA;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:11px;color:#666">মেধাক্রম</div>
          <div style="font-size:20px;font-weight:700;color:#E8A838">#{rank}</div>
        </div>
      </div>

      <!-- স্বাক্ষর -->
      <table class="no-border" style="font-size:11px">
        <tr>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              শ্রেণী শিক্ষকের স্বাক্ষর
            </div>
          </td>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              পরীক্ষা নিয়ন্ত্রকের স্বাক্ষর
            </div>
          </td>
          <td style="width:33%;text-align:center">
            <div style="border-top:1px solid #555;margin-top:35px;padding-top:4px">
              প্রধান শিক্ষকের সিল ও স্বাক্ষর
            </div>
          </td>
        </tr>
      </table>

      <div style="text-align:center;font-size:10px;color:#999;
                  margin-top:12px;border-top:1px dashed #ccc;padding-top:8px">
        ইস্যু তারিখ: {date.today()} · {tenant['madrasa_name']} কর্তৃক প্রদত্ত
      </div>
    </div>"""


def _render_marksheet(tid):
    st.markdown("#### 📊 মার্কশিট প্রিন্ট")

    sessions = fetchall(
        "SELECT id, session_name FROM academic_sessions WHERE tenant_id=%s ORDER BY id DESC", (tid,)
    )
    classes = fetchall(
        "SELECT id, class_name, class_numeric FROM classes WHERE tenant_id=%s ORDER BY class_numeric", (tid,)
    )
    if not sessions or not classes:
        alert("সেশন বা ক্লাস নেই।", "warning")
        return

    sess_map  = {s["session_name"]: s["id"] for s in sessions}
    class_map = {c["class_name"]:   c["id"] for c in classes}

    c1, c2 = st.columns(2)
    sel_sess  = c1.selectbox("সেশন",  list(sess_map.keys()),  key="ms2_sess")
    sel_class = c2.selectbox("শ্রেণী", list(class_map.keys()), key="ms2_class")

    exams = fetchall(
        "SELECT id, exam_name FROM exams WHERE tenant_id=%s AND session_id=%s ORDER BY exam_date",
        (tid, sess_map[sel_sess]),
    )
    if not exams:
        alert("এই সেশনে কোনো পরীক্ষা নেই।", "info")
        return

    exam_map = {e["exam_name"]: e["id"] for e in exams}
    sel_exam = st.selectbox("পরীক্ষা", list(exam_map.keys()), key="ms2_exam")

    students = fetchall(
        """SELECT s.id AS student_id, s.name, s.father_name,
                  e.roll_no, e.id AS enrollment_id, c.class_name, sess.session_name
           FROM students s
           JOIN student_enrollments e ON e.student_id=s.id AND e.tenant_id=s.tenant_id
           JOIN classes c ON c.id=e.class_id
           JOIN academic_sessions sess ON sess.id=e.session_id
           WHERE s.tenant_id=%s AND e.session_id=%s AND e.class_id=%s
             AND e.enrollment_status='active'
           ORDER BY e.roll_no""",
        (tid, sess_map[sel_sess], class_map[sel_class]),
    )
    if not students:
        alert("এই শ্রেণীতে কোনো ছাত্র নেই।", "info")
        return

    stu_map = {f"Roll {s['roll_no'] or '?'} — {s['name']}": s for s in students}
    sel_stu = st.selectbox("ছাত্র", list(stu_map.keys()), key="ms2_stu")
    stu = stu_map[sel_stu]

    if st.button("📄 মার্কশিট তৈরি করুন", type="primary", key="gen_ms2"):
        marks = fetchall(
            """SELECT sm.*, subj.subject_name, subj.full_marks, subj.pass_marks
               FROM student_marks sm
               JOIN subjects subj ON subj.id=sm.subject_id
               WHERE sm.tenant_id=%s AND sm.enrollment_id=%s AND sm.exam_id=%s
               ORDER BY subj.id""",
            (tid, stu["enrollment_id"], exam_map[sel_exam]),
        )
        if not marks:
            alert("এই ছাত্রের নম্বর এখনো এন্ট্রি হয়নি।", "warning")
            return

        # Calculate rank
        all_results = fetchall(
            """SELECT e.id AS enrollment_id, SUM(sm.total_obtained) AS total
               FROM student_enrollments e
               JOIN student_marks sm ON sm.enrollment_id=e.id
               WHERE e.tenant_id=%s AND e.session_id=%s AND e.class_id=%s AND sm.exam_id=%s
               GROUP BY e.id ORDER BY total DESC""",
            (tid, sess_map[sel_sess], class_map[sel_class], exam_map[sel_exam]),
        )
        rank = next(
            (i+1 for i, r in enumerate(all_results) if r["enrollment_id"] == stu["enrollment_id"]),
            "—"
        )

        total_full = sum(int(m["full_marks"]) for m in marks)
        total_obt  = sum(int(m["total_obtained"] or 0) for m in marks)
        pct        = round(total_obt / total_full * 100, 2) if total_full else 0
        grade, gpa = get_grade(pct)
        tenant     = _tenant_info(tid)

        _print_button("marksheet_print")
        st.markdown(
            f'<div id="marksheet_print" class="print-wrap">'
            f'{_marksheet_print_html(tenant, stu, sel_exam, sel_sess, marks, total_obt, total_full, pct, grade, gpa, rank)}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Main Render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    _inject_print_css()
    page_header("🖨️", "প্রিন্ট সেন্টার", "ভাউচার · রিসিট · বেতন স্লিপ · মার্কশিট")

    st.markdown(
        """<div class="alert alert-info" style="margin-bottom:1rem">
        💡 <strong>প্রিন্ট নির্দেশনা:</strong>
        ডকুমেন্ট তৈরির পর <strong>🖨️ প্রিন্ট করুন</strong> বাটনে ক্লিক করুন।
        ব্রাউজারে Print ডায়ালগ আসবে — সেখান থেকে <strong>PDF হিসেবে সেভ</strong> করুন
        অথবা সরাসরি প্রিন্টারে পাঠান। <em>Destination: Save as PDF</em> নির্বাচন করুন।
        </div>""",
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 ফি ভাউচার (৩ কপি)",
        "🧾 টাকা জমার রিসিট",
        "💼 বেতন স্লিপ",
        "📊 মার্কশিট",
    ])

    with tab1:
        _render_fee_voucher(tid)

    with tab2:
        _render_money_receipt(tid)

    with tab3:
        _render_salary_slip(tid)

    with tab4:
        _render_marksheet(tid)

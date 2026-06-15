"""
notice_module.py — Notice Board & Notification Center
Publish notices, due-fee SMS alerts, exam schedule announcements.
Integrates with local SMS gateway (configurable) or stores as in-app notifications.
"""

import streamlit as st
from datetime import date, datetime
from db import get_connection, fetchall, fetchone
from utils import page_header, kpi_row, alert, divider, get_tenant_id


# ──────────────────────────────────────────────────────────────────────────────
# Table setup
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_tables():
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                id           SERIAL PRIMARY KEY,
                tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                title        TEXT NOT NULL,
                body         TEXT NOT NULL,
                category     TEXT DEFAULT 'general',
                target_class INTEGER REFERENCES classes(id) ON DELETE SET NULL,
                is_pinned    BOOLEAN DEFAULT FALSE,
                publish_date DATE DEFAULT CURRENT_DATE,
                expiry_date  DATE,
                created_by   TEXT DEFAULT 'Admin',
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id           SERIAL PRIMARY KEY,
                tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                student_id   INTEGER REFERENCES students(id) ON DELETE CASCADE,
                message      TEXT NOT NULL,
                type         TEXT DEFAULT 'info',
                is_read      BOOLEAN DEFAULT FALSE,
                sent_via_sms BOOLEAN DEFAULT FALSE,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
            """)
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_notices(tid, category=None):
    params = [tid, date.today()]
    cat_clause = ""
    if category and category != "সব":
        cat_clause = "AND n.category=%s"
        params.append(category.lower())
    return fetchall(
        f"""SELECT n.*, c.class_name FROM notices n
            LEFT JOIN classes c ON c.id=n.target_class
            WHERE n.tenant_id=%s
              AND (n.expiry_date IS NULL OR n.expiry_date >= %s)
              {cat_clause}
            ORDER BY n.is_pinned DESC, n.created_at DESC
            LIMIT 50""",
        tuple(params),
    )


def _create_notice(tid, title, body, category, target_class_id, is_pinned, expiry):
    conn = get_connection()
    if not conn:
        return False, "DB error"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO notices
                   (tenant_id, title, body, category, target_class, is_pinned, expiry_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (tid, title, body, category, target_class_id, is_pinned,
                 str(expiry) if expiry else None),
            )
            nid = cur.fetchone()["id"]
        conn.commit()
        return True, nid
    except Exception as ex:
        conn.rollback()
        return False, str(ex)
    finally:
        conn.close()


def _delete_notice(tid, notice_id):
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notices WHERE id=%s AND tenant_id=%s", (notice_id, tid))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def _generate_due_notifications(tid):
    """Auto-generate in-app notifications for students with unpaid fees."""
    due_students = fetchall(
        """SELECT DISTINCT s.id AS student_id, s.name, s.mobile_no,
                  v.month_name, v.year, v.amount, v.fund_type
           FROM fee_vouchers v
           JOIN students s ON s.id=v.student_id
           WHERE v.tenant_id=%s AND v.status='unpaid'
             AND (v.due_date IS NULL OR v.due_date <= CURRENT_DATE + INTERVAL '3 days')""",
        (tid,),
    )
    conn = get_connection()
    if not conn:
        return 0
    count = 0
    try:
        with conn.cursor() as cur:
            for stu in due_students:
                msg = (
                    f"প্রিয় অভিভাবক, {stu['name']}-এর {stu['month_name']} {stu['year']} মাসের "
                    f"৳{float(stu['amount']):,.0f} ফি বকেয়া রয়েছে। অনুগ্রহ করে দ্রুত পরিশোধ করুন।"
                )
                cur.execute(
                    """INSERT INTO notifications (tenant_id, student_id, message, type)
                       VALUES (%s,%s,%s,'warning')
                       ON CONFLICT DO NOTHING""",
                    (tid, stu["student_id"], msg),
                )
                count += 1
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


def _get_notifications(tid, limit=30):
    return fetchall(
        """SELECT n.id, n.message, n.type, n.is_read, n.sent_via_sms,
                  n.created_at, s.name AS student_name, s.mobile_no
           FROM notifications n
           LEFT JOIN students s ON s.id=n.student_id
           WHERE n.tenant_id=%s
           ORDER BY n.created_at DESC LIMIT %s""",
        (tid, limit),
    )


def _mark_all_read(tid):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE notifications SET is_read=TRUE WHERE tenant_id=%s", (tid,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def _bulk_sms_preview(tid):
    """Returns list of students with pending dues for SMS preview."""
    return fetchall(
        """SELECT s.name, s.mobile_no,
                  COUNT(v.id) AS due_count,
                  SUM(v.amount) AS total_due
           FROM students s
           JOIN fee_vouchers v ON v.student_id=s.id AND v.tenant_id=s.tenant_id
           WHERE s.tenant_id=%s AND v.status='unpaid' AND s.mobile_no IS NOT NULL
           GROUP BY s.id, s.name, s.mobile_no
           ORDER BY total_due DESC""",
        (tid,),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Notice card HTML
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "general":  ("#E3F2FD", "#1565C0", "📢"),
    "exam":     ("#FFF8E1", "#9a6800", "📝"),
    "fee":      ("#FFEBEE", "#C62828", "💰"),
    "holiday":  ("#E8F5E9", "#2E7D32", "🌿"),
    "result":   ("#F3E5F5", "#6A1B9A", "🏆"),
    "event":    ("#FBE9E7", "#BF360C", "🎉"),
}

def _notice_card_html(n):
    bg, color, icon = CATEGORY_COLORS.get(n["category"], ("#F7F9FA", "#1A2332", "📌"))
    pinned = "📌 " if n["is_pinned"] else ""
    target = f" · {n['class_name']}" if n.get("class_name") else ""
    return f"""
    <div style="background:{bg};border-left:4px solid {color};border-radius:8px;
                padding:1rem 1.25rem;margin-bottom:0.75rem">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <span style="font-size:1.1rem">{icon}</span>
          <strong style="color:{color};margin-left:0.4rem">{pinned}{n['title']}</strong>
          <span style="font-size:0.72rem;color:#6B7A8D;margin-left:0.5rem">
            {n['category'].title()}{target} · {str(n['publish_date'])}
          </span>
        </div>
      </div>
      <div style="margin-top:0.5rem;font-size:0.88rem;color:#1A2332;white-space:pre-wrap">{n['body']}</div>
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────────────

def render():
    tid = get_tenant_id()
    _ensure_tables()
    page_header("📢", "নোটিশ বোর্ড ও নোটিফিকেশন", "বিজ্ঞপ্তি, অ্যালার্ট ও SMS ব্যবস্থাপনা")

    # Unread count
    unread = fetchone(
        "SELECT COUNT(*) AS n FROM notifications WHERE tenant_id=%s AND is_read=FALSE", (tid,)
    )
    unread_count = int(unread["n"]) if unread else 0
    notices_total = fetchone("SELECT COUNT(*) AS n FROM notices WHERE tenant_id=%s", (tid,))

    kpi_row([
        {"label": "মোট নোটিশ",        "value": int(notices_total["n"]) if notices_total else 0, "cls": ""},
        {"label": "অপঠিত নোটিফিকেশন", "value": unread_count,   "cls": "warning" if unread_count else ""},
    ])

    tab_board, tab_create, tab_notif, tab_sms = st.tabs([
        "📋 নোটিশ বোর্ড", "✏️ নোটিশ তৈরি", f"🔔 নোটিফিকেশন ({unread_count})", "📱 SMS অ্যালার্ট"
    ])

    # ── নোটিশ বোর্ড ──
    with tab_board:
        CATEGORIES = ["সব", "General", "Exam", "Fee", "Holiday", "Result", "Event"]
        cat_filter = st.radio("ক্যাটাগরি", CATEGORIES, horizontal=True, key="notice_cat")
        notices = _get_notices(tid, None if cat_filter == "সব" else cat_filter)

        if not notices:
            alert("কোনো নোটিশ নেই।", "info")
        else:
            for n in notices:
                col_notice, col_del = st.columns([10, 1])
                with col_notice:
                    st.markdown(_notice_card_html(n), unsafe_allow_html=True)
                with col_del:
                    st.markdown("<div style='margin-top:0.75rem'>", unsafe_allow_html=True)
                    if st.button("🗑", key=f"del_notice_{n['id']}", help="মুছুন"):
                        _delete_notice(tid, n["id"])
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    # ── নোটিশ তৈরি ──
    with tab_create:
        st.markdown("#### ✏️ নতুন নোটিশ প্রকাশ করুন")
        classes = fetchall(
            "SELECT id, class_name FROM classes WHERE tenant_id=%s ORDER BY class_numeric", (tid,)
        )
        class_opts = {"সকল ক্লাস (General)": None}
        class_opts.update({c["class_name"]: c["id"] for c in classes})

        with st.form("notice_form"):
            title    = st.text_input("শিরোনাম *", placeholder="যেমন: অর্ধবার্ষিক পরীক্ষার নোটিশ")
            body     = st.text_area("বিষয়বস্তু *", height=140,
                                    placeholder="নোটিশের বিস্তারিত লিখুন...")
            c1, c2, c3 = st.columns(3)
            category = c1.selectbox("ক্যাটাগরি",
                                    ["general", "exam", "fee", "holiday", "result", "event"])
            target   = c2.selectbox("টার্গেট", list(class_opts.keys()))
            expiry   = c3.date_input("মেয়াদ উত্তীর্ণ", value=None)
            is_pinned = st.checkbox("📌 শীর্ষে পিন করুন")

            if st.form_submit_button("📢 নোটিশ প্রকাশ করুন", type="primary"):
                if not title.strip() or not body.strip():
                    st.error("শিরোনাম ও বিষয়বস্তু আবশ্যক।")
                else:
                    ok, result = _create_notice(
                        tid, title.strip(), body.strip(), category,
                        class_opts[target], is_pinned, expiry
                    )
                    if ok:
                        st.success(f"✅ নোটিশ প্রকাশিত হয়েছে! ID: {result}")
                        st.rerun()
                    else:
                        st.error(result)

    # ── নোটিফিকেশন ──
    with tab_notif:
        col_gen, col_mark = st.columns([3, 1])
        with col_gen:
            if st.button("🔄 বকেয়া ফি অ্যালার্ট তৈরি করুন", type="primary"):
                count = _generate_due_notifications(tid)
                st.success(f"{count}টি নোটিফিকেশন তৈরি হয়েছে!")
                st.rerun()
        with col_mark:
            if st.button("✅ সব পঠিত", key="mark_all_read"):
                _mark_all_read(tid)
                st.rerun()

        notifs = _get_notifications(tid)
        if not notifs:
            alert("কোনো নোটিফিকেশন নেই।", "info")
        else:
            type_colors = {"warning": "🟡", "danger": "🔴", "info": "🔵", "success": "🟢"}
            for n in notifs:
                read_style = "" if n["is_read"] else "font-weight:600;"
                icon = type_colors.get(n["type"], "⚪")
                st.markdown(
                    f"""<div style="padding:0.6rem 0.75rem;border-bottom:1px solid #DDE3E7;
                                    {read_style}">
                      {icon} {n['message']}
                      <span style="float:right;font-size:0.72rem;color:#6B7A8D">
                        {n['student_name'] or ''} · {str(n['created_at'])[:16]}
                      </span>
                    </div>""",
                    unsafe_allow_html=True,
                )

    # ── SMS অ্যালার্ট ──
    with tab_sms:
        st.markdown("#### 📱 SMS অ্যালার্ট প্রিভিউ")
        alert(
            "🔧 SMS পাঠাতে আপনার SMS Gateway API Key সেটিংসে যোগ করুন "
            "(Green Web, SSL Wireless, Infobip ইত্যাদি)। "
            "এই ভিউতে কোন SMS পাঠানো হবে যাবে তার প্রিভিউ দেখা যাচ্ছে।",
            "info"
        )

        sms_list = _bulk_sms_preview(tid)
        if not sms_list:
            alert("কোনো বকেয়া ফি নেই — SMS পাঠানোর প্রয়োজন নেই! 🎉", "success")
        else:
            st.markdown(f"**{len(sms_list)} জন ছাত্রের অভিভাবককে SMS পাঠানো হবে:**")
            rows = []
            for s in sms_list:
                msg = (
                    f"প্রিয় অভিভাবক, আপনার সন্তান {s['name']}-এর "
                    f"{s['due_count']}টি বকেয়া ফি (মোট ৳{float(s['total_due']):,.0f}) রয়েছে। "
                    "অনুগ্রহ করে দ্রুত পরিশোধ করুন।"
                )
                rows.append({
                    "নাম":    s["name"],
                    "মোবাইল": s["mobile_no"],
                    "বকেয়া": s["due_count"],
                    "মোট (৳)": f"৳{float(s['total_due']):,.0f}",
                    "SMS বার্তা": msg[:60] + "...",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

            # Custom SMS composer
            divider()
            st.markdown("**✉️ কাস্টম SMS কম্পোজার**")
            with st.form("sms_compose"):
                custom_msg = st.text_area(
                    "বার্তা লিখুন",
                    value="প্রিয় অভিভাবক, আপনার সন্তানের ফি বকেয়া রয়েছে। অনুগ্রহ করে পরিশোধ করুন।",
                    height=100
                )
                char_count = len(custom_msg)
                sms_count  = (char_count // 160) + 1
                st.caption(f"অক্ষর সংখ্যা: {char_count} | SMS সংখ্যা: {sms_count} | মোট SMS: {sms_count * len(sms_list)}")
                if st.form_submit_button("📤 SMS পাঠান (Gateway প্রয়োজন)", type="primary"):
                    alert(
                        "SMS Gateway কনফিগার না থাকায় পাঠানো সম্ভব হয়নি। "
                        ".streamlit/secrets.toml এ SMS_API_KEY যোগ করুন।",
                        "warning"
                    )

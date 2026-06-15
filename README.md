# 🕌 Smart Madrasa ERP — v2.0.0

আধুনিক মাল্টি-টেন্যান্ট SaaS মাদ্রাসা ম্যানেজমেন্ট সিস্টেম।

---

## ✅ সম্পূর্ণ মডিউল তালিকা (১৫টি ফাইল)

| # | ফাইল | মডিউল | বিবরণ |
|---|---|---|---|
| 1 | `app.py` | এন্ট্রি পয়েন্ট | Auth gate, sidebar nav, route dispatch |
| 2 | `auth.py` | লগইন | Multi-tenant login, RBAC, user management |
| 3 | `db.py` | ডেটাবেস | Schema bootstrap, helpers |
| 4 | `utils.py` | UI থিম | CSS system, KPI tiles, components |
| 5 | `dashboard.py` | ড্যাশবোর্ড | KPI, charts, activity feed |
| 6 | `admission_module.py` | ভর্তি | Multi-step form, admin approval |
| 7 | `finance_module.py` | ফি | Voucher, collection, ledger |
| 8 | `academic_module.py` | পরীক্ষা | Marks, result, marksheet |
| 9 | `attendance_module.py` | উপস্থিতি | Roll call, bulk, monthly |
| 10 | `teacher_module.py` | শিক্ষক | Profile, assignment, salary |
| 11 | `reports_module.py` | রিপোর্ট | Defaulters, analytics, CSV |
| 12 | `notice_module.py` | নোটিশ | Board, notifications, SMS |
| 13 | `student_portal.py` | ছাত্র পোর্টাল | Fee, academics, due alerts |
| 14 | `settings_module.py` | সেটিংস | Profile, sessions, classes |
| 15 | `seed_demo.py` | ডেমো ডেটা | Realistic sample seeder |

---

## 🚀 দ্রুত শুরু

```bash
# ১। ইনস্টল
pip install -r requirements.txt

# ২। DB সেটআপ
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# DATABASE_URL বসান

# ৩। ডেমো ডেটা (ঐচ্ছিক)
python seed_demo.py

# ৪। চালু করুন
streamlit run app.py
```

**লগইন:** `admin` / `admin123`

---

## 🔐 Role-Based Access

| Role | অ্যাক্সেস |
|---|---|
| **Admin** | সব মডিউল |
| **Staff** | Dashboard, Admissions, Finance, Attendance, Notice |
| **Teacher** | Dashboard, Academics, Attendance, Notice, Portal |
| **Accountant** | Dashboard, Finance, Reports, Portal |

---

## 🗄️ ডেটাবেস টেবিল (১৮টি)

tenants · academic_sessions · classes · students · student_enrollments · fee_vouchers · fee_payments · subjects · exams · marks_distribution · student_marks · attendance · teachers · teacher_assignments · teacher_salary · notices · notifications · app_users

---

## 💡 ডিজাইন নীতি

- **৩-ক্লিক নিয়ম** — প্রতিটি কাজ সর্বোচ্চ ৩ ক্লিকে
- **Tenant Isolation** — প্রতিটি SQL-এ `tenant_id` বাধ্যতামূলক
- **Atomic Transactions** — commit/rollback গ্যারান্টি
- **Parameterized SQL** — SQL Injection সুরক্ষা

*Smart Madrasa ERP — আধুনিক প্রযুক্তিতে ইসলামী শিক্ষা পরিচালনা 🕌*

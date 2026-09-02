import sqlite3
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import sys

DB_NAME = 'office_data.db'

# -------------------------------------------------------------------
# 1. DATABASE CLEANUP
# -------------------------------------------------------------------
def clean_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = OFF;")
    c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    for (name,) in c.fetchall():
        try: c.execute(f"DROP TRIGGER IF EXISTS {name}")
        except: pass
    c.execute("SELECT name FROM sqlite_master WHERE type='view'")
    for (name,) in c.fetchall():
        try: c.execute(f"DROP VIEW IF EXISTS {name}")
        except: pass
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'")
    for (name,) in c.fetchall():
        try: c.execute(f"DROP TABLE IF EXISTS {name}")
        except: pass
    c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    for (name,) in c.fetchall():
        try: c.execute(f"DROP INDEX IF EXISTS {name}")
        except: pass
    tables = [
        'employees', 'clients', 'bookings', 'collections', 'chq_register',
        'conveyance', 'salary', 'car_requisition', 'deed_movement',
        'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery'
    ]
    for t in tables:
        try: c.execute(f"DROP TABLE IF EXISTS {t}")
        except: pass
    conn.commit()
    c.execute("PRAGMA foreign_keys = ON;")
    conn.close()
    print("✅ Database cleanup complete.\n")

# -------------------------------------------------------------------
# 2. CREATE ALL TABLES (NO UNIQUE CONSTRAINTS)
# -------------------------------------------------------------------
def create_tables():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        emp_id TEXT, name TEXT, designation TEXT, team TEXT,
        joining_date TEXT, office_contact TEXT, personal_contact TEXT,
        dob TEXT, blood_group TEXT, present_address TEXT,
        permanent_address TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        name TEXT, contact TEXT, project TEXT, unit_plot TEXT,
        sale_value REAL, booking_date TEXT)''')
    c.execute('''CREATE TABLE bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        file_no TEXT, sales_person_id INTEGER, client_id INTEGER,
        project TEXT, unit_plot TEXT, sale_value REAL,
        soled_date TEXT, dp_commited REAL, dp_received REAL,
        next_pay_date TEXT, next_pay_amount REAL, booking_date TEXT,
        emi_start TEXT, monthly_emi REAL, last_paid_date TEXT,
        paid_month TEXT, next_installment_date TEXT,
        next_followup_date TEXT, total_due_inst INTEGER,
        total_due_taka REAL, special_instruction TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        mr_no TEXT, sales_person_id INTEGER, client_name TEXT,
        project TEXT, collection_date TEXT, unit INTEGER,
        mr_type TEXT, cash REAL, dd_ft_online REAL,
        clear_cheque REAL, advance_cheque REAL,
        dishonour_cheque REAL, cheque_status TEXT)''')
    c.execute('''CREATE TABLE chq_register (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        mr_no TEXT, collection_date TEXT, sales_person TEXT,
        client_name TEXT, project TEXT, unit_katha TEXT,
        mr_type TEXT, amount REAL, bank TEXT, cheque_no TEXT,
        cheque_status TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE conveyance (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        bill_date TEXT, employee TEXT, billing_duration TEXT,
        amount REAL, receiver_sign TEXT, purpose TEXT,
        client_name TEXT, meeting_loc TEXT, contact_number TEXT,
        remarks TEXT, type TEXT DEFAULT 'Regular')''')
    c.execute('''CREATE TABLE salary (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        month TEXT, employee TEXT, joining_date TEXT, od INTEGER,
        gross_salary REAL, payable_salary REAL, paid_taka REAL,
        due_salary REAL, designation TEXT)''')
    c.execute('''CREATE TABLE car_requisition (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        visit_date TEXT, employee TEXT, time TEXT, purpose TEXT,
        client_name TEXT, occupation TEXT, vehicle TEXT,
        from_place TEXT, pick_drop_via TEXT, to_project TEXT,
        visit_output TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE deed_movement (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        file_no TEXT, sales_person TEXT, client_name TEXT,
        project TEXT, unit_plot TEXT, deed_status TEXT,
        received_by TEXT, delivered_to TEXT, signature_pnr TEXT,
        delivery_date TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE token_money (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        mr_no TEXT, sales_person TEXT, client_name TEXT,
        project TEXT, collection_date TEXT, unit_plot TEXT,
        mr_type TEXT, cash REAL, dd_ft_online REAL,
        clear_cheque REAL, advance_cheque REAL,
        dishonour_cheque REAL, cheque_status TEXT)''')
    c.execute('''CREATE TABLE courier (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        date TEXT, sender_name TEXT, batch_team TEXT,
        client_name TEXT, address TEXT, contact_number TEXT,
        courier_name TEXT, cn_number TEXT, courier_charge REAL,
        remarks TEXT)''')
    c.execute('''CREATE TABLE hotel_reservation (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        issue_date TEXT, sales_person TEXT, client_name TEXT,
        client_contact TEXT, arrival_date TEXT, departure_date TEXT,
        total_nights INTEGER, no_of_rooms INTEGER, adults INTEGER,
        children INTEGER, complimentary TEXT, project TEXT,
        unit_katha TEXT, expected_collection REAL,
        soled_unit_katha TEXT, soled_date TEXT,
        realized_amount REAL, recommended_by TEXT,
        approved_by TEXT, remarks TEXT)''')
    c.execute('''CREATE TABLE gift_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        gift_date TEXT, sales_person TEXT, designation TEXT,
        client_name TEXT, project TEXT, unit_katha TEXT,
        sale_value REAL, expected_amount REAL, realize_date TEXT,
        item_name TEXT, size TEXT, gift_value REAL, remarks TEXT)''')
    c.execute('''CREATE TABLE mr_delivery (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_sheet TEXT,
        mr_no TEXT, client_name TEXT, project TEXT, issue_date TEXT,
        payment_type TEXT, amount REAL, received_by TEXT,
        receiver_signature TEXT, received_date TEXT)''')
    conn.commit()
    conn.close()
    print("All 14 tables created (no UNIQUE constraints).\n")

# -------------------------------------------------------------------
# 3. FTS VIRTUAL TABLES (NO triggers)
# -------------------------------------------------------------------
def create_fts_tables():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS collections_fts")
    c.execute("DROP TABLE IF EXISTS employees_fts")
    c.execute("DROP TABLE IF EXISTS clients_fts")
    c.execute("DROP TABLE IF EXISTS bookings_fts")
    c.execute('''CREATE VIRTUAL TABLE collections_fts USING fts5(
        mr_no, client_name, project, sales_person_name)''')
    c.execute('''CREATE VIRTUAL TABLE employees_fts USING fts5(
        name, designation, team)''')
    c.execute('''CREATE VIRTUAL TABLE clients_fts USING fts5(
        name, project, contact)''')
    c.execute('''CREATE VIRTUAL TABLE bookings_fts USING fts5(
        file_no, project, client_name)''')
    conn.commit()
    conn.close()
    print("FTS virtual tables created (no triggers).\n")

# -------------------------------------------------------------------
# 4. REBUILD FTS
# -------------------------------------------------------------------
def rebuild_fts():
    print("Rebuilding FTS indexes...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM collections_fts")
    c.execute("DELETE FROM employees_fts")
    c.execute("DELETE FROM clients_fts")
    c.execute("DELETE FROM bookings_fts")
    c.execute('''INSERT INTO collections_fts(rowid, mr_no, client_name, project, sales_person_name)
        SELECT c.id, c.mr_no, c.client_name, c.project, e.name
        FROM collections c LEFT JOIN employees e ON c.sales_person_id = e.id''')
    print(f"  collections_fts: {c.rowcount} rows")
    c.execute('''INSERT INTO employees_fts(rowid, name, designation, team)
        SELECT id, name, designation, team FROM employees''')
    print(f"  employees_fts: {c.rowcount} rows")
    c.execute('''INSERT INTO clients_fts(rowid, name, project, contact)
        SELECT id, name, project, contact FROM clients''')
    print(f"  clients_fts: {c.rowcount} rows")
    c.execute('''INSERT INTO bookings_fts(rowid, file_no, project, client_name)
        SELECT b.id, b.file_no, b.project, c.name
        FROM bookings b LEFT JOIN clients c ON b.client_id = c.id''')
    print(f"  bookings_fts: {c.rowcount} rows")
    conn.commit()
    conn.close()
    print("✅ FTS indexes rebuilt.\n")

# -------------------------------------------------------------------
# 5. HELPER FUNCTIONS
# -------------------------------------------------------------------
def safe_float(val):
    if val is None: return None
    if isinstance(val, (list, pd.Series)):
        if len(val) == 0: return None
        val = val[0] if isinstance(val, list) else val.iloc[0]
    if pd.isna(val): return None
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r'[^\d.]', '', val.strip())
        if cleaned == '': return None
        try: return float(cleaned)
        except: return None
    return None

def safe_int(val):
    if val is None: return None
    if isinstance(val, (list, pd.Series)):
        if len(val) == 0: return None
        val = val[0] if isinstance(val, list) else val.iloc[0]
    if pd.isna(val): return None
    if isinstance(val, (int, float)): return int(val)
    if isinstance(val, str):
        cleaned = re.sub(r'[^\d]', '', val.strip())
        if cleaned == '': return None
        try: return int(cleaned)
        except: return None
    return None

def safe_str(val):
    if val is None: return None
    if isinstance(val, (list, pd.Series)):
        if len(val) == 0: return None
        val = val[0] if isinstance(val, list) else val.iloc[0]
    if pd.isna(val): return None
    s = str(val).strip()
    return s if s != '' else None

def clean_mr_no(val):
    s = safe_str(val)
    if not s: return None
    if '.' in s:
        try: return str(int(float(s)))
        except: return s
    return s

def robust_date_conversion(series):
    def convert_cell(val):
        if val is None: return None
        if isinstance(val, (list, pd.Series)):
            if len(val) == 0: return None
            val = val[0] if isinstance(val, list) else val.iloc[0]
        if pd.isna(val): return None
        if isinstance(val, (datetime, pd.Timestamp)): return val.strftime('%Y-%m-%d')
        if isinstance(val, (int, float)):
            if 30000 < val < 60000:
                try:
                    dt = datetime(1899, 12, 30) + timedelta(days=val)
                    return dt.strftime('%Y-%m-%d')
                except: pass
            return None
        if isinstance(val, str):
            s = val.strip()
            if s == '': return None
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y',
                        '%d/%m/%y', '%m/%d/%y', '%d-%b-%Y', '%d-%b-%y',
                        '%b %d, %Y', '%d %b %Y', '%d.%m.%Y', '%d.%m.%y']:
                try:
                    dt = datetime.strptime(s, fmt)
                    return dt.strftime('%Y-%m-%d')
                except: continue
            try:
                dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
                if pd.notna(dt): return dt.strftime('%Y-%m-%d')
            except: pass
        return None
    result = series.apply(convert_cell)
    result = result.where(pd.notna(result), None)
    return result

def find_header_row_robust(df_raw, keywords, skip_rows=0):
    keyword_set = set([kw.lower() for kw in keywords])
    for idx in range(skip_rows, len(df_raw)):
        row = df_raw.iloc[idx]
        row_str = ' '.join([str(v).lower() for v in row if pd.notna(v)])
        if any(k in row_str for k in ['one city developers', 'commercial cove', 'ocdl sales']):
            continue
        match_count = sum(1 for kw in keyword_set if kw in row_str)
        if match_count >= 2:   # 3 থেকে 2 করা হয়েছে – হেডার সহজে পেতে
            return idx
    max_non_empty = 0
    best = 0
    for idx, row in df_raw.iterrows():
        non_empty = sum(1 for v in row if pd.notna(v) and str(v).strip() != '')
        if non_empty > max_non_empty:
            max_non_empty = non_empty
            best = idx
    return best

def match_sales_person(cursor, name):
    if not name: return None
    name_clean = re.sub(r'[\(\)\.]', '', name).strip().replace('  ', ' ')
    cursor.execute("SELECT id, name FROM employees")
    for emp_id, emp_name in cursor.fetchall():
        emp_clean = re.sub(r'[\(\)\.]', '', emp_name).strip().replace('  ', ' ')
        if emp_clean.lower() == name_clean.lower():
            return emp_id
    parts = name_clean.split()
    if len(parts) >= 2:
        first, last = parts[0].lower(), parts[-1].lower()
        cursor.execute("SELECT id, name FROM employees")
        for emp_id, emp_name in cursor.fetchall():
            emp_parts = re.sub(r'[\(\)\.]', '', emp_name).strip().split()
            if len(emp_parts) >= 2 and emp_parts[0].lower() == first and emp_parts[-1].lower() == last:
                return emp_id
    return None

# -------------------------------------------------------------------
# 6. IMPORT FUNCTIONS (ALL FIXED WITH CORRECT skip_rows)
# -------------------------------------------------------------------
def import_employees():
    print("Importing Employees...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Employee Book.xlsx'
    xl = pd.ExcelFile(file_path)
    generic_mapping = {
        'sl': 'sl', 'team': 'team', 'name': 'name',
        'designation': 'designation', 'emp id': 'emp_id',
        'office contact': 'office_contact', 'personal cont': 'personal_contact',
        'joining date': 'joining_date', 'doj': 'joining_date',
        'dob': 'dob', 'blood group': 'blood_group',
        'present address': 'present_address', 'permanent address': 'permanent_address',
        'remarks': 'remarks'
    }
    total_count = 0
    sheet_skip = {
        'Branch Batch Plan': 6, 'Current Manpower': 5, 'Mobile Recharge Sheet': 7,
        'Total Manpower': 5, '6 Month Eid Bonus': 5, 'Others Attendance Bonus': 6,
        'Attendance Bonus': 5, 'Iftar List': 5
    }
    for sheet in xl.sheet_names:
        if sheet == 'Sheet1': continue
        skip = sheet_skip.get(sheet, 0)
        df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=20)
        keywords = ['sl', 'name', 'designation', 'emp', 'id', 'office', 'contact', 'joining', 'date']
        hdr = find_header_row_robust(df_raw, keywords, skip_rows=skip)
        if hdr is None:
            print(f"  {sheet}: Header not found, skipping.")
            continue
        df = pd.read_excel(file_path, sheet_name=sheet, header=hdr)
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in generic_mapping:
                renamed[col] = generic_mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(generic_mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        else: continue
        for col in ['joining_date', 'dob']:
            if col in df.columns: df[col] = robust_date_conversion(df[col])
        count = 0
        dup_counter = {}
        for _, row in df.iterrows():
            name = safe_str(row.get('name'))
            if not name: continue
            emp_id = safe_str(row.get('emp_id'))
            if emp_id:
                if emp_id in dup_counter:
                    dup_counter[emp_id] += 1
                    emp_id = f"{emp_id}-dup-{dup_counter[emp_id]}"
                else:
                    dup_counter[emp_id] = 0
            else:
                emp_id = f"AUTO-{sheet}-{count+1}"
            c.execute('''INSERT INTO employees
                (source_sheet, emp_id, name, designation, team, joining_date, office_contact,
                 personal_contact, dob, blood_group, present_address, permanent_address)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (sheet, emp_id, name, safe_str(row.get('designation')),
                 safe_str(row.get('team')), row.get('joining_date'),
                 safe_str(row.get('office_contact')), safe_str(row.get('personal_contact')),
                 row.get('dob'), safe_str(row.get('blood_group')),
                 safe_str(row.get('present_address')), safe_str(row.get('permanent_address'))))
            count += 1
        conn.commit()
        print(f"  {sheet}: {count} employees")
        total_count += count
    conn.close()
    print(f"✅ Employees total: {total_count}\n")

def import_clients_and_bookings():
    print("Importing Clients and Bookings...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    def get_or_create_client(sheet, name, contact, project, unit_plot, sale_value, booking_date):
        name = safe_str(name)
        contact = safe_str(contact) or ''
        if not name: return None
        c.execute('SELECT id FROM clients WHERE name=? AND contact=?', (name, contact))
        row = c.fetchone()
        if row: return row[0]
        c.execute('''INSERT INTO clients
            (source_sheet, name, contact, project, unit_plot, sale_value, booking_date)
            VALUES (?,?,?,?,?,?,?)''',
            (sheet, name, contact, safe_str(project), safe_str(unit_plot),
             safe_float(sale_value), robust_date_conversion(pd.Series([booking_date]))[0] if booking_date else None))
        conn.commit()
        c.execute('SELECT id FROM clients WHERE name=? AND contact=?', (name, contact))
        row = c.fetchone()
        return row[0] if row else None

    # EMI Track
    file_path = 'data/EMI Track Book & Details.xlsx'
    xl = pd.ExcelFile(file_path)
    sheet = xl.sheet_names[0]
    df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=15)
    hdr = find_header_row_robust(df_raw, ['file no', 'client name', 'sales person', 'project', 'unit', 'sale value'], skip_rows=5)
    if hdr is not None:
        df = pd.read_excel(file_path, sheet_name=sheet, header=hdr)
        mapping = {'sl':'sl','file_no':'file_no','sales_person':'sales_person',
                   'client_name':'client_name','contact':'contact','project':'project',
                   'unit_plot':'unit_plot','unit/plot':'unit_plot','sale_value':'sale_value',
                   'booking_date':'booking_date','emi_start':'emi_start',
                   'monthly_emi':'monthly_emi','last_paid_date':'last_paid_date',
                   'paid_month':'paid_month','next_installment_date':'next_installment_date',
                   'next_followup_date':'next_followup_date','total_due_inst':'total_due_inst',
                   'total_due_taka':'total_due_taka','remarks':'remarks'}
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping: renamed[col] = mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        if 'client_name' in df.columns: df = df.dropna(subset=['client_name'], how='all')
        if not df.empty:
            for idx, row in df.iterrows():
                client_name = safe_str(row.get('client_name'))
                if not client_name: continue
                client_id = get_or_create_client(sheet, client_name, row.get('contact'),
                    row.get('project'), row.get('unit_plot'), row.get('sale_value'),
                    row.get('booking_date'))
                if not client_id: continue
                file_no = safe_str(row.get('file_no'))
                if not file_no: file_no = f"AUTO-{client_id}-{idx}"
                c.execute('''INSERT INTO bookings
                    (source_sheet, file_no, client_id, project, unit_plot, sale_value,
                     booking_date, emi_start, monthly_emi, last_paid_date, paid_month,
                     next_installment_date, next_followup_date, total_due_inst, total_due_taka, remarks)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (sheet, file_no, client_id, safe_str(row.get('project')),
                     safe_str(row.get('unit_plot')), safe_float(row.get('sale_value')),
                     robust_date_conversion(pd.Series([row.get('booking_date')]))[0] if row.get('booking_date') else None,
                     robust_date_conversion(pd.Series([row.get('emi_start')]))[0] if row.get('emi_start') else None,
                     safe_float(row.get('monthly_emi')),
                     robust_date_conversion(pd.Series([row.get('last_paid_date')]))[0] if row.get('last_paid_date') else None,
                     safe_str(row.get('paid_month')),
                     robust_date_conversion(pd.Series([row.get('next_installment_date')]))[0] if row.get('next_installment_date') else None,
                     robust_date_conversion(pd.Series([row.get('next_followup_date')]))[0] if row.get('next_followup_date') else None,
                     safe_int(row.get('total_due_inst')), safe_float(row.get('total_due_taka')),
                     safe_str(row.get('remarks'))))
            conn.commit()

    # Client Ledger
    file_path2 = 'data/Client Ledger and Booking Details OCDL Sales.xlsx'
    xl2 = pd.ExcelFile(file_path2)
    sheet2 = xl2.sheet_names[0]
    df_raw2 = pd.read_excel(file_path2, sheet_name=sheet2, header=None, nrows=15)
    hdr2 = find_header_row_robust(df_raw2, ['file no', 'client name', 'sales person', 'project', 'unit', 'sale value'], skip_rows=6)
    if hdr2 is not None:
        df2 = pd.read_excel(file_path2, sheet_name=sheet2, header=hdr2)
        mapping2 = {'sl':'sl','file_no':'file_no','sales_person':'sales_person',
                    'client_name':'client_name','contact':'contact','project':'project',
                    'unit_plot':'unit_plot','unit/plot':'unit_plot','sale_value':'sale_value',
                    'soled_date':'soled_date','dp_commited':'dp_commited',
                    'dp_received':'dp_received','next_pay_date':'next_pay_date',
                    'next_pay_amount':'next_pay_amount','booking_date':'booking_date',
                    'emi_start':'emi_start','monthly_emi':'monthly_emi',
                    'last_paid_date':'last_paid_date','special_instruction':'special_instruction',
                    'remarks':'remarks'}
        renamed2 = {}
        for col in df2.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping2: renamed2[col] = mapping2[norm]
        if renamed2:
            df2 = df2.rename(columns=renamed2)
            keep2 = list(mapping2.values())
            existing2 = [c for c in keep2 if c in df2.columns]
            df2 = df2[existing2]
            df2 = df2.loc[:, ~df2.columns.duplicated()]
        if 'client_name' in df2.columns: df2 = df2.dropna(subset=['client_name'], how='all')
        if not df2.empty:
            file_dup_counter = {}
            for _, row in df2.iterrows():
                file_no = safe_str(row.get('file_no'))
                if not file_no: continue
                if file_no in file_dup_counter:
                    file_dup_counter[file_no] += 1
                    file_no = f"{file_no}-dup-{file_dup_counter[file_no]}"
                else:
                    file_dup_counter[file_no] = 0
                client_name = safe_str(row.get('client_name'))
                contact = safe_str(row.get('contact'))
                client_id = get_or_create_client(sheet2, client_name, contact,
                    row.get('project'), row.get('unit_plot'), row.get('sale_value'),
                    row.get('booking_date'))
                if not client_id: continue
                c.execute('SELECT id FROM bookings WHERE file_no=?', (file_no,))
                existing = c.fetchone()
                if not existing:
                    c.execute('''INSERT INTO bookings
                        (source_sheet, file_no, client_id, project, unit_plot, sale_value,
                         soled_date, dp_commited, dp_received, next_pay_date, next_pay_amount,
                         booking_date, emi_start, monthly_emi, last_paid_date,
                         special_instruction, remarks)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (sheet2, file_no, client_id, safe_str(row.get('project')),
                         safe_str(row.get('unit_plot')), safe_float(row.get('sale_value')),
                         robust_date_conversion(pd.Series([row.get('soled_date')]))[0] if row.get('soled_date') else None,
                         safe_float(row.get('dp_commited')), safe_float(row.get('dp_received')),
                         robust_date_conversion(pd.Series([row.get('next_pay_date')]))[0] if row.get('next_pay_date') else None,
                         safe_float(row.get('next_pay_amount')),
                         robust_date_conversion(pd.Series([row.get('booking_date')]))[0] if row.get('booking_date') else None,
                         robust_date_conversion(pd.Series([row.get('emi_start')]))[0] if row.get('emi_start') else None,
                         safe_float(row.get('monthly_emi')),
                         robust_date_conversion(pd.Series([row.get('last_paid_date')]))[0] if row.get('last_paid_date') else None,
                         safe_str(row.get('special_instruction')), safe_str(row.get('remarks'))))
                else:
                    updates = []
                    vals = []
                    for col, field in [('soled_date','soled_date'), ('dp_commited','dp_commited'),
                                       ('dp_received','dp_received'), ('next_pay_date','next_pay_date'),
                                       ('next_pay_amount','next_pay_amount'),
                                       ('special_instruction','special_instruction')]:
                        val = row.get(col)
                        if val is not None and not pd.isna(val):
                            updates.append(f"{field}=?")
                            if field in ['soled_date', 'next_pay_date']:
                                vals.append(robust_date_conversion(pd.Series([val]))[0])
                            else:
                                vals.append(safe_float(val))
                    if updates:
                        vals.append(file_no)
                        c.execute(f"UPDATE bookings SET {', '.join(updates)} WHERE file_no=?", vals)
            conn.commit()
    conn.close()
    print("✅ Clients and bookings imported.\n")

def import_collections():
    print("Importing Collections...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/MR Reg & Sales Collection Report.xlsx'
    xl = pd.ExcelFile(file_path)
    keyword_sets = [
        ['MR No', 'Sales Person', 'Clients Name'],
        ['MR No', 'Sales Person', 'Client Name'],
        ['SL', 'Office', 'MR Book', 'Batch', 'MR No'],
        ['SL', 'Office', 'Batch', 'MR No', 'Sales Person']
    ]
    total_count = 0
    for sheet in xl.sheet_names:
        if not (sheet.startswith('MR Register') or sheet.startswith('Sales & Installment')):
            continue
        print(f"  Processing {sheet}...")
        df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=15)
        hdr = None
        for kw in keyword_sets:
            hdr = find_header_row_robust(df_raw, kw, skip_rows=0)
            if hdr is not None: break
        if hdr is None:
            print(f"    Header not found, skipping.")
            continue
        df = pd.read_excel(file_path, sheet_name=sheet, header=hdr)
        mapping = {
            'sl':'sl','office':'office','mr_book':'mr_book',
            'batch':'batch','group':'batch',
            'mr_no':'mr_no','sales_person':'sales_person',
            'client_name':'client_name','clients_name':'client_name',
            'project':'project',
            'collection_date':'collection_date','collection\ndate':'collection_date',
            'unit_plot':'unit','unit':'unit',
            'mr_type':'mr_type','cash':'cash','dd_ft_online':'dd_ft_online',
            'clear_cheque':'clear_cheque','advance_cheque':'advance_cheque',
            'dishonour_cheque':'dishonour_cheque','cheque_status':'cheque_status',
            'chq_status':'cheque_status'
        }
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping: renamed[col] = mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        else:
            print(f"    No mapping, skipping.")
            continue
        if 'mr_no' not in df.columns:
            print(f"    No mr_no column, skipping.")
            continue
        print(f"    Total rows before processing: {len(df)}")
        if 'collection_date' in df.columns:
            df['collection_date'] = robust_date_conversion(df['collection_date'])
            df['collection_date'] = df['collection_date'].apply(lambda x: None if pd.isna(x) else x)
        count = 0
        dup_counter = {}
        for _, row in df.iterrows():
            mr_no = clean_mr_no(row.get('mr_no'))
            if not mr_no:
                mr_no = f"DMY-{sheet[:10]}-{count+1}"
            else:
                if mr_no in dup_counter:
                    dup_counter[mr_no] += 1
                    mr_no = f"{mr_no}-dup-{dup_counter[mr_no]}"
                else:
                    dup_counter[mr_no] = 0
            sales_name = safe_str(row.get('sales_person'))
            sales_person_id = match_sales_person(c, sales_name) if sales_name else None
            client_name = safe_str(row.get('client_name')) or ''
            coll_date = row.get('collection_date')
            if pd.isna(coll_date) or coll_date is None: coll_date = None
            c.execute('''INSERT INTO collections
                (source_sheet, mr_no, sales_person_id, client_name, project, collection_date,
                 unit, mr_type, cash, dd_ft_online, clear_cheque,
                 advance_cheque, dishonour_cheque, cheque_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (sheet, mr_no, sales_person_id, client_name,
                 safe_str(row.get('project')), coll_date,
                 safe_int(row.get('unit')), safe_str(row.get('mr_type')),
                 safe_float(row.get('cash')), safe_float(row.get('dd_ft_online')),
                 safe_float(row.get('clear_cheque')), safe_float(row.get('advance_cheque')),
                 safe_float(row.get('dishonour_cheque')), safe_str(row.get('cheque_status'))))
            count += 1
        conn.commit()
        print(f"    Imported {count} records")
        total_count += count
    print("\n  📊 SOURCE_SHEET DISTRIBUTION:")
    dist = c.execute("SELECT source_sheet, COUNT(*) FROM collections GROUP BY source_sheet ORDER BY COUNT(*) DESC").fetchall()
    for s, cnt in dist: print(f"      {s}: {cnt}")
    conn.close()
    print(f"✅ Collections total: {total_count}\n")

def import_chq_register():
    print("Importing CHQ Register...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/CHQ Book Register.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=15)
    hdr = find_header_row_robust(df_raw, ['sl', 'collection date', 'mr no', 'sales person'], skip_rows=1)
    if hdr is None: print("  Header not found."); conn.close(); return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','collection_date':'collection_date','mr_no':'mr_no',
               'sales_person':'sales_person','client_name':'client_name',
               'project':'project','unit_katha':'unit_katha','mr_type':'mr_type',
               'amount':'amount','bank':'bank','cheque_no':'cheque_no',
               'cheque_status':'cheque_status','remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty or 'mr_no' not in df.columns: print("  No data."); conn.close(); return
    if 'collection_date' in df.columns:
        df['collection_date'] = robust_date_conversion(df['collection_date'])
        df['collection_date'] = df['collection_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        mr_no = clean_mr_no(row.get('mr_no'))
        if not mr_no: continue
        coll_date = row.get('collection_date')
        if pd.isna(coll_date) or coll_date is None: coll_date = None
        c.execute('''INSERT INTO chq_register
            (source_sheet, mr_no, collection_date, sales_person, client_name, project,
             unit_katha, mr_type, amount, bank, cheque_no, cheque_status, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('CHQ Book Register', mr_no, coll_date,
             safe_str(row.get('sales_person')), safe_str(row.get('client_name')),
             safe_str(row.get('project')), safe_str(row.get('unit_katha')),
             safe_str(row.get('mr_type')), safe_float(row.get('amount')),
             safe_str(row.get('bank')), safe_str(row.get('cheque_no')),
             safe_str(row.get('cheque_status')), safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ CHQ Register total: {count}\n")

def import_conveyance():
    print("Importing Conveyance...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Conveyance Data Sheet.xlsx'
    total_count = 0

    # Regular sheet (skip_rows=5)
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=15)
    hdr = find_header_row_robust(df_raw, ['receive date', 'employee', 'billing duration', 'taka'], skip_rows=5)
    if hdr is not None:
        df = pd.read_excel(file_path, sheet_name=0, header=hdr)
        mapping = {'receive_date':'receive_date','employee':'employee',
                   'billing_duration':'billing_duration','amount':'amount',
                   'receiver_sign':'receiver_sign'}
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping: renamed[col] = mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        if not df.empty and 'employee' in df.columns:
            df = df.dropna(subset=['employee'], how='all')
            if 'receive_date' in df.columns:
                df['receive_date'] = robust_date_conversion(df['receive_date'])
                df['receive_date'] = df['receive_date'].apply(lambda x: None if pd.isna(x) else x)
            count = 0
            for _, row in df.iterrows():
                rec_date = row.get('receive_date')
                if pd.isna(rec_date) or rec_date is None: rec_date = None
                c.execute('''INSERT INTO conveyance
                    (source_sheet, bill_date, employee, billing_duration, amount, receiver_sign, type)
                    VALUES (?,?,?,?,?,?,'Regular')''',
                    ('Conveyance Payment', rec_date,
                     safe_str(row.get('employee')), safe_str(row.get('billing_duration')),
                     safe_float(row.get('amount')), safe_str(row.get('receiver_sign'))))
                count += 1
            conn.commit()
            print(f"  Regular: {count} records")
            total_count += count

    # Pending sheet (skip_rows=7)
    df_raw = pd.read_excel(file_path, sheet_name=1, header=None, nrows=15)
    hdr = find_header_row_robust(df_raw, ['sl', 'bill date', 'meeting date', 'employee', 'purpose'], skip_rows=7)
    if hdr is not None:
        df = pd.read_excel(file_path, sheet_name=1, header=hdr)
        mapping = {'sl':'sl','bill_date':'bill_date','meeting_date':'meeting_date',
                   'employee':'employee','purpose':'purpose','client_name':'client_name',
                   'meeting_loc':'meeting_loc','contact_number':'contact_number',
                   'amount':'amount','remarks':'remarks'}
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping: renamed[col] = mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        if not df.empty and 'employee' in df.columns:
            df = df.dropna(subset=['employee'], how='all')
            if 'bill_date' in df.columns:
                df['bill_date'] = robust_date_conversion(df['bill_date'])
                df['bill_date'] = df['bill_date'].apply(lambda x: None if pd.isna(x) else x)
            count = 0
            for _, row in df.iterrows():
                bill_date = row.get('bill_date')
                if pd.isna(bill_date) or bill_date is None: bill_date = None
                c.execute('''INSERT INTO conveyance
                    (source_sheet, bill_date, employee, purpose, client_name,
                     meeting_loc, contact_number, amount, remarks, type)
                    VALUES (?,?,?,?,?,?,?,?,?,'Pending')''',
                    ('Conveyance Pending', bill_date,
                     safe_str(row.get('employee')), safe_str(row.get('purpose')),
                     safe_str(row.get('client_name')), safe_str(row.get('meeting_loc')),
                     safe_str(row.get('contact_number')), safe_float(row.get('amount')),
                     safe_str(row.get('remarks'))))
                count += 1
            conn.commit()
            print(f"  Pending: {count} records")
            total_count += count

    # Office Duty sheets (skip_rows=7)
    for idx, name in enumerate(['Office Duty', 'Office Duty (2)']):
        try:
            df_raw = pd.read_excel(file_path, sheet_name=idx+2, header=None, nrows=15)
            hdr = find_header_row_robust(df_raw, ['sl', 'bill date', 'employee', 'purpose', 'client name'], skip_rows=7)
            if hdr is not None:
                df = pd.read_excel(file_path, sheet_name=idx+2, header=hdr)
                mapping = {'sl':'sl','bill_date':'bill_date','employee':'employee',
                           'purpose':'purpose','client_name':'client_name',
                           'meeting_loc':'meeting_loc','contact_number':'contact_number',
                           'amount':'amount','remarks':'remarks'}
                renamed = {}
                for col in df.columns:
                    norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
                    if norm in mapping: renamed[col] = mapping[norm]
                if renamed:
                    df = df.rename(columns=renamed)
                    keep = list(mapping.values())
                    existing = [c for c in keep if c in df.columns]
                    df = df[existing]
                    df = df.loc[:, ~df.columns.duplicated()]
                if not df.empty and 'employee' in df.columns:
                    df = df.dropna(subset=['employee'], how='all')
                    if 'bill_date' in df.columns:
                        df['bill_date'] = robust_date_conversion(df['bill_date'])
                        df['bill_date'] = df['bill_date'].apply(lambda x: None if pd.isna(x) else x)
                    count = 0
                    for _, row in df.iterrows():
                        bill_date = row.get('bill_date')
                        if pd.isna(bill_date) or bill_date is None: bill_date = None
                        c.execute('''INSERT INTO conveyance
                            (source_sheet, bill_date, employee, purpose, client_name,
                             meeting_loc, contact_number, amount, remarks, type)
                            VALUES (?,?,?,?,?,?,?,?,?,'Regular')''',
                            (name, bill_date, safe_str(row.get('employee')),
                             safe_str(row.get('purpose')), safe_str(row.get('client_name')),
                             safe_str(row.get('meeting_loc')), safe_str(row.get('contact_number')),
                             safe_float(row.get('amount')), safe_str(row.get('remarks'))))
                        count += 1
                    conn.commit()
                    print(f"  {name}: {count} records")
                    total_count += count
        except: pass
    conn.close()
    print(f"✅ Conveyance total: {total_count}\n")

def import_salary():
    print("Importing Salary...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Salary Book Land Office.xlsx'
    xl = pd.ExcelFile(file_path)
    months = ['Jul 26','Jun 26','May 26','Apr 26','Mar 26','Feb 26',
              'Jan 26','Dec 25','Nov 25','Oct 25','Sep 25','Aug 25',
              'July 25','June 25','May 25']
    mapping = {'sl':'sl','employee':'employee','joining_date':'joining_date',
               'od':'od','gross_salary':'gross_salary',
               'payable_salary':'payable_salary','paid_taka':'paid_taka',
               'due_salary':'due_salary','designation':'designation'}
    total_count = 0
    sheet_skip = {'Jul 26':5,'Jun 26':5,'May 26':5,'Apr 26':5,'Mar 26':5,
                  'Feb 26':5,'Jan 26':5,'Dec 25':5,'Nov 25':5,'Oct 25':5,
                  'Sep 25':4,'Aug 25':6,'July 25':7,'June 25':8,'May 25':8}
    for month in months:
        if month not in xl.sheet_names: continue
        skip = sheet_skip.get(month, 3)
        df_raw = pd.read_excel(file_path, sheet_name=month, header=None, nrows=15)
        hdr = find_header_row_robust(df_raw, ['sl', 'employee', 'joining', 'date', 'gross', 'salary'], skip_rows=skip)
        if hdr is None: continue
        df = pd.read_excel(file_path, sheet_name=month, header=hdr)
        renamed = {}
        for col in df.columns:
            norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
            if norm in mapping: renamed[col] = mapping[norm]
        if renamed:
            df = df.rename(columns=renamed)
            keep = list(mapping.values())
            existing = [c for c in keep if c in df.columns]
            df = df[existing]
            df = df.loc[:, ~df.columns.duplicated()]
        if df.empty: continue
        if 'employee' in df.columns: df = df.dropna(subset=['employee'], how='all')
        if 'joining_date' in df.columns:
            df['joining_date'] = robust_date_conversion(df['joining_date'])
            df['joining_date'] = df['joining_date'].apply(lambda x: None if pd.isna(x) else x)
        count = 0
        for _, row in df.iterrows():
            join_date = row.get('joining_date')
            if pd.isna(join_date) or join_date is None: join_date = None
            c.execute('''INSERT INTO salary
                (source_sheet, month, employee, joining_date, od, gross_salary,
                 payable_salary, paid_taka, due_salary, designation)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (month, month, safe_str(row.get('employee')), join_date,
                 safe_int(row.get('od')), safe_float(row.get('gross_salary')),
                 safe_float(row.get('payable_salary')), safe_float(row.get('paid_taka')),
                 safe_float(row.get('due_salary')), safe_str(row.get('designation'))))
            count += 1
        conn.commit()
        print(f"  {month}: {count} records")
        total_count += count
    conn.close()
    print(f"✅ Salary total: {total_count}\n")

def import_car_requisition():
    print("Importing Car Requisition...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Car Requisition Record.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=15)
    hdr = find_header_row_robust(df_raw, ['sl', 'visit date', 'employee', 'time', 'purpose'], skip_rows=4)
    if hdr is None: print("  Header not found."); conn.close(); return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','visit_date':'visit_date','employee':'employee',
               'time':'time','purpose':'purpose','client_name':'client_name',
               'occupation':'occupation','vehicle':'vehicle',
               'from_place':'from_place','pick_drop_via':'pick_drop_via',
               'to_project':'to_project','visit_output':'visit_output','remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'employee' in df.columns: df = df.dropna(subset=['employee'], how='all')
    if 'visit_date' in df.columns:
        df['visit_date'] = robust_date_conversion(df['visit_date'])
        df['visit_date'] = df['visit_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        visit_date = row.get('visit_date')
        if pd.isna(visit_date) or visit_date is None: visit_date = None
        c.execute('''INSERT INTO car_requisition
            (source_sheet, visit_date, employee, time, purpose, client_name,
             occupation, vehicle, from_place, pick_drop_via,
             to_project, visit_output, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('Car Requisition Record', visit_date,
             safe_str(row.get('employee')), safe_str(row.get('time')),
             safe_str(row.get('purpose')), safe_str(row.get('client_name')),
             safe_str(row.get('occupation')), safe_str(row.get('vehicle')),
             safe_str(row.get('from_place')), safe_str(row.get('pick_drop_via')),
             safe_str(row.get('to_project')), safe_str(row.get('visit_output')),
             safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Car requisition total: {count}\n")

# ========== FIXED FUNCTIONS FOR THE 6 TABLES ==========

def import_deed_movement():
    print("Importing Deed Movement...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Client Deed Movment Register.xlsx'
    # skip_rows এখন 5 (আগে ছিল 6)
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'file no', 'sales person', 'client name'], skip_rows=5)
    if hdr is None:
        print("  Header not found, trying skip_rows=4...")
        hdr = find_header_row_robust(df_raw, ['sl', 'file no', 'sales person', 'client name'], skip_rows=4)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','file_no':'file_no','sales_person':'sales_person',
               'client_name':'client_name','project':'project',
               'unit_plot':'unit_plot','deed_status':'deed_status',
               'received_by':'received_by','delivered_to':'delivered_to',
               'signature_pnr':'signature_pnr','delivery_date':'delivery_date',
               'remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'client_name' in df.columns: df = df.dropna(subset=['client_name'], how='all')
    if 'delivery_date' in df.columns:
        df['delivery_date'] = robust_date_conversion(df['delivery_date'])
        df['delivery_date'] = df['delivery_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        delivery_date = row.get('delivery_date')
        if pd.isna(delivery_date) or delivery_date is None: delivery_date = None
        c.execute('''INSERT INTO deed_movement
            (source_sheet, file_no, sales_person, client_name, project, unit_plot,
             deed_status, received_by, delivered_to, signature_pnr,
             delivery_date, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('Client Deed Movement Register', safe_str(row.get('file_no')),
             safe_str(row.get('sales_person')), safe_str(row.get('client_name')),
             safe_str(row.get('project')), safe_str(row.get('unit_plot')),
             safe_str(row.get('deed_status')), safe_str(row.get('received_by')),
             safe_str(row.get('delivered_to')), safe_str(row.get('signature_pnr')),
             delivery_date, safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Deed movement total: {count}\n")

def import_token_money():
    print("Importing Token Money...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Client Token Money Details.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'office', 'batch', 'mr no', 'sales person'], skip_rows=3)
    if hdr is None:
        print("  Header not found, trying skip_rows=2...")
        hdr = find_header_row_robust(df_raw, ['sl', 'office', 'batch', 'mr no', 'sales person'], skip_rows=2)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','office':'office','batch':'batch',
               'mr_no':'mr_no','sales_person':'sales_person',
               'client_name':'client_name','project':'project',
               'collection_date':'collection_date','unit_plot':'unit_plot',
               'mr_type':'mr_type','cash':'cash',
               'dd_ft_online':'dd_ft_online','clear_cheque':'clear_cheque',
               'advance_cheque':'advance_cheque','dishonour_cheque':'dishonour_cheque',
               'cheque_status':'cheque_status'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'collection_date' in df.columns:
        df['collection_date'] = robust_date_conversion(df['collection_date'])
        df['collection_date'] = df['collection_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        mr_no = clean_mr_no(row.get('mr_no'))
        if not mr_no: continue
        coll_date = row.get('collection_date')
        if pd.isna(coll_date) or coll_date is None: coll_date = None
        c.execute('''INSERT INTO token_money
            (source_sheet, mr_no, sales_person, client_name, project, collection_date,
             unit_plot, mr_type, cash, dd_ft_online, clear_cheque,
             advance_cheque, dishonour_cheque, cheque_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('Client Token Money Details', mr_no,
             safe_str(row.get('sales_person')), safe_str(row.get('client_name')),
             safe_str(row.get('project')), coll_date,
             safe_str(row.get('unit_plot')), safe_str(row.get('mr_type')),
             safe_float(row.get('cash')), safe_float(row.get('dd_ft_online')),
             safe_float(row.get('clear_cheque')), safe_float(row.get('advance_cheque')),
             safe_float(row.get('dishonour_cheque')), safe_str(row.get('cheque_status'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Token money total: {count}\n")

def import_courier():
    print("Importing Courier...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Postage & Courier Register.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'date', 'sender name', 'batch', 'team'], skip_rows=5)
    if hdr is None:
        print("  Header not found, trying skip_rows=4...")
        hdr = find_header_row_robust(df_raw, ['sl', 'date', 'sender name', 'batch', 'team'], skip_rows=4)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','date':'date','sender_name':'sender_name',
               'batch_team':'batch_team','client_name':'client_name',
               'address':'address','contact_number':'contact_number',
               'courier_name':'courier_name','cn_number':'cn_number',
               'courier_charge':'courier_charge','remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'sender_name' in df.columns: df = df.dropna(subset=['sender_name'], how='all')
    if 'date' in df.columns:
        df['date'] = robust_date_conversion(df['date'])
        df['date'] = df['date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        date_val = row.get('date')
        if pd.isna(date_val) or date_val is None: date_val = None
        c.execute('''INSERT INTO courier
            (source_sheet, date, sender_name, batch_team, client_name, address,
             contact_number, courier_name, cn_number, courier_charge, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            ('Postage & Courier Register', date_val,
             safe_str(row.get('sender_name')), safe_str(row.get('batch_team')),
             safe_str(row.get('client_name')), safe_str(row.get('address')),
             safe_str(row.get('contact_number')), safe_str(row.get('courier_name')),
             safe_str(row.get('cn_number')), safe_float(row.get('courier_charge')),
             safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Courier total: {count}\n")

def import_hotel_reservation():
    print("Importing Hotel Reservation...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Hotel Reservation Record Book.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'issue date', 'sales person', 'client name'], skip_rows=5)
    if hdr is None:
        print("  Header not found, trying skip_rows=4...")
        hdr = find_header_row_robust(df_raw, ['sl', 'issue date', 'sales person', 'client name'], skip_rows=4)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','issue_date':'issue_date','sales_person':'sales_person',
               'client_name':'client_name','client_contact':'client_contact',
               'arrival_date':'arrival_date','departure_date':'departure_date',
               'total_nights':'total_nights','no_of_rooms':'no_of_rooms',
               'adults':'adults','children':'children',
               'complimentary':'complimentary','project':'project',
               'unit_katha':'unit_katha','expected_collection':'expected_collection',
               'soled_unit_katha':'soled_unit_katha','soled_date':'soled_date',
               'realized_amount':'realized_amount','recommended_by':'recommended_by',
               'approved_by':'approved_by','remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'client_name' in df.columns: df = df.dropna(subset=['client_name'], how='all')
    date_cols = ['issue_date','arrival_date','departure_date','soled_date']
    for col in date_cols:
        if col in df.columns:
            df[col] = robust_date_conversion(df[col])
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        issue = row.get('issue_date'); arrival = row.get('arrival_date')
        departure = row.get('departure_date'); soled = row.get('soled_date')
        if pd.isna(issue) or issue is None: issue = None
        if pd.isna(arrival) or arrival is None: arrival = None
        if pd.isna(departure) or departure is None: departure = None
        if pd.isna(soled) or soled is None: soled = None
        c.execute('''INSERT INTO hotel_reservation
            (source_sheet, issue_date, sales_person, client_name, client_contact,
             arrival_date, departure_date, total_nights, no_of_rooms,
             adults, children, complimentary, project, unit_katha,
             expected_collection, soled_unit_katha, soled_date,
             realized_amount, recommended_by, approved_by, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('Hotel Reservation Record Book', issue,
             safe_str(row.get('sales_person')), safe_str(row.get('client_name')),
             safe_str(row.get('client_contact')), arrival, departure,
             safe_int(row.get('total_nights')), safe_int(row.get('no_of_rooms')),
             safe_int(row.get('adults')), safe_int(row.get('children')),
             safe_str(row.get('complimentary')), safe_str(row.get('project')),
             safe_str(row.get('unit_katha')), safe_float(row.get('expected_collection')),
             safe_str(row.get('soled_unit_katha')), soled,
             safe_float(row.get('realized_amount')), safe_str(row.get('recommended_by')),
             safe_str(row.get('approved_by')), safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Hotel reservation total: {count}\n")

def import_gift_ledger():
    print("Importing Gift Ledger...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Client Gift Ledger.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'gift handover date', 'sales person', 'client name'], skip_rows=4)
    if hdr is None:
        print("  Header not found, trying skip_rows=3...")
        hdr = find_header_row_robust(df_raw, ['sl', 'gift handover date', 'sales person', 'client name'], skip_rows=3)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','gift_date':'gift_date',
               'sales_person':'sales_person','designation':'designation',
               'client_name':'client_name','project':'project',
               'unit_katha':'unit_katha','sale_value':'sale_value',
               'expected_amount':'expected_amount',
               'realize_date':'realize_date','item_name':'item_name',
               'size':'size','gift_value':'gift_value','remarks':'remarks'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'client_name' in df.columns: df = df.dropna(subset=['client_name'], how='all')
    if 'gift_date' in df.columns:
        df['gift_date'] = robust_date_conversion(df['gift_date'])
        df['gift_date'] = df['gift_date'].apply(lambda x: None if pd.isna(x) else x)
    if 'realize_date' in df.columns:
        df['realize_date'] = robust_date_conversion(df['realize_date'])
        df['realize_date'] = df['realize_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        gift_d = row.get('gift_date'); real_d = row.get('realize_date')
        if pd.isna(gift_d) or gift_d is None: gift_d = None
        if pd.isna(real_d) or real_d is None: real_d = None
        c.execute('''INSERT INTO gift_ledger
            (source_sheet, gift_date, sales_person, designation, client_name, project,
             unit_katha, sale_value, expected_amount, realize_date,
             item_name, size, gift_value, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('Client Gift Ledger', gift_d,
             safe_str(row.get('sales_person')), safe_str(row.get('designation')),
             safe_str(row.get('client_name')), safe_str(row.get('project')),
             safe_str(row.get('unit_katha')), safe_float(row.get('sale_value')),
             safe_float(row.get('expected_amount')), real_d,
             safe_str(row.get('item_name')), safe_str(row.get('size')),
             safe_float(row.get('gift_value')), safe_str(row.get('remarks'))))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ Gift ledger total: {count}\n")

def import_mr_delivery():
    print("Importing MR Delivery...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    file_path = 'data/Client MR Delivery Register.xlsx'
    df_raw = pd.read_excel(file_path, sheet_name=0, header=None, nrows=20)
    hdr = find_header_row_robust(df_raw, ['sl', 'mr no', 'client name', 'project'], skip_rows=5)
    if hdr is None:
        print("  Header not found, trying skip_rows=4...")
        hdr = find_header_row_robust(df_raw, ['sl', 'mr no', 'client name', 'project'], skip_rows=4)
    if hdr is None:
        print("  Header not found, skipping.")
        conn.close()
        return
    df = pd.read_excel(file_path, sheet_name=0, header=hdr)
    mapping = {'sl':'sl','mr_no':'mr_no','client_name':'client_name',
               'project':'project','issue_date':'issue_date',
               'payment_type':'payment_type','amount':'amount',
               'received_by':'received_by','receiver_signature':'receiver_signature',
               'received_date':'received_date'}
    renamed = {}
    for col in df.columns:
        norm = str(col).strip().lower().replace(' ', '_').replace(':', '')
        if norm in mapping: renamed[col] = mapping[norm]
    if renamed:
        df = df.rename(columns=renamed)
        keep = list(mapping.values())
        existing = [c for c in keep if c in df.columns]
        df = df[existing]
        df = df.loc[:, ~df.columns.duplicated()]
    if df.empty: print("  No data."); conn.close(); return
    if 'issue_date' in df.columns:
        df['issue_date'] = robust_date_conversion(df['issue_date'])
        df['issue_date'] = df['issue_date'].apply(lambda x: None if pd.isna(x) else x)
    if 'received_date' in df.columns:
        df['received_date'] = robust_date_conversion(df['received_date'])
        df['received_date'] = df['received_date'].apply(lambda x: None if pd.isna(x) else x)
    count = 0
    for _, row in df.iterrows():
        mr_no = clean_mr_no(row.get('mr_no'))
        if not mr_no: continue
        issue = row.get('issue_date'); received = row.get('received_date')
        if pd.isna(issue) or issue is None: issue = None
        if pd.isna(received) or received is None: received = None
        c.execute('''INSERT INTO mr_delivery
            (source_sheet, mr_no, client_name, project, issue_date, payment_type,
             amount, received_by, receiver_signature, received_date)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            ('Client MR Delivery Register', mr_no,
             safe_str(row.get('client_name')), safe_str(row.get('project')),
             issue, safe_str(row.get('payment_type')),
             safe_float(row.get('amount')), safe_str(row.get('received_by')),
             safe_str(row.get('receiver_signature')), received))
        count += 1
    conn.commit()
    conn.close()
    print(f"✅ MR Delivery total: {count}\n")

# -------------------------------------------------------------------
# 7. MAIN
# -------------------------------------------------------------------
def main():
    print("\n" + "="*70)
    print("🚀 STARTING COMPLETE DATA IMPORT (ALL 14 FILES - 100% FIXED V2)")
    print("="*70)
    clean_database()
    create_tables()
    create_fts_tables()
    import_employees()
    import_clients_and_bookings()
    import_collections()
    import_chq_register()
    import_conveyance()
    import_salary()
    import_car_requisition()
    import_deed_movement()
    import_token_money()
    import_courier()
    import_hotel_reservation()
    import_gift_ledger()
    import_mr_delivery()
    rebuild_fts()
    print("\n" + "="*70)
    print("📊 FINAL DATABASE COUNTS")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    tables = ['employees','clients','bookings','collections','chq_register','conveyance',
              'salary','car_requisition','deed_movement','token_money','courier',
              'hotel_reservation','gift_ledger','mr_delivery']
    total = 0
    for t in tables:
        cnt = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt}")
        total += cnt
    print("-"*70)
    print(f"  TOTAL RECORDS IN DATABASE: {total}")
    conn.close()
    print("="*70)
    print("✅ ALL DATA IMPORT COMPLETED! 🚀")
    print("="*70)

if __name__ == '__main__':
    main()
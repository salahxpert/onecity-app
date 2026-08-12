from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
import sqlite3
import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import time
import random
import pandas as pd
import requests
from functools import wraps
import bcrypt
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import zipfile
import shutil
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

# ===== Load Environment =====
load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY', 'your-super-secret-key-change-this-in-production')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-me')

# ===== Logging =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
jwt = JWTManager(app)

# ---------- Database ----------
def get_db():
    conn = sqlite3.connect('office_data.db')
    conn.row_factory = sqlite3.Row
    return conn

# ===== Authentication =====
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def init_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    admin_pass = hash_password('admin123')
    c.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
              ('admin', admin_pass, 'admin'))
    conn.commit()
    conn.close()
    logger.info("Users table initialized.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ===== Auto Backup Scheduler =====
def create_auto_backup():
    try:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.exists('office_data.db'):
            backup_path = os.path.join(backup_dir, f'office_data_backup_{timestamp}.db')
            shutil.copy2('office_data.db', backup_path)
            zip_path = os.path.join(backup_dir, f'backup_{timestamp}.zip')
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(backup_path, os.path.basename(backup_path))
            os.remove(backup_path)
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.zip')])
            cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
            for f in backups:
                try:
                    date_str = f.replace('backup_', '').replace('.zip', '')
                    file_date = datetime.datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                    if file_date < cutoff:
                        os.remove(os.path.join(backup_dir, f))
                        logger.info(f"Removed old backup: {f}")
                except Exception as e:
                    logger.warning(f"Could not parse backup file: {f} - {e}")
    except Exception as e:
        logger.error(f"Auto backup failed: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=create_auto_backup,
    trigger=CronTrigger(hour=2, minute=0),
    id='auto_backup_job',
    replace_existing=True
)
scheduler.start()
logger.info("Auto backup scheduler started (daily at 2:00 AM)")

# ---------- Google Sheets Sync (UPDATED: Environment Variable support) ----------
class GoogleSheetSync:
    def __init__(self):
        self.folder_id = '1lWfeObWJL1UisqAEc6qU4iW89lbMw-PF'
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.client = None
        self.creds = None
        self.sheets = {}
        self._authenticate()
        self._load_sheet_list()
    
def _authenticate(self):
    import base64
    b64_key = os.getenv('GOOGLE_PRIVATE_KEY_B64')
    if b64_key:
        try:
            private_key = base64.b64decode(b64_key).decode('utf-8')
            creds_dict = {
                "type": "service_account",
                "project_id": "secure-path-503710-d7",
                "private_key_id": "29f74a30981fe5b098b44fbf08d3a5bd35bc8dae",
                "private_key": private_key,
                "client_email": "onecity-app@secure-path-503710-d7.iam.gserviceaccount.com",
                "client_id": "110982405032183988934",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/onecity-app%40secure-path-503710-d7.iam.gserviceaccount.com",
                "universe_domain": "googleapis.com"
            }
            self.creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, self.scope)
            self.client = gspread.authorize(self.creds)
            logger.info("Google Sheets authenticated via Base64-encoded private key")
            return
        except Exception as e:
            logger.error(f"Base64 decode error: {e}")
    raise Exception("GOOGLE_PRIVATE_KEY_B64 environment variable not set or invalid")
    
    def _load_sheet_list(self):
        try:
            access_token = self.creds.get_access_token().access_token
            url = f"https://www.googleapis.com/drive/v3/files?q='{self.folder_id}'+in+parents&mimeType='application/vnd.google-apps.spreadsheet'&fields=files(id,name)"
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files = response.json().get('files', [])
                self.sheets = {f['name']: f['id'] for f in files}
                logger.info(f"Loaded {len(self.sheets)} sheets from Google Drive")
            else:
                self.sheets = {}
                logger.error(f"Failed to load sheets: {response.status_code}")
        except Exception as e:
            logger.error(f"Could not load sheet list: {e}")
            self.sheets = {}
    
    def _get_worksheet_data(self, sheet_id, worksheet_title):
        try:
            sh = self.client.open_by_key(sheet_id)
            ws = None
            for w in sh.worksheets():
                if w.title == worksheet_title:
                    ws = w
                    break
            if not ws:
                return None, None
            values = ws.get_all_values()
            if not values or len(values) < 2:
                return None, None
            headers = values[0]
            data_rows = values[1:]
            return headers, data_rows
        except Exception as e:
            logger.error(f"Error reading worksheet {worksheet_title}: {e}")
            return None, None
    
    def _insert_data(self, table_name, headers, rows, source_sheet):
        if not rows:
            return 0
        conn = get_db()
        c = conn.cursor()
        c.execute(f"PRAGMA table_info({table_name})")
        existing_cols = [row[1] for row in c.fetchall()]
        col_map = {}
        for h in headers:
            if not h or not isinstance(h, str):
                continue
            key = h.strip().lower().replace(' ', '_').replace(':', '')
            key = re.sub(r'[^a-zA-Z0-9_]', '', key)
            if key and key in existing_cols:
                col_map[h] = key
        if 'source_sheet' in existing_cols:
            col_map['__SOURCE__'] = 'source_sheet'
        if not col_map:
            return 0
        final_cols = list(col_map.values())
        placeholders = ','.join(['?' for _ in final_cols])
        query = f"INSERT OR REPLACE INTO {table_name} ({','.join(final_cols)}) VALUES ({placeholders})"
        count = 0
        for row in rows:
            if not any(row):
                continue
            vals = []
            for k, col in col_map.items():
                if k == '__SOURCE__':
                    vals.append(source_sheet)
                else:
                    try:
                        idx = headers.index(k)
                    except ValueError:
                        idx = -1
                    val = row[idx] if idx != -1 and idx < len(row) else None
                    if val and isinstance(val, str) and re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', val.strip()):
                        try:
                            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y']:
                                try:
                                    dt = datetime.datetime.strptime(val.strip(), fmt)
                                    val = dt.strftime('%Y-%m-%d')
                                    break
                                except:
                                    continue
                        except:
                            pass
                    vals.append(val)
            try:
                c.execute(query, vals)
                count += 1
            except Exception as e:
                logger.warning(f"Insert error: {e}")
        conn.commit()
        conn.close()
        return count
    
    def sync_all(self, max_retries=3):
        total = 0
        for sheet_name, sheet_id in self.sheets.items():
            table = self._get_table_name(sheet_name)
            if not table:
                logger.info(f"No mapping for {sheet_name}, skipping")
                continue
            logger.info(f"Syncing {sheet_name} -> {table}")
            try:
                sh = self.client.open_by_key(sheet_id)
                for ws in sh.worksheets():
                    try:
                        headers, rows = self._get_worksheet_data(sheet_id, ws.title)
                        if headers is None:
                            continue
                        for attempt in range(max_retries):
                            try:
                                cnt = self._insert_data(table, headers, rows, ws.title)
                                total += cnt
                                break
                            except Exception as e:
                                if "429" in str(e) or "Quota" in str(e):
                                    wait = (attempt + 1) * 10 + random.randint(0, 5)
                                    logger.warning(f"Quota hit, waiting {wait}s...")
                                    time.sleep(wait)
                                else:
                                    logger.error(f"Error syncing {ws.title}: {e}")
                                    break
                        time.sleep(1)
                    except Exception as e:
                        logger.error(f"Error processing worksheet {ws.title}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error opening sheet {sheet_name}: {e}")
                continue
        return total
    
    def _get_table_name(self, sheet_name):
        mapping = {
            'Conveyance Data Sheet': 'conveyance',
            'Salary Book Land Office': 'salary',
            'Employee Book': 'employees',
            'Hotel Reservation Record Book': 'hotel_reservation',
            'Postage & Courier Register': 'courier',
            'Client Token Money Details': 'token_money',
            'Car Requisition Record': 'car_requisition',
            'Client MR Delivery Register': 'mr_delivery',
            'EMI Track Book & Details': 'bookings',
            'Client Deed Movment Register': 'deed_movement',
            'Client Ledger and Booking Details OCDL Sales': 'bookings',
            'MR Reg & Sales Collection Report': 'collections',
            'CHQ Book Register': 'chq_register',
            'Client Gift Ledger': 'gift_ledger'
        }
        return mapping.get(sheet_name, None)
    
    def write_to_sheet(self, table_name, row_data, sheet_name=None):
        if not self.client:
            logger.error("Google Sheets client not available")
            return False
        try:
            sheet_id = None
            if sheet_name:
                for name, sid in self.sheets.items():
                    if sheet_name.lower() in name.lower():
                        sheet_id = sid
                        break
            if not sheet_id:
                for name, sid in self.sheets.items():
                    if table_name in name.lower():
                        sheet_id = sid
                        break
            if not sheet_id:
                logger.error(f"No sheet found for {table_name}")
                return False
            
            sh = self.client.open_by_key(sheet_id)
            ws = sh.get_worksheet(0)
            headers = ws.row_values(1)
            header_map = {}
            for h in headers:
                h_clean = h.strip().lower().replace(' ', '_').replace(':', '')
                h_clean = re.sub(r'[^a-zA-Z0-9_]', '', h_clean)
                header_map[h_clean] = h
            
            mr_no = row_data.get('mr_no')
            if mr_no:
                records = ws.get_all_records()
                for i, record in enumerate(records, start=2):
                    if str(record.get('MR No', '')) == str(mr_no):
                        cell_list = []
                        for key, val in row_data.items():
                            if key in header_map:
                                try:
                                    col_index = headers.index(header_map[key])
                                    if col_index < 26:
                                        col_letter = chr(65 + col_index)
                                    else:
                                        col_letter = chr(64 + col_index // 26) + chr(65 + col_index % 26)
                                    cell_list.append({
                                        'range': f"{col_letter}{i}",
                                        'values': [[val]]
                                    })
                                except ValueError:
                                    continue
                        if cell_list:
                            ws.batch_update(cell_list)
                            logger.info(f"Updated row {i} in Google Sheet for MR {mr_no}")
                        return True
            
            new_row = []
            for h in headers:
                h_clean = h.strip().lower().replace(' ', '_').replace(':', '')
                h_clean = re.sub(r'[^a-zA-Z0-9_]', '', h_clean)
                new_row.append(row_data.get(h_clean, ''))
            ws.append_row(new_row)
            logger.info(f"Appended new row to Google Sheet for MR {mr_no}")
            return True
        except Exception as e:
            logger.error(f"Error writing to Google Sheet: {e}")
            return False

sync = None
try:
    sync = GoogleSheetSync()
    logger.info("Google Sheets Sync initialized")
except Exception as e:
    logger.error(f"Google Sheets Sync not available: {e}")

# ===== backup_to_excel =====
def backup_to_excel(table_name, limit=None):
    try:
        conn = get_db()
        if limit:
            df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}", conn)
        else:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        if df.empty:
            logger.warning(f"No data to backup for {table_name}")
            return False
        os.makedirs('data', exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = f"data/backup_{table_name}_{timestamp}.xlsx"
        df.to_excel(file_path, index=False, sheet_name=table_name)
        logger.info(f"Backup created: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error backing up {table_name}: {e}")
        return False

# ---------- Static ----------
@app.route('/static/<path:path>')
def serve_static(path):
    if path in ['icon-192.png', 'icon-512.png']:
        if not os.path.exists(os.path.join('static', path)):
            try:
                from PIL import Image, ImageDraw
                size = 192 if '192' in path else 512
                img = Image.new('RGB', (size, size), color=(13, 110, 253))
                d = ImageDraw.Draw(img)
                d.text((size//2-40, size//2-20), "OC", fill=(255,255,255))
                img.save(os.path.join('static', path))
            except:
                pass
    return send_from_directory('static', path)

# ===== Authentication Routes =====
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            return render_template('login.html', error='Please enter username and password')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password(password, user['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and check_password(password, user['password']):
        access_token = create_access_token(identity=user['id'])
        return jsonify({'access_token': access_token, 'username': user['username'], 'role': user['role']})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({'message': f'Hello user {current_user}'})

# ---------- Pages ----------
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/accounts')
@login_required
def accounts():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.id, c.mr_no, c.client_name, c.project, c.collection_date, c.mr_type,
               c.cash, c.dd_ft_online, c.clear_cheque, c.advance_cheque, c.dishonour_cheque,
               COALESCE(e.name, 'N/A') as sales_person, c.source_sheet
        FROM collections c
        LEFT JOIN employees e ON c.sales_person_id = e.id
        ORDER BY c.collection_date DESC LIMIT 500
    ''').fetchall()
    groups = {}
    for row in rows:
        row_dict = dict(row)
        sheet = row['source_sheet'] or 'Unknown'
        if sheet not in groups:
            groups[sheet] = []
        groups[sheet].append(row_dict)
    
    salary_data = conn.execute('''
        SELECT id, month, employee, gross_salary, payable_salary, paid_taka, due_salary, 
               COALESCE(designation, 'N/A') as designation
        FROM salary
        ORDER BY month DESC, employee ASC
        LIMIT 200
    ''').fetchall()
    salary_list = [dict(row) for row in salary_data]
    
    conv_data = conn.execute('''
        SELECT id, bill_date, employee, purpose, client_name, amount, 
               COALESCE(type, 'Regular') as type
        FROM conveyance
        ORDER BY bill_date DESC
        LIMIT 200
    ''').fetchall()
    conv_list = [dict(row) for row in conv_data]
    conn.close()
    return render_template('accounts.html', 
                         groups=groups, 
                         salary_data=salary_list,
                         conveyance_data=conv_list)

@app.route('/api/salary/<int:id>', methods=['PUT'])
@login_required
def update_salary(id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    fields = []
    values = []
    for key in ['gross_salary', 'payable_salary', 'paid_taka', 'due_salary']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({'error': 'No fields to update'}), 400
    values.append(id)
    query = f"UPDATE salary SET {', '.join(fields)} WHERE id = ?"
    c.execute(query, values)
    conn.commit()
    conn.close()
    backup_to_excel('salary')
    return jsonify({'success': True, 'message': 'Salary updated successfully!'})

@app.route('/add-collection')
@login_required
def add_collection_form():
    conn = get_db()
    employees = conn.execute('SELECT id, name FROM employees ORDER BY name').fetchall()
    clients = conn.execute('SELECT id, name, project FROM clients ORDER BY name').fetchall()
    sheets = conn.execute('SELECT DISTINCT source_sheet FROM collections WHERE source_sheet IS NOT NULL').fetchall()
    conn.close()
    return render_template('add_collection.html', employees=employees, clients=clients, sheets=sheets)

@app.route('/edit-collection/<int:mr_id>')
@login_required
def edit_collection_form(mr_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM collections WHERE id = ?', (mr_id,)).fetchone()
    if not row:
        return "MR not found", 404
    employees = conn.execute('SELECT id, name FROM employees ORDER BY name').fetchall()
    clients = conn.execute('SELECT id, name, project FROM clients ORDER BY name').fetchall()
    sheets = conn.execute('SELECT DISTINCT source_sheet FROM collections WHERE source_sheet IS NOT NULL').fetchall()
    conn.close()
    return render_template('edit_collection.html', mr=row, employees=employees, clients=clients, sheets=sheets)

@app.route('/collections')
@login_required
def collections_list():
    conn = get_db()
    cols = conn.execute('''
        SELECT c.id, c.mr_no, c.client_name, c.project, c.collection_date, c.mr_type,
               c.cash, c.dd_ft_online, c.clear_cheque, c.advance_cheque, c.dishonour_cheque,
               COALESCE(e.name, 'N/A') as sales_person, c.source_sheet
        FROM collections c
        LEFT JOIN employees e ON c.sales_person_id = e.id
        ORDER BY c.collection_date DESC LIMIT 200
    ''').fetchall()
    conn.close()
    return render_template('collections_list.html', collections=cols)

@app.route('/client-ledger/<int:client_id>')
@login_required
def client_ledger(client_id):
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    bookings = conn.execute('''
        SELECT b.*, COALESCE(e.name, 'N/A') as sales_person
        FROM bookings b
        LEFT JOIN employees e ON b.sales_person_id = e.id
        WHERE b.client_id = ?
        ORDER BY b.booking_date DESC
    ''', (client_id,)).fetchall()
    collections = conn.execute('''
        SELECT c.*, COALESCE(e.name, 'N/A') as sales_person
        FROM collections c
        LEFT JOIN employees e ON c.sales_person_id = e.id
        WHERE c.client_name = (SELECT name FROM clients WHERE id = ?)
        ORDER BY c.collection_date DESC LIMIT 50
    ''', (client_id,)).fetchall()
    conn.close()
    return render_template('client_ledger.html', client=client, bookings=bookings, collections=collections)

@app.route('/client-ledgers')
@login_required
def client_ledgers_list():
    conn = get_db()
    clients = conn.execute('SELECT id, name, contact, project, unit_plot FROM clients ORDER BY name').fetchall()
    conn.close()
    return render_template('client_ledgers.html', clients=clients)

@app.route('/emi-track')
@login_required
def emi_track():
    conn = get_db()
    emis = conn.execute('''
        SELECT b.file_no, b.client_id, c.name as client_name, b.project, b.unit_plot,
               b.emi_start, b.monthly_emi, b.last_paid_date, b.total_due_inst, b.total_due_taka,
               b.remarks, COALESCE(e.name, 'N/A') as sales_person
        FROM bookings b
        LEFT JOIN clients c ON b.client_id = c.id
        LEFT JOIN employees e ON b.sales_person_id = e.id
        ORDER BY b.total_due_taka DESC
    ''').fetchall()
    conn.close()
    return render_template('emi_track.html', emis=emis)

@app.route('/employees-list')
@login_required
def employees_list():
    conn = get_db()
    emps = conn.execute('SELECT id, name, designation, team, joining_date, office_contact FROM employees ORDER BY name').fetchall()
    conn.close()
    return render_template('employees_list.html', employees=emps)

@app.route('/salary')
@login_required
def salary_page():
    return render_template('salary.html')

@app.route('/conveyance')
@login_required
def conveyance_page():
    return render_template('conveyance.html')

@app.route('/chq-register')
@login_required
def chq_register():
    return render_template('chq_register.html')

@app.route('/car-requisition')
@login_required
def car_requisition():
    return render_template('car_requisition.html')

@app.route('/deed-movement')
@login_required
def deed_movement():
    return render_template('deed_movement.html')

@app.route('/token-money')
@login_required
def token_money():
    return render_template('token_money.html')

@app.route('/courier')
@login_required
def courier():
    return render_template('courier.html')

@app.route('/hotel-reservation')
@login_required
def hotel_reservation():
    return render_template('hotel_reservation.html')

@app.route('/gift-ledger')
@login_required
def gift_ledger():
    return render_template('gift_ledger.html')

@app.route('/mr-delivery')
@login_required
def mr_delivery():
    return render_template('mr_delivery.html')

@app.route('/check-requisition')
@login_required
def check_requisition():
    return render_template('check_requisition.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    tables = ['employees', 'clients', 'bookings', 'collections', 'chq_register',
              'conveyance', 'salary', 'car_requisition', 'deed_movement',
              'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    counts = {}
    for t in tables:
        counts[t] = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    conn.close()
    return render_template('admin.html', counts=counts, tables=tables)

@app.route('/admin/<table>')
@admin_required
def admin_table(table):
    allowed = ['employees', 'clients', 'bookings', 'collections', 'chq_register',
               'conveyance', 'salary', 'car_requisition', 'deed_movement',
               'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    if table not in allowed:
        return "Invalid table", 400
    search_q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    conn = get_db()
    columns = [row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    if search_q:
        like = f'%{search_q}%'
        conditions = []
        for col in columns:
            if col in ['id']:
                continue
            conditions.append(f"{col} LIKE ?")
        if conditions:
            where_clause = f"WHERE {' OR '.join(conditions)}"
            params = [like] * len([c for c in columns if c != 'id'])
            count_query = f"SELECT COUNT(*) FROM {table} {where_clause}"
            total = conn.execute(count_query, params).fetchone()[0]
            query = f"SELECT * FROM {table} {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            rows = conn.execute(query, params).fetchall()
        else:
            total = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            rows = conn.execute(f'SELECT * FROM {table} ORDER BY id DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
    else:
        total = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        rows = conn.execute(f'SELECT * FROM {table} ORDER BY id DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
    conn.close()
    data = [dict(row) for row in rows]
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    return render_template('admin_table.html', 
                         table=table, 
                         columns=columns, 
                         data=data, 
                         search_q=search_q,
                         page=page,
                         total_pages=total_pages,
                         total=total)

@app.route('/admin/<table>/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit(table, id):
    allowed = ['employees', 'clients', 'bookings', 'collections', 'chq_register',
               'conveyance', 'salary', 'car_requisition', 'deed_movement',
               'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    if table not in allowed:
        return "Invalid table", 400
    conn = get_db()
    if request.method == 'POST':
        data = request.form.to_dict()
        fields = []
        values = []
        for key, val in data.items():
            if key != 'id':
                fields.append(f"{key} = ?")
                values.append(val)
        if fields:
            values.append(id)
            conn.execute(f"UPDATE {table} SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        conn.close()
        backup_to_excel(table)
        return redirect(f'/admin/{table}?q={request.args.get("q", "")}')
    row = conn.execute(f'SELECT * FROM {table} WHERE id = ?', (id,)).fetchone()
    columns = [row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    conn.close()
    return render_template('admin_edit.html', table=table, row=row, columns=columns)

@app.route('/admin/<table>/<int:id>/delete', methods=['POST'])
@admin_required
def admin_delete(table, id):
    allowed = ['employees', 'clients', 'bookings', 'collections', 'chq_register',
               'conveyance', 'salary', 'car_requisition', 'deed_movement',
               'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    if table not in allowed:
        return "Invalid table", 400
    conn = get_db()
    conn.execute(f'DELETE FROM {table} WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    backup_to_excel(table)
    return jsonify({'success': True})

@app.route('/sheet/<table>/<sheet_name>')
@login_required
def view_sheet(table, sheet_name):
    allowed_tables = ['collections', 'chq_register', 'conveyance', 'salary',
                      'car_requisition', 'deed_movement', 'token_money',
                      'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    if table not in allowed_tables:
        return "Invalid table", 400
    conn = get_db()
    if table == 'conveyance':
        rows = conn.execute('SELECT * FROM conveyance WHERE type = ? ORDER BY id DESC', (sheet_name,)).fetchall()
    else:
        rows = conn.execute(f'SELECT * FROM {table} WHERE source_sheet = ? ORDER BY id DESC', (sheet_name,)).fetchall()
    columns = [row['name'] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    conn.close()
    data = []
    totals = {'cash':0, 'dd_ft_online':0, 'clear_cheque':0, 'advance_cheque':0, 'dishonour_cheque':0}
    for row in rows:
        row_dict = dict(row)
        color = None
        for key, val in row_dict.items():
            if isinstance(val, str):
                if 'paid' in val.lower() or 'complete' in val.lower() or 'received' in val.lower():
                    color = 'bg-success text-white'
                    break
                elif 'due' in val.lower() or 'pending' in val.lower():
                    color = 'bg-danger text-white'
                    break
        if color:
            row_dict['_color'] = color
        if table == 'collections':
            for col in ['cash', 'dd_ft_online', 'clear_cheque', 'advance_cheque', 'dishonour_cheque']:
                if col in row_dict:
                    try:
                        totals[col] += float(row_dict[col] or 0)
                    except:
                        pass
        data.append(row_dict)
    return render_template('sheet_view.html', table=table, sheet_name=sheet_name, columns=columns, data=data, totals=totals)

@app.route('/api/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'empty query'}), 400
    conn = get_db()
    like = f'%{q}%'
    results = {}
    
    try:
        fts_cols = conn.execute('''
            SELECT c.*, COALESCE(e.name, 'N/A') as sales_person FROM collections c
            JOIN collections_fts ON c.id = collections_fts.rowid
            LEFT JOIN employees e ON c.sales_person_id = e.id
            WHERE collections_fts MATCH ?
            LIMIT 50
        ''', (q,)).fetchall()
        results['collections_fts'] = [dict(row) for row in fts_cols]
    except Exception as e:
        logger.warning(f"FTS search failed: {e}")
    
    emps = conn.execute('''
        SELECT id, emp_id, name, designation, team, office_contact
        FROM employees WHERE name LIKE ? OR emp_id LIKE ? OR designation LIKE ? OR team LIKE ? LIMIT 50
    ''', (like, like, like, like)).fetchall()
    results['employees'] = [dict(row) for row in emps]
    
    clients = conn.execute('''
        SELECT id, name, contact, project, unit_plot, sale_value, booking_date
        FROM clients WHERE name LIKE ? OR contact LIKE ? OR project LIKE ? OR unit_plot LIKE ? LIMIT 50
    ''', (like, like, like, like)).fetchall()
    results['clients'] = [dict(row) for row in clients]
    
    bookings = conn.execute('''
        SELECT b.file_no, b.project, b.unit_plot, b.sale_value, b.booking_date,
               b.emi_start, b.monthly_emi, b.last_paid_date, b.total_due_inst, b.total_due_taka,
               b.dp_received, b.dp_commited, b.remarks,
               COALESCE(e.name, 'N/A') as sales_person, c.name as client_name, c.contact
        FROM bookings b
        LEFT JOIN employees e ON b.sales_person_id = e.id
        LEFT JOIN clients c ON b.client_id = c.id
        WHERE b.file_no LIKE ? OR e.name LIKE ? OR c.name LIKE ? OR c.contact LIKE ? LIMIT 50
    ''', (like, like, like, like)).fetchall()
    results['bookings'] = [dict(row) for row in bookings]
    
    cols = conn.execute('''
        SELECT c.mr_no, c.client_name, c.project, c.collection_date,
               c.unit, c.mr_type, c.cash, c.dd_ft_online,
               c.clear_cheque, c.advance_cheque, c.dishonour_cheque,
               COALESCE(e.name, 'N/A') as sales_person, c.source_sheet
        FROM collections c
        LEFT JOIN employees e ON c.sales_person_id = e.id
        WHERE c.mr_no LIKE ? OR c.client_name LIKE ? OR c.project LIKE ? OR c.mr_type LIKE ?
        LIMIT 50
    ''', (like, like, like, like)).fetchall()
    for col in cols:
        if col['mr_no'] and '.' in col['mr_no']:
            try:
                col['mr_no'] = str(int(float(col['mr_no'])))
            except:
                pass
    results['collections'] = [dict(row) for row in cols]
    
    chq = conn.execute('''
        SELECT mr_no, collection_date, client_name, project, unit_katha, mr_type,
               amount, bank, cheque_no, cheque_status
        FROM chq_register
        WHERE mr_no LIKE ? OR client_name LIKE ? OR project LIKE ? OR bank LIKE ? OR cheque_no LIKE ? LIMIT 50
    ''', (like, like, like, like, like)).fetchall()
    results['chq_register'] = [dict(row) for row in chq]
    
    conv = conn.execute('''
        SELECT bill_date, employee, purpose, client_name, amount, type
        FROM conveyance
        WHERE employee LIKE ? OR client_name LIKE ? OR purpose LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['conveyance'] = [dict(row) for row in conv]
    
    salary = conn.execute('''
        SELECT id, month, employee, gross_salary, payable_salary, paid_taka, due_salary
        FROM salary
        WHERE employee LIKE ? OR month LIKE ? LIMIT 50
    ''', (like, like)).fetchall()
    results['salary'] = [dict(row) for row in salary]
    
    car = conn.execute('''
        SELECT visit_date, employee, purpose, client_name, vehicle, to_project
        FROM car_requisition
        WHERE employee LIKE ? OR client_name LIKE ? OR purpose LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['car_requisition'] = [dict(row) for row in car]
    
    deed = conn.execute('''
        SELECT file_no, client_name, project, deed_status, delivered_to, delivery_date
        FROM deed_movement
        WHERE client_name LIKE ? OR file_no LIKE ? OR project LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['deed_movement'] = [dict(row) for row in deed]
    
    token = conn.execute('''
        SELECT mr_no, client_name, project, collection_date, mr_type,
               cash, dd_ft_online, clear_cheque, advance_cheque, dishonour_cheque
        FROM token_money
        WHERE mr_no LIKE ? OR client_name LIKE ? OR project LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['token_money'] = [dict(row) for row in token]
    
    courier = conn.execute('''
        SELECT date, sender_name, client_name, courier_name, cn_number, courier_charge
        FROM courier
        WHERE sender_name LIKE ? OR client_name LIKE ? OR courier_name LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['courier'] = [dict(row) for row in courier]
    
    hotel = conn.execute('''
        SELECT issue_date, sales_person, client_name, arrival_date, departure_date,
               project, expected_collection, realized_amount
        FROM hotel_reservation
        WHERE client_name LIKE ? OR sales_person LIKE ? OR project LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['hotel_reservation'] = [dict(row) for row in hotel]
    
    gift = conn.execute('''
        SELECT gift_date, sales_person, client_name, project, item_name, gift_value
        FROM gift_ledger
        WHERE client_name LIKE ? OR sales_person LIKE ? OR item_name LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['gift_ledger'] = [dict(row) for row in gift]
    
    mrd = conn.execute('''
        SELECT mr_no, client_name, project, issue_date, payment_type, amount, received_by
        FROM mr_delivery
        WHERE mr_no LIKE ? OR client_name LIKE ? OR project LIKE ? LIMIT 50
    ''', (like, like, like)).fetchall()
    results['mr_delivery'] = [dict(row) for row in mrd]
    conn.close()
    return jsonify(results)

@app.route('/api/rebuild_fts', methods=['POST'])
@admin_required
def rebuild_fts():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM collections_fts")
        c.execute('''
            INSERT INTO collections_fts(rowid, mr_no, client_name, project, sales_person_name)
            SELECT c.id, c.mr_no, c.client_name, c.project, COALESCE(e.name, 'N/A')
            FROM collections c
            LEFT JOIN employees e ON c.sales_person_id = e.id
        ''')
        c.execute("DELETE FROM employees_fts")
        c.execute('''
            INSERT INTO employees_fts(rowid, name, designation, team)
            SELECT id, name, designation, team FROM employees
        ''')
        c.execute("DELETE FROM clients_fts")
        c.execute('''
            INSERT INTO clients_fts(rowid, name, project, contact)
            SELECT id, name, project, contact FROM clients
        ''')
        c.execute("DELETE FROM bookings_fts")
        c.execute('''
            INSERT INTO bookings_fts(rowid, file_no, project, client_name)
            SELECT b.id, b.file_no, b.project, c.name
            FROM bookings b
            LEFT JOIN clients c ON b.client_id = c.id
        ''')
        conn.commit()
        conn.close()
        logger.info("All FTS tables rebuilt successfully")
        return jsonify({'success': True, 'message': 'All FTS indexes rebuilt'})
    except Exception as e:
        logger.error(f"FTS rebuild error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/db_stats')
@login_required
def db_stats():
    conn = get_db()
    stats = {}
    tables = ['employees', 'clients', 'bookings', 'collections', 'chq_register',
              'conveyance', 'salary', 'car_requisition', 'deed_movement',
              'token_money', 'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery']
    for table in tables:
        stats[table] = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    summary = conn.execute('''
        SELECT 
            SUM(cash) as total_cash,
            SUM(dd_ft_online) as total_online,
            SUM(clear_cheque) as total_cheque,
            SUM(advance_cheque) as total_advance,
            SUM(dishonour_cheque) as total_dishonour,
            COUNT(*) as total_entries
        FROM collections
    ''').fetchone()
    stats['summary'] = dict(summary)
    conn.close()
    return jsonify(stats)

@app.route('/api/table/<table_name>')
@login_required
def get_table_data(table_name):
    allowed_tables = [
        'collections', 'chq_register', 'conveyance', 'salary',
        'car_requisition', 'deed_movement', 'token_money',
        'courier', 'hotel_reservation', 'gift_ledger', 'mr_delivery'
    ]
    if table_name not in allowed_tables:
        return jsonify({'error': 'Invalid table name'}), 400
    filter_type = request.args.get('type', '')
    conn = get_db()
    columns = [row['name'] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()]
    if table_name == 'conveyance' and filter_type:
        rows = conn.execute(f'SELECT * FROM {table_name} WHERE type = ? ORDER BY id DESC LIMIT 200', (filter_type,)).fetchall()
    else:
        rows = conn.execute(f'SELECT * FROM {table_name} ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    data = [dict(row) for row in rows]
    return jsonify({'columns': columns, 'data': data})

@app.route('/api/collection', methods=['POST'])
@login_required
def add_collection():
    data = request.json
    required = ['sales_person', 'client_name', 'project', 'collection_date', 'mr_type', 'payment_type', 'amount']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400
    conn = get_db()
    c = conn.cursor()
    
    client_name = data['client_name']
    contact = data.get('contact', '')
    c.execute('SELECT id FROM clients WHERE name = ? AND contact = ?', (client_name, contact))
    client = c.fetchone()
    if not client:
        c.execute('''
            INSERT INTO clients (name, contact, project, sale_value, booking_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (client_name, contact, data['project'], 0, datetime.date.today().isoformat()))
        client_id = c.lastrowid
    else:
        client_id = client['id']
    
    sales_name = data['sales_person']
    c.execute('SELECT id FROM employees WHERE name = ?', (sales_name,))
    emp = c.fetchone()
    sales_person_id = emp['id'] if emp else None
    
    amount = float(data['amount'])
    cash = dd_ft_online = clear_cheque = advance_cheque = dishonour_cheque = 0
    payment_type = data['payment_type']
    if payment_type == 'Cash': cash = amount
    elif payment_type == 'Online': dd_ft_online = amount
    elif payment_type == 'Clear Cheque': clear_cheque = amount
    elif payment_type == 'Advance Cheque': advance_cheque = amount
    elif payment_type == 'Dishonour Cheque': dishonour_cheque = amount
    
    mr_no = data.get('mr_no')
    if not mr_no:
        mr_no = f"MR-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    else:
        if '.' in mr_no:
            try:
                mr_no = str(int(float(mr_no)))
            except:
                pass
    
    source_sheet = data.get('source_sheet', 'Manual Entry')
    c.execute('''
        INSERT INTO collections (
            mr_no, sales_person_id, client_name, project, collection_date,
            unit, mr_type, cash, dd_ft_online, clear_cheque, advance_cheque, dishonour_cheque,
            cheque_status, source_sheet
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        mr_no, sales_person_id, client_name, data['project'],
        data['collection_date'], int(data.get('unit', 1)), data['mr_type'],
        cash, dd_ft_online, clear_cheque, advance_cheque, dishonour_cheque,
        data.get('cheque_status', ''), source_sheet
    ))
    
    c.execute('''
        SELECT id, dp_received, dp_commited, total_due_inst, total_due_taka, monthly_emi
        FROM bookings 
        WHERE client_id = ? AND project = ? 
        ORDER BY booking_date DESC LIMIT 1
    ''', (client_id, data['project']))
    booking = c.fetchone()
    
    if booking:
        mr_type = data['mr_type']
        if mr_type == 'Booking':
            new_dp = (booking['dp_received'] or 0) + amount
            c.execute('''
                UPDATE bookings 
                SET dp_received = ?,
                    remarks = CASE WHEN dp_commited IS NOT NULL AND ? >= dp_commited THEN 'DP Complete' ELSE remarks END
                WHERE id = ?
            ''', (new_dp, new_dp, booking['id']))
        elif mr_type == 'Installment':
            new_due_inst = max(0, (booking['total_due_inst'] or 0) - 1)
            new_due_taka = max(0, (booking['total_due_taka'] or 0) - (booking['monthly_emi'] or 0))
            c.execute('''
                UPDATE bookings 
                SET last_paid_date = ?,
                    total_due_inst = ?,
                    total_due_taka = ?,
                    remarks = CASE WHEN ? <= 0 THEN 'EMI Complete' ELSE remarks END
                WHERE id = ?
            ''', (data['collection_date'], new_due_inst, new_due_taka, new_due_inst, booking['id']))
        elif mr_type == 'Token':
            new_dp = (booking['dp_received'] or 0) + amount
            c.execute('UPDATE bookings SET dp_received = ? WHERE id = ?', (new_dp, booking['id']))
    else:
        c.execute('''
            INSERT INTO bookings (client_id, project, unit_plot, sale_value, booking_date, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (client_id, data['project'], int(data.get('unit', 1)), 0, data['collection_date'], 'Auto-created from collection'))
    
    conn.commit()
    conn.close()
    
    if sync:
        sync.write_to_sheet('collections', data, sheet_name=source_sheet)
    backup_to_excel('collections')
    
    return jsonify({'success': True, 'message': 'Collection added & auto-posted successfully!'})

@app.route('/api/collection/<int:mr_id>', methods=['PUT'])
@login_required
def edit_collection(mr_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    fields = []
    values = []
    for key in ['mr_no', 'client_name', 'project', 'collection_date', 'unit', 'mr_type',
                'cash', 'dd_ft_online', 'clear_cheque', 'advance_cheque', 'dishonour_cheque',
                'cheque_status', 'source_sheet']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return jsonify({'error': 'No fields to update'}), 400
    values.append(mr_id)
    query = f"UPDATE collections SET {', '.join(fields)} WHERE id = ?"
    c.execute(query, values)
    conn.commit()
    conn.close()
    
    if sync:
        sync.write_to_sheet('collections', data, sheet_name=data.get('source_sheet'))
    backup_to_excel('collections')
    
    return jsonify({'success': True, 'message': 'MR updated successfully!'})

@app.route('/api/sync_google_sheet', methods=['POST'])
@admin_required
def sync_google_sheet():
    if not sync:
        return jsonify({'error': 'Google Sheets sync not available'}), 500
    try:
        total = sync.sync_all()
        backup_to_excel('collections')
        return jsonify({'success': True, 'message': f'Synced {total} rows from Google Sheets'})
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backup', methods=['POST'])
@admin_required
def manual_backup():
    try:
        create_auto_backup()
        return jsonify({'success': True, 'message': 'Backup created successfully!'})
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return jsonify({'error': str(e)}), 500

GOOGLE_SHEET_URL = None
GOOGLE_SHEET_FILE = 'google_sheet_config.json'

@app.route('/api/set_google_sheet', methods=['POST'])
@admin_required
def set_google_sheet():
    global GOOGLE_SHEET_URL
    data = request.json
    if data and data.get('url'):
        GOOGLE_SHEET_URL = data['url']
        with open(GOOGLE_SHEET_FILE, 'w') as f:
            json.dump({'url': GOOGLE_SHEET_URL}, f)
        return jsonify({'success': True, 'message': 'Google Sheet URL saved.'})
    return jsonify({'error': 'No URL provided'}), 400

@app.route('/api/get_google_sheet', methods=['GET'])
@login_required
def get_google_sheet():
    global GOOGLE_SHEET_URL
    if GOOGLE_SHEET_URL is None:
        try:
            with open(GOOGLE_SHEET_FILE, 'r') as f:
                config = json.load(f)
                GOOGLE_SHEET_URL = config.get('url')
        except:
            pass
    return jsonify({'url': GOOGLE_SHEET_URL})

@app.route('/google-config')
@login_required
def google_config():
    return render_template('google_config.html')

if __name__ == '__main__':
    init_users()
    app.run(debug=True, host='0.0.0.0', port=5000)
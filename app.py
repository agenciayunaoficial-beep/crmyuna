from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
import sqlite3, hashlib, os, uuid
from datetime import datetime, date, timedelta
from functools import wraps

from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'yuna_secret_2024_crm')
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yuna.db')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png','jpg','jpeg','gif','webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

def save_upload(file_field):
    """Save uploaded file and return relative path or None."""
    f = request.files.get(file_field)
    if f and f.filename and allowed_file(f.filename):
        ext = f.filename.rsplit('.',1)[1].lower()
        fname = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, fname))
        return f'uploads/{fname}'
    return None

# ─────────────────────────────────────────
# DB SETUP
# ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT,
        role TEXT DEFAULT 'admin',
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        whatsapp TEXT,
        instagram TEXT,
        email TEXT,
        plan TEXT,
        plan_type TEXT,
        value REAL,
        payment_day INTEGER,
        payment_method TEXT,
        status TEXT DEFAULT 'active',
        start_date TEXT,
        notes TEXT,
        created_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        client_id TEXT,
        amount REAL,
        due_date TEXT,
        paid_date TEXT,
        method TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS recordings (
        id TEXT PRIMARY KEY,
        client_id TEXT,
        date TEXT,
        time TEXT,
        address TEXT,
        notes TEXT,
        status TEXT DEFAULT 'scheduled',
        created_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        client_id TEXT,
        month INTEGER,
        year INTEGER,
        report_type TEXT,
        -- social media
        followers INTEGER,
        profile_visits INTEGER,
        top_post1 TEXT,
        top_post1_img TEXT,
        top_post2 TEXT,
        top_post2_img TEXT,
        top_post3 TEXT,
        top_post3_img TEXT,
        -- trafego
        new_whatsapp_clients INTEGER,
        reach INTEGER,
        cost_per_result REAL,
        invested_value REAL,
        ctr REAL,
        -- metas
        -- Social Media metas (3 tiers)
        goal_min_followers INTEGER,
        goal_ok_followers INTEGER,
        goal_super_followers INTEGER,
        goal_min_visits INTEGER,
        goal_ok_visits INTEGER,
        goal_super_visits INTEGER,
        -- Trafego metas (3 tiers)
        goal_min_clients INTEGER,
        goal_ok_clients INTEGER,
        goal_super_clients INTEGER,
        goal_min_reach INTEGER,
        goal_ok_reach INTEGER,
        goal_super_reach INTEGER,
        goal_min_ctr REAL,
        goal_ok_ctr REAL,
        goal_super_ctr REAL,
        goal_max_cpr REAL,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    # Migrate: add columns if not exist
    new_cols = [
        ('top_post1_img','TEXT'),('top_post2_img','TEXT'),('top_post3_img','TEXT'),
        ('goal_min_followers','INTEGER'),('goal_ok_followers','INTEGER'),('goal_super_followers','INTEGER'),
        ('goal_min_visits','INTEGER'),('goal_ok_visits','INTEGER'),('goal_super_visits','INTEGER'),
        ('goal_min_clients','INTEGER'),('goal_ok_clients','INTEGER'),('goal_super_clients','INTEGER'),
        ('goal_min_reach','INTEGER'),('goal_ok_reach','INTEGER'),('goal_super_reach','INTEGER'),
        ('goal_min_ctr','REAL'),('goal_ok_ctr','REAL'),('goal_super_ctr','REAL'),
        ('goal_max_cpr','REAL'),
    ]
    for col, typ in new_cols:
        try:
            c.execute(f'ALTER TABLE reports ADD COLUMN {col} {typ}')
        except:
            pass

    # Default admin user
    admin_id = str(uuid.uuid4())
    pwd = hashlib.sha256('#Yunabbc26'.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (id, username, password, name, role, created_at) VALUES (?,?,?,?,?,?)",
                  (admin_id, 'Yunabbc', pwd, 'Administrador', 'admin', datetime.now().isoformat()))
    except:
        pass

    conn.commit()
    conn.close()

# Init DB on startup (works with Gunicorn)
init_db()

# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                            (username, hash_pwd(password))).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        error = 'Usuário ou senha incorretos.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    total_clients = conn.execute("SELECT COUNT(*) FROM clients WHERE status='active'").fetchone()[0]
    cancelled = conn.execute("SELECT COUNT(*) FROM clients WHERE status='cancelled'").fetchone()[0]
    monthly_revenue = conn.execute("SELECT COALESCE(SUM(value),0) FROM clients WHERE status='active'").fetchone()[0]

    # Pagamentos do mês
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    paid_month = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_date>=?",
        (month_start,)).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE status='pending' AND due_date<?",
        (today.isoformat(),)).fetchone()[0]

    # Próximas gravações
    recordings = conn.execute("""
        SELECT r.*, c.name as client_name FROM recordings r
        JOIN clients c ON c.id=r.client_id
        WHERE r.date >= ? AND r.status='scheduled'
        ORDER BY r.date ASC LIMIT 5
    """, (today.isoformat(),)).fetchall()

    # Clientes recentes
    recent_clients = conn.execute("""
        SELECT * FROM clients ORDER BY created_at DESC LIMIT 5
    """).fetchall()

    # Revenue by month (last 6 months)
    months_data = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i*28)
        label = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][d.month-1]
        val = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND strftime('%Y-%m',paid_date)=?",
            (d.strftime('%Y-%m'),)).fetchone()[0]
        months_data.append({'month': label, 'value': float(val)})

    conn.close()
    return render_template('dashboard.html',
        total_clients=total_clients, cancelled=cancelled,
        monthly_revenue=monthly_revenue, paid_month=paid_month,
        pending=pending, overdue=overdue,
        recordings=recordings, recent_clients=recent_clients,
        months_data=months_data)

# ─────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────
@app.route('/clients')
@login_required
def clients():
    search = request.args.get('q','')
    status = request.args.get('status','all')
    conn = get_db()
    q = "SELECT * FROM clients WHERE 1=1"
    params = []
    if search:
        q += " AND (name LIKE ? OR whatsapp LIKE ? OR instagram LIKE ?)"
        params += [f'%{search}%']*3
    if status != 'all':
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY name ASC"
    all_clients = conn.execute(q, params).fetchall()
    conn.close()
    return render_template('clients.html', clients=all_clients, search=search, status=status)

@app.route('/clients/new', methods=['GET','POST'])
@login_required
def new_client():
    if request.method == 'POST':
        conn = get_db()
        cid = str(uuid.uuid4())
        conn.execute("""INSERT INTO clients
            (id,name,whatsapp,instagram,email,plan,plan_type,value,payment_day,payment_method,status,start_date,notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            cid,
            request.form['name'], request.form.get('whatsapp',''),
            request.form.get('instagram',''), request.form.get('email',''),
            request.form.get('plan',''), request.form.get('plan_type',''),
            float(request.form.get('value',0)),
            int(request.form.get('payment_day',1)),
            request.form.get('payment_method','pix'),
            request.form.get('status','active'),
            request.form.get('start_date', date.today().isoformat()),
            request.form.get('notes',''),
            datetime.now().isoformat()
        ))
        # Auto-generate first payment
        pday = int(request.form.get('payment_day',1))
        today = date.today()
        due = today.replace(day=pday)
        if due < today: due = (due.replace(day=1) + timedelta(days=32)).replace(day=pday)
        conn.execute("""INSERT INTO payments (id,client_id,amount,due_date,method,status,created_at)
            VALUES (?,?,?,?,?,?,?)""", (
            str(uuid.uuid4()), cid, float(request.form.get('value',0)),
            due.isoformat(), request.form.get('payment_method','pix'),
            'pending', datetime.now().isoformat()
        ))
        conn.commit(); conn.close()
        return redirect(url_for('clients'))
    return render_template('client_form.html', client=None)

@app.route('/clients/<cid>')
@login_required
def client_detail(cid):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    payments = conn.execute("SELECT * FROM payments WHERE client_id=? ORDER BY due_date DESC", (cid,)).fetchall()
    recordings = conn.execute("SELECT * FROM recordings WHERE client_id=? ORDER BY date DESC", (cid,)).fetchall()
    reports = conn.execute("SELECT * FROM reports WHERE client_id=? ORDER BY year DESC, month DESC", (cid,)).fetchall()
    conn.close()
    return render_template('client_detail.html', client=client, payments=payments, recordings=recordings, reports=reports)

@app.route('/clients/<cid>/edit', methods=['GET','POST'])
@login_required
def edit_client(cid):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    if request.method == 'POST':
        conn.execute("""UPDATE clients SET name=?,whatsapp=?,instagram=?,email=?,plan=?,plan_type=?,
            value=?,payment_day=?,payment_method=?,status=?,start_date=?,notes=? WHERE id=?""", (
            request.form['name'], request.form.get('whatsapp',''),
            request.form.get('instagram',''), request.form.get('email',''),
            request.form.get('plan',''), request.form.get('plan_type',''),
            float(request.form.get('value',0)), int(request.form.get('payment_day',1)),
            request.form.get('payment_method','pix'), request.form.get('status','active'),
            request.form.get('start_date',''), request.form.get('notes',''), cid
        ))
        conn.commit(); conn.close()
        return redirect(url_for('client_detail', cid=cid))
    conn.close()
    return render_template('client_form.html', client=client)

@app.route('/clients/<cid>/delete', methods=['POST'])
@login_required
def delete_client(cid):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.execute("DELETE FROM payments WHERE client_id=?", (cid,))
    conn.execute("DELETE FROM recordings WHERE client_id=?", (cid,))
    conn.execute("DELETE FROM reports WHERE client_id=?", (cid,))
    conn.commit(); conn.close()
    return redirect(url_for('clients'))

# ─────────────────────────────────────────
# PAYMENTS
# ─────────────────────────────────────────
@app.route('/payments')
@login_required
def payments():
    conn = get_db()
    today = date.today().isoformat()
    all_payments = conn.execute("""
        SELECT p.*, c.name as client_name FROM payments p
        JOIN clients c ON c.id=p.client_id
        ORDER BY p.due_date DESC
    """).fetchall()
    conn.close()
    return render_template('payments.html', payments=all_payments, today=today)

@app.route('/payments/<pid>/pay', methods=['POST'])
@login_required
def mark_paid(pid):
    conn = get_db()
    conn.execute("UPDATE payments SET status='paid', paid_date=? WHERE id=?",
                 (date.today().isoformat(), pid))
    conn.commit()
    # Get client info to generate next payment
    pay = conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
    client = conn.execute("SELECT * FROM clients WHERE id=?", (pay['client_id'],)).fetchone()
    if client:
        due = date.fromisoformat(pay['due_date'])
        next_due = (due.replace(day=1) + timedelta(days=32)).replace(day=client['payment_day'])
        # Check if next payment already exists
        existing = conn.execute(
            "SELECT id FROM payments WHERE client_id=? AND due_date=?",
            (client['id'], next_due.isoformat())).fetchone()
        if not existing:
            conn.execute("""INSERT INTO payments (id,client_id,amount,due_date,method,status,created_at)
                VALUES (?,?,?,?,?,?,?)""", (
                str(uuid.uuid4()), client['id'], client['value'],
                next_due.isoformat(), client['payment_method'],
                'pending', datetime.now().isoformat()
            ))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for('payments'))

@app.route('/payments/new', methods=['POST'])
@login_required
def new_payment():
    conn = get_db()
    conn.execute("""INSERT INTO payments (id,client_id,amount,due_date,method,status,notes,created_at)
        VALUES (?,?,?,?,?,?,?,?)""", (
        str(uuid.uuid4()),
        request.form['client_id'], float(request.form.get('amount',0)),
        request.form['due_date'], request.form.get('method','pix'),
        'pending', request.form.get('notes',''),
        datetime.now().isoformat()
    ))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for('payments'))

# ─────────────────────────────────────────
# RECEIPT (HTML print)
# ─────────────────────────────────────────
@app.route('/payments/<pid>/receipt')
@login_required
def receipt(pid):
    conn = get_db()
    pay = conn.execute("""
        SELECT p.*, c.name as client_name, c.whatsapp, c.plan, c.plan_type
        FROM payments p JOIN clients c ON c.id=p.client_id WHERE p.id=?
    """, (pid,)).fetchone()
    conn.close()
    return render_template('receipt.html', pay=pay)

# ─────────────────────────────────────────
# RECORDINGS / AGENDA
# ─────────────────────────────────────────
@app.route('/agenda')
@login_required
def agenda():
    conn = get_db()
    recordings = conn.execute("""
        SELECT r.*, c.name as client_name, c.instagram FROM recordings r
        JOIN clients c ON c.id=r.client_id
        ORDER BY r.date ASC, r.time ASC
    """).fetchall()
    clients = conn.execute("SELECT id, name FROM clients WHERE status='active' ORDER BY name").fetchall()
    conn.close()
    return render_template('agenda.html', recordings=recordings, clients=clients)

@app.route('/agenda/new', methods=['POST'])
@login_required
def new_recording():
    conn = get_db()
    conn.execute("""INSERT INTO recordings (id,client_id,date,time,address,notes,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)""", (
        str(uuid.uuid4()),
        request.form['client_id'], request.form['date'],
        request.form.get('time',''), request.form.get('address',''),
        request.form.get('notes',''), 'scheduled',
        datetime.now().isoformat()
    ))
    conn.commit(); conn.close()
    return redirect(url_for('agenda'))

@app.route('/agenda/<rid>/status', methods=['POST'])
@login_required
def update_recording_status(rid):
    status = request.form.get('status','scheduled')
    conn = get_db()
    conn.execute("UPDATE recordings SET status=? WHERE id=?", (status, rid))
    conn.commit(); conn.close()
    return redirect(url_for('agenda'))

@app.route('/agenda/<rid>/delete', methods=['POST'])
@login_required
def delete_recording(rid):
    conn = get_db()
    conn.execute("DELETE FROM recordings WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return redirect(url_for('agenda'))

# ─────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    conn = get_db()
    clients = conn.execute("SELECT id, name, plan_type FROM clients WHERE status='active' ORDER BY name").fetchall()
    all_reports = conn.execute("""
        SELECT r.*, c.name as client_name, c.plan_type FROM reports r
        JOIN clients c ON c.id=r.client_id
        ORDER BY r.year DESC, r.month DESC, c.name ASC
    """).fetchall()
    conn.close()
    return render_template('reports.html', clients=clients, reports=all_reports)

@app.route('/reports/new', methods=['GET','POST'])
@login_required
def new_report():
    conn = get_db()
    clients = conn.execute("SELECT id, name, plan_type FROM clients WHERE status='active' ORDER BY name").fetchall()
    if request.method == 'POST':
        rid = str(uuid.uuid4())
        pt = request.form.get('plan_type','social')
        img1 = save_upload('img_post1')
        img2 = save_upload('img_post2')
        img3 = save_upload('img_post3')
        conn.execute("""INSERT INTO reports
            (id,client_id,month,year,report_type,
             followers,profile_visits,top_post1,top_post1_img,top_post2,top_post2_img,top_post3,top_post3_img,
             new_whatsapp_clients,reach,cost_per_result,invested_value,ctr,
             goal_min_followers,goal_ok_followers,goal_super_followers,
             goal_min_visits,goal_ok_visits,goal_super_visits,
             goal_min_clients,goal_ok_clients,goal_super_clients,
             goal_min_reach,goal_ok_reach,goal_super_reach,
             goal_min_ctr,goal_ok_ctr,goal_super_ctr,goal_max_cpr,
             notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            rid,
            request.form['client_id'],
            int(request.form['month']), int(request.form['year']),
            pt,
            int(request.form.get('followers',0) or 0),
            int(request.form.get('profile_visits',0) or 0),
            request.form.get('top_post1',''), img1,
            request.form.get('top_post2',''), img2,
            request.form.get('top_post3',''), img3,
            int(request.form.get('new_whatsapp_clients',0) or 0),
            int(request.form.get('reach',0) or 0),
            float(request.form.get('cost_per_result',0) or 0),
            float(request.form.get('invested_value',0) or 0),
            float(request.form.get('ctr',0) or 0),
            int(request.form.get('goal_min_followers',0) or 0),
            int(request.form.get('goal_ok_followers',0) or 0),
            int(request.form.get('goal_super_followers',0) or 0),
            int(request.form.get('goal_min_visits',0) or 0),
            int(request.form.get('goal_ok_visits',0) or 0),
            int(request.form.get('goal_super_visits',0) or 0),
            int(request.form.get('goal_min_clients',0) or 0),
            int(request.form.get('goal_ok_clients',0) or 0),
            int(request.form.get('goal_super_clients',0) or 0),
            int(request.form.get('goal_min_reach',0) or 0),
            int(request.form.get('goal_ok_reach',0) or 0),
            int(request.form.get('goal_super_reach',0) or 0),
            float(request.form.get('goal_min_ctr',0) or 0),
            float(request.form.get('goal_ok_ctr',0) or 0),
            float(request.form.get('goal_super_ctr',0) or 0),
            float(request.form.get('goal_max_cpr',0) or 0),
            request.form.get('notes',''),
            datetime.now().isoformat()
        ))
        conn.commit(); conn.close()
        return redirect(url_for('view_report', rid=rid))
    conn.close()
    return render_template('report_form.html', clients=clients, report=None)

@app.route('/reports/<rid>')
@login_required
def view_report(rid):
    conn = get_db()
    report_row = conn.execute("""
        SELECT r.*, c.name as client_name, c.instagram, c.plan, c.plan_type
        FROM reports r JOIN clients c ON c.id=r.client_id WHERE r.id=?
    """, (rid,)).fetchone()
    history_rows = conn.execute("""
        SELECT * FROM reports WHERE client_id=? AND report_type=?
        ORDER BY year ASC, month ASC LIMIT 12
    """, (report_row['client_id'], report_row['report_type'])).fetchall()

    # Get previous month report for comparison
    prev_month = report_row['month'] - 1 if report_row['month'] > 1 else 12
    prev_year = report_row['year'] if report_row['month'] > 1 else report_row['year'] - 1
    prev_row = conn.execute("""
        SELECT * FROM reports WHERE client_id=? AND report_type=? AND month=? AND year=?
    """, (report_row['client_id'], report_row['report_type'], prev_month, prev_year)).fetchone()

    conn.close()
    report = dict(report_row)
    history = [dict(r) for r in history_rows]
    prev = dict(prev_row) if prev_row else None
    months_pt = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    return render_template('report_view.html', report=report, history=history,
                           prev=prev, months_pt=months_pt)

@app.route('/reports/<rid>/delete', methods=['POST'])
@login_required
def delete_report(rid):
    conn = get_db()
    conn.execute("DELETE FROM reports WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return redirect(url_for('reports'))

# ─────────────────────────────────────────
# API for charts
# ─────────────────────────────────────────
@app.route('/api/client_plan_type/<cid>')
@login_required
def client_plan_type(cid):
    conn = get_db()
    c = conn.execute("SELECT plan_type FROM clients WHERE id=?", (cid,)).fetchone()
    conn.close()
    return jsonify({'plan_type': c['plan_type'] if c else ''})

@app.context_processor
def inject_globals():
    now = datetime.now()
    return dict(
        now_month=now.month,
        now_year=now.year,
        today=date.today().isoformat(),
        date=date,
        enumerate=enumerate
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)

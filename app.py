from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import sqlite3, hashlib, os, uuid, json
from datetime import datetime, date, timedelta
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'yuna_crm_2025')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, 'yuna.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_IMG = {'png','jpg','jpeg','gif','webp'}
ALLOWED_DOC = {'pdf','png','jpg','jpeg'}

def allowed(fn, exts): return '.' in fn and fn.rsplit('.',1)[1].lower() in exts
def save_file(field, exts=None):
    exts = exts or ALLOWED_IMG
    f = request.files.get(field)
    if f and f.filename and allowed(f.filename, exts):
        ext = f.filename.rsplit('.',1)[1].lower()
        fname = f'{uuid.uuid4().hex}.{ext}'
        f.save(os.path.join(UPLOAD_FOLDER, fname))
        return f'uploads/{fname}'
    return None

def get_db():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row; return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,name TEXT,role TEXT DEFAULT "admin",created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,name TEXT NOT NULL,instagram TEXT,plan TEXT,plan_type TEXT,value REAL,payment_day INTEGER DEFAULT 10,payment_method TEXT DEFAULT "pix",status TEXT DEFAULT "active",start_date TEXT,notes TEXT,contract_file TEXT,prepaid_months INTEGER DEFAULT 0,created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments(id TEXT PRIMARY KEY,client_id TEXT,amount REAL,due_date TEXT,paid_date TEXT,method TEXT,status TEXT DEFAULT "pending",notes TEXT,reminder_3d_sent INTEGER DEFAULT 0,reminder_day_sent INTEGER DEFAULT 0,created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS recordings(id TEXT PRIMARY KEY,client_id TEXT,date TEXT,time TEXT,address TEXT,notes TEXT,status TEXT DEFAULT "scheduled",created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS editorial_calendar(id TEXT PRIMARY KEY,client_id TEXT,year INTEGER,month INTEGER,day INTEGER,content TEXT,content_type TEXT DEFAULT "post",status TEXT DEFAULT "planned",created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS traffic_weeks(id TEXT PRIMARY KEY,client_id TEXT,year INTEGER,month INTEGER,week INTEGER,videos TEXT,created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS media_library(id TEXT PRIMARY KEY,client_id TEXT,file_path TEXT,file_type TEXT,title TEXT,notes TEXT,created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,client_id TEXT,month INTEGER,year INTEGER,report_type TEXT,followers INTEGER DEFAULT 0,profile_visits INTEGER DEFAULT 0,ig_messages INTEGER DEFAULT 0,top_post_img TEXT,top_post_desc TEXT,impressions INTEGER DEFAULT 0,new_messages INTEGER DEFAULT 0,ctr REAL DEFAULT 0,cpc REAL DEFAULT 0,avg_frequency REAL DEFAULT 0,best_ad_img TEXT,best_ad_desc TEXT,goal_min_clients INTEGER DEFAULT 0,goal_ok_clients INTEGER DEFAULT 0,goal_super_clients INTEGER DEFAULT 0,goal_min_ctr REAL DEFAULT 0,goal_ok_ctr REAL DEFAULT 0,goal_super_ctr REAL DEFAULT 0,goal_min_cpc REAL DEFAULT 0,goal_ok_cpc REAL DEFAULT 0,goal_super_cpc REAL DEFAULT 0,notes TEXT,created_at TEXT)''')
    for m in ["ALTER TABLE clients ADD COLUMN contract_file TEXT","ALTER TABLE clients ADD COLUMN prepaid_months INTEGER DEFAULT 0","ALTER TABLE payments ADD COLUMN reminder_3d_sent INTEGER DEFAULT 0","ALTER TABLE payments ADD COLUMN reminder_day_sent INTEGER DEFAULT 0"]:
        try: c.execute(m)
        except: pass
    try:
        c.execute("INSERT INTO users(id,username,password,name,role,created_at) VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()),'Yunabbc',hashlib.sha256('#Yunabbc26'.encode()).hexdigest(),'Administrador','admin',datetime.now().isoformat()))
    except: pass
    conn.commit(); conn.close()

init_db()

@app.context_processor
def ctx():
    now=datetime.now()
    return dict(now_month=now.month,now_year=now.year,today=date.today().isoformat(),date=date,enumerate=enumerate,json=json,abs=abs)

def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a,**k)
    return dec

@app.route('/login',methods=['GET','POST'])
def login():
    error=None
    if request.method=='POST':
        u,p=request.form.get('username','').strip(),request.form.get('password','')
        conn=get_db()
        user=conn.execute("SELECT * FROM users WHERE username=? AND password=?",(u,hashlib.sha256(p.encode()).hexdigest())).fetchone()
        conn.close()
        if user:
            session.update({'user_id':user['id'],'username':user['username'],'name':user['name']})
            return redirect(url_for('dashboard'))
        error='Usuário ou senha incorretos.'
    return render_template('login.html',error=error)

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    conn=get_db(); today=date.today(); ms=today.replace(day=1).isoformat()
    active=conn.execute("SELECT COUNT(*) FROM clients WHERE status='active'").fetchone()[0]
    cancelled=conn.execute("SELECT COUNT(*) FROM clients WHERE status='cancelled'").fetchone()[0]
    mrr=conn.execute("SELECT COALESCE(SUM(value),0) FROM clients WHERE status='active'").fetchone()[0]
    paid_month=conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_date>=?",(ms,)).fetchone()[0]
    overdue_count=conn.execute("SELECT COUNT(*) FROM payments WHERE status='pending' AND due_date<?",(today.isoformat(),)).fetchone()[0]
    social_c=conn.execute("SELECT COUNT(*) FROM clients WHERE status='active' AND plan_type='social'").fetchone()[0]
    trafego_c=conn.execute("SELECT COUNT(*) FROM clients WHERE status='active' AND plan_type='trafego'").fetchone()[0]
    site_c=conn.execute("SELECT COUNT(*) FROM clients WHERE status='active' AND plan_type='site'").fetchone()[0]
    other_c=conn.execute("SELECT COUNT(*) FROM clients WHERE status='active' AND plan_type NOT IN ('social','trafego','site')").fetchone()[0]
    months_data=[]
    for i in range(5,-1,-1):
        d=(today.replace(day=1)-timedelta(days=i*28)).replace(day=1)
        label=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][d.month-1]
        val=conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND strftime('%Y-%m',paid_date)=?",(d.strftime('%Y-%m'),)).fetchone()[0]
        months_data.append({'month':label,'value':float(val)})
    recordings=conn.execute("SELECT r.*,c.name as client_name FROM recordings r JOIN clients c ON c.id=r.client_id WHERE r.date>=? AND r.status='scheduled' ORDER BY r.date ASC LIMIT 5",(today.isoformat(),)).fetchall()
    overdue_pays=conn.execute("SELECT p.*,c.name as client_name FROM payments p JOIN clients c ON c.id=p.client_id WHERE p.status='pending' AND p.due_date<? ORDER BY p.due_date ASC LIMIT 5",(today.isoformat(),)).fetchall()
    conn.close()
    return render_template('dashboard.html',active=active,cancelled=cancelled,mrr=mrr,paid_month=paid_month,overdue_count=overdue_count,social_c=social_c,trafego_c=trafego_c,site_c=site_c,other_c=other_c,months_data=months_data,recordings=recordings,overdue_pays=overdue_pays)

@app.route('/clients')
@login_required
def clients():
    q=request.args.get('q',''); status=request.args.get('status','all'); ptype=request.args.get('type','all')
    conn=get_db(); sql="SELECT * FROM clients WHERE 1=1"; params=[]
    if q: sql+=" AND (name LIKE ? OR instagram LIKE ?)"; params+=[f'%{q}%']*2
    if status!='all': sql+=" AND status=?"; params.append(status)
    if ptype!='all': sql+=" AND plan_type=?"; params.append(ptype)
    all_clients=conn.execute(sql+' ORDER BY name',params).fetchall(); conn.close()
    return render_template('clients.html',clients=all_clients,q=q,status=status,ptype=ptype)

@app.route('/clients/new',methods=['GET','POST'])
@login_required
def new_client():
    if request.method=='POST':
        conn=get_db(); cid=str(uuid.uuid4())
        contract=save_file('contract_file',ALLOWED_DOC)
        prepaid=int(request.form.get('prepaid_months',0) or 0)
        val=float(request.form.get('value',0) or 0)
        pday=int(request.form.get('payment_day',10) or 10)
        conn.execute("INSERT INTO clients(id,name,instagram,plan,plan_type,value,payment_day,payment_method,status,start_date,notes,contract_file,prepaid_months,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid,request.form['name'],request.form.get('instagram',''),request.form.get('plan',''),request.form.get('plan_type',''),val,pday,request.form.get('payment_method','pix'),request.form.get('status','active'),request.form.get('start_date',date.today().isoformat()),request.form.get('notes',''),contract,prepaid,datetime.now().isoformat()))
        today=date.today()
        try:
            due=today.replace(day=pday)
            if due<=today: due=(due.replace(day=1)+timedelta(days=32)).replace(day=pday)
        except: due=today+timedelta(days=30)
        conn.execute("INSERT INTO payments(id,client_id,amount,due_date,method,status,created_at) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),cid,val,due.isoformat(),request.form.get('payment_method','pix'),'pending',datetime.now().isoformat()))
        conn.commit(); conn.close()
        return redirect(url_for('client_detail',cid=cid))
    return render_template('client_form.html',client=None)

@app.route('/clients/<cid>')
@login_required
def client_detail(cid):
    conn=get_db()
    client=conn.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    payments=conn.execute("SELECT * FROM payments WHERE client_id=? ORDER BY due_date DESC",(cid,)).fetchall()
    recordings=conn.execute("SELECT * FROM recordings WHERE client_id=? ORDER BY date DESC LIMIT 10",(cid,)).fetchall()
    reports=conn.execute("SELECT * FROM reports WHERE client_id=? ORDER BY year DESC,month DESC",(cid,)).fetchall()
    media=conn.execute("SELECT * FROM media_library WHERE client_id=? ORDER BY created_at DESC LIMIT 12",(cid,)).fetchall()
    conn.close()
    return render_template('client_detail.html',client=client,payments=payments,recordings=recordings,reports=reports,media=media,today=date.today().isoformat())

@app.route('/clients/<cid>/edit',methods=['GET','POST'])
@login_required
def edit_client(cid):
    conn=get_db(); client=conn.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    if request.method=='POST':
        contract=save_file('contract_file',ALLOWED_DOC) or client['contract_file']
        conn.execute("UPDATE clients SET name=?,instagram=?,plan=?,plan_type=?,value=?,payment_day=?,payment_method=?,status=?,start_date=?,notes=?,contract_file=?,prepaid_months=? WHERE id=?",
            (request.form['name'],request.form.get('instagram',''),request.form.get('plan',''),request.form.get('plan_type',''),float(request.form.get('value',0) or 0),int(request.form.get('payment_day',10) or 10),request.form.get('payment_method','pix'),request.form.get('status','active'),request.form.get('start_date',''),request.form.get('notes',''),contract,int(request.form.get('prepaid_months',0) or 0),cid))
        conn.commit(); conn.close(); return redirect(url_for('client_detail',cid=cid))
    conn.close(); return render_template('client_form.html',client=client)

@app.route('/clients/<cid>/delete',methods=['POST'])
@login_required
def delete_client(cid):
    conn=get_db()
    for t in ['payments','recordings','editorial_calendar','traffic_weeks','media_library','reports']:
        conn.execute(f"DELETE FROM {t} WHERE client_id=?",(cid,))
    conn.execute("DELETE FROM clients WHERE id=?",(cid,)); conn.commit(); conn.close()
    return redirect(url_for('clients'))

@app.route('/payments')
@login_required
def payments():
    conn=get_db(); today=date.today().isoformat()
    pays=conn.execute("SELECT p.*,c.name as client_name FROM payments p JOIN clients c ON c.id=p.client_id ORDER BY p.due_date DESC").fetchall()
    clients_list=conn.execute("SELECT id,name FROM clients WHERE status='active' ORDER BY name").fetchall()
    conn.close()
    return render_template('payments.html',payments=pays,today=today,clients=clients_list)

@app.route('/payments/<pid>/pay',methods=['POST'])
@login_required
def mark_paid(pid):
    conn=get_db(); conn.execute("UPDATE payments SET status='paid',paid_date=? WHERE id=?",(date.today().isoformat(),pid))
    pay=conn.execute("SELECT * FROM payments WHERE id=?",(pid,)).fetchone()
    client=conn.execute("SELECT * FROM clients WHERE id=?",(pay['client_id'],)).fetchone()
    if client:
        try:
            due=date.fromisoformat(pay['due_date']); nd=(due.replace(day=1)+timedelta(days=32)).replace(day=client['payment_day'])
        except: nd=date.today()+timedelta(days=30)
        if not conn.execute("SELECT id FROM payments WHERE client_id=? AND due_date=?",(client['id'],nd.isoformat())).fetchone():
            conn.execute("INSERT INTO payments(id,client_id,amount,due_date,method,status,created_at) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),client['id'],client['value'],nd.isoformat(),client['payment_method'],'pending',datetime.now().isoformat()))
    conn.commit(); conn.close(); return redirect(request.referrer or url_for('payments'))

@app.route('/payments/new',methods=['POST'])
@login_required
def new_payment():
    conn=get_db()
    conn.execute("INSERT INTO payments(id,client_id,amount,due_date,method,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),request.form['client_id'],float(request.form.get('amount',0)),request.form['due_date'],request.form.get('method','pix'),'pending',request.form.get('notes',''),datetime.now().isoformat()))
    conn.commit(); conn.close(); return redirect(request.referrer or url_for('payments'))

@app.route('/payments/<pid>/receipt')
@login_required
def receipt(pid):
    conn=get_db(); pay=conn.execute("SELECT p.*,c.name as client_name,c.plan,c.plan_type FROM payments p JOIN clients c ON c.id=p.client_id WHERE p.id=?",(pid,)).fetchone(); conn.close()
    return render_template('receipt.html',pay=pay)

@app.route('/api/reminders')
@login_required
def get_reminders():
    conn=get_db(); today=date.today(); in3=(today+timedelta(days=3)).isoformat()
    pays=conn.execute("SELECT p.*,c.name as client_name FROM payments p JOIN clients c ON c.id=p.client_id WHERE p.status='pending' AND (p.due_date=? OR p.due_date=?) ORDER BY p.due_date",(today.isoformat(),in3)).fetchall()
    conn.close(); return jsonify([dict(p) for p in pays])

@app.route('/agenda')
@login_required
def agenda():
    conn=get_db()
    recs=conn.execute("SELECT r.*,c.name as client_name,c.instagram FROM recordings r JOIN clients c ON c.id=r.client_id ORDER BY r.date ASC,r.time ASC").fetchall()
    cls=conn.execute("SELECT id,name FROM clients WHERE status='active' ORDER BY name").fetchall()
    conn.close(); return render_template('agenda.html',recordings=recs,clients=cls)

@app.route('/agenda/new',methods=['POST'])
@login_required
def new_recording():
    conn=get_db()
    conn.execute("INSERT INTO recordings(id,client_id,date,time,address,notes,status,created_at) VALUES(?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),request.form['client_id'],request.form['date'],request.form.get('time',''),request.form.get('address',''),request.form.get('notes',''),'scheduled',datetime.now().isoformat()))
    conn.commit(); conn.close(); return redirect(url_for('agenda'))

@app.route('/agenda/<rid>/status',methods=['POST'])
@login_required
def update_rec_status(rid):
    conn=get_db(); conn.execute("UPDATE recordings SET status=? WHERE id=?",(request.form.get('status'),rid)); conn.commit(); conn.close(); return redirect(url_for('agenda'))

@app.route('/agenda/<rid>/delete',methods=['POST'])
@login_required
def delete_rec(rid):
    conn=get_db(); conn.execute("DELETE FROM recordings WHERE id=?",(rid,)); conn.commit(); conn.close(); return redirect(url_for('agenda'))

@app.route('/calendar/<cid>')
@login_required
def editorial_calendar(cid):
    conn=get_db(); client=conn.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    month=int(request.args.get('month',date.today().month)); year=int(request.args.get('year',date.today().year))
    entries=conn.execute("SELECT * FROM editorial_calendar WHERE client_id=? AND month=? AND year=?",(cid,month,year)).fetchall()
    conn.close(); return render_template('editorial_calendar.html',client=client,entries=entries,month=month,year=year)

@app.route('/calendar/<cid>/save',methods=['POST'])
@login_required
def save_cal(cid):
    conn=get_db(); eid=request.form.get('id') or str(uuid.uuid4())
    ex=conn.execute("SELECT id FROM editorial_calendar WHERE id=?",(eid,)).fetchone()
    if ex: conn.execute("UPDATE editorial_calendar SET content=?,content_type=?,status=? WHERE id=?",(request.form.get('content',''),request.form.get('content_type','post'),request.form.get('status','planned'),eid))
    else: conn.execute("INSERT INTO editorial_calendar(id,client_id,year,month,day,content,content_type,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(eid,cid,int(request.form['year']),int(request.form['month']),int(request.form['day']),request.form.get('content',''),request.form.get('content_type','post'),request.form.get('status','planned'),datetime.now().isoformat()))
    conn.commit(); conn.close(); return jsonify({'ok':True,'id':eid})

@app.route('/calendar/<cid>/delete/<eid>',methods=['POST'])
@login_required
def del_cal(cid,eid):
    conn=get_db(); conn.execute("DELETE FROM editorial_calendar WHERE id=?",(eid,)); conn.commit(); conn.close(); return jsonify({'ok':True})

@app.route('/traffic/<cid>')
@login_required
def traffic_weeks(cid):
    conn=get_db(); client=conn.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    month=int(request.args.get('month',date.today().month)); year=int(request.args.get('year',date.today().year))
    weeks=conn.execute("SELECT * FROM traffic_weeks WHERE client_id=? AND month=? AND year=? ORDER BY week",(cid,month,year)).fetchall()
    conn.close(); return render_template('traffic_weeks.html',client=client,weeks=weeks,month=month,year=year)

@app.route('/traffic/<cid>/save',methods=['POST'])
@login_required
def save_traffic(cid):
    conn=get_db(); week=int(request.form['week']); month=int(request.form['month']); year=int(request.form['year'])
    videos=[v for v in request.form.getlist('videos[]') if v.strip()][:5]
    ex=conn.execute("SELECT id FROM traffic_weeks WHERE client_id=? AND month=? AND year=? AND week=?",(cid,month,year,week)).fetchone()
    if ex: conn.execute("UPDATE traffic_weeks SET videos=? WHERE id=?",(json.dumps(videos),ex['id']))
    else: conn.execute("INSERT INTO traffic_weeks(id,client_id,year,month,week,videos,created_at) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),cid,year,month,week,json.dumps(videos),datetime.now().isoformat()))
    conn.commit(); conn.close(); return jsonify({'ok':True})

@app.route('/media/<cid>')
@login_required
def media_library(cid):
    conn=get_db(); client=conn.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone()
    media=conn.execute("SELECT * FROM media_library WHERE client_id=? ORDER BY created_at DESC",(cid,)).fetchall()
    conn.close(); return render_template('media_library.html',client=client,media=media)

@app.route('/media/<cid>/upload',methods=['POST'])
@login_required
def upload_media(cid):
    VIDEO_EXT={'mp4','mov','avi','webm'}
    fpath=save_file('file',ALLOWED_IMG|VIDEO_EXT)
    if fpath:
        ftype='video' if fpath.rsplit('.',1)[-1] in VIDEO_EXT else 'image'
        conn=get_db()
        conn.execute("INSERT INTO media_library(id,client_id,file_path,file_type,title,notes,created_at) VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),cid,fpath,ftype,request.form.get('title',''),request.form.get('notes',''),datetime.now().isoformat()))
        conn.commit(); conn.close()
    return redirect(url_for('media_library',cid=cid))

@app.route('/media/delete/<mid>',methods=['POST'])
@login_required
def delete_media(mid):
    conn=get_db(); m=conn.execute("SELECT * FROM media_library WHERE id=?",(mid,)).fetchone()
    if m:
        cid=m['client_id']
        try: os.remove(os.path.join(BASE_DIR,'static',m['file_path']))
        except: pass
        conn.execute("DELETE FROM media_library WHERE id=?",(mid,)); conn.commit(); conn.close()
        return redirect(url_for('media_library',cid=cid))
    conn.close(); return redirect(url_for('clients'))

@app.route('/reports')
@login_required
def reports():
    conn=get_db()
    cls=conn.execute("SELECT id,name,plan_type FROM clients WHERE status='active' ORDER BY name").fetchall()
    all_rep=conn.execute("SELECT r.*,c.name as client_name,c.plan_type FROM reports r JOIN clients c ON c.id=r.client_id ORDER BY r.year DESC,r.month DESC,c.name").fetchall()
    conn.close(); return render_template('reports.html',clients=cls,reports=all_rep)

@app.route('/reports/new',methods=['GET','POST'])
@login_required
def new_report():
    conn=get_db(); cls=conn.execute("SELECT id,name,plan_type FROM clients WHERE status='active' ORDER BY name").fetchall()
    if request.method=='POST':
        rid=str(uuid.uuid4()); pt=request.form.get('plan_type','social')
        top_img=save_file('top_post_img') if pt=='social' else None
        best_img=save_file('best_ad_img') if pt=='trafego' else None
        conn.execute("INSERT INTO reports(id,client_id,month,year,report_type,followers,profile_visits,ig_messages,top_post_img,top_post_desc,impressions,new_messages,ctr,cpc,avg_frequency,best_ad_img,best_ad_desc,goal_min_clients,goal_ok_clients,goal_super_clients,goal_min_ctr,goal_ok_ctr,goal_super_ctr,goal_min_cpc,goal_ok_cpc,goal_super_cpc,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid,request.form['client_id'],int(request.form['month']),int(request.form['year']),pt,int(request.form.get('followers',0) or 0),int(request.form.get('profile_visits',0) or 0),int(request.form.get('ig_messages',0) or 0),top_img,request.form.get('top_post_desc',''),int(request.form.get('impressions',0) or 0),int(request.form.get('new_messages',0) or 0),float(request.form.get('ctr',0) or 0),float(request.form.get('cpc',0) or 0),float(request.form.get('avg_frequency',0) or 0),best_img,request.form.get('best_ad_desc',''),int(request.form.get('goal_min_clients',0) or 0),int(request.form.get('goal_ok_clients',0) or 0),int(request.form.get('goal_super_clients',0) or 0),float(request.form.get('goal_min_ctr',0) or 0),float(request.form.get('goal_ok_ctr',0) or 0),float(request.form.get('goal_super_ctr',0) or 0),float(request.form.get('goal_min_cpc',0) or 0),float(request.form.get('goal_ok_cpc',0) or 0),float(request.form.get('goal_super_cpc',0) or 0),request.form.get('notes',''),datetime.now().isoformat()))
        conn.commit(); conn.close(); return redirect(url_for('view_report',rid=rid))
    conn.close(); return render_template('report_form.html',clients=cls)

@app.route('/reports/<rid>')
@login_required
def view_report(rid):
    conn=get_db()
    rr=conn.execute("SELECT r.*,c.name as client_name,c.instagram,c.plan,c.plan_type FROM reports r JOIN clients c ON c.id=r.client_id WHERE r.id=?",(rid,)).fetchone()
    history=conn.execute("SELECT * FROM reports WHERE client_id=? AND report_type=? ORDER BY year ASC,month ASC LIMIT 12",(rr['client_id'],rr['report_type'])).fetchall()
    pm=rr['month']-1 if rr['month']>1 else 12; py=rr['year'] if rr['month']>1 else rr['year']-1
    prev=conn.execute("SELECT * FROM reports WHERE client_id=? AND report_type=? AND month=? AND year=?",(rr['client_id'],rr['report_type'],pm,py)).fetchone()
    conn.close()
    mpt=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    return render_template('report_view.html',report=dict(rr),history=[dict(r) for r in history],prev=dict(prev) if prev else None,months_pt=mpt)

@app.route('/reports/<rid>/delete',methods=['POST'])
@login_required
def delete_report(rid):
    conn=get_db(); conn.execute("DELETE FROM reports WHERE id=?",(rid,)); conn.commit(); conn.close(); return redirect(url_for('reports'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER,filename)

if __name__=='__main__': app.run(debug=True,port=5001)

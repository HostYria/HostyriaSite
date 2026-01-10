import os
import json
import re
import subprocess
import psutil
import socket
import sys
import hashlib
import secrets
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, request, jsonify, session, redirect, url_for, make_response
from models import db, User, RememberToken, UserFile

def sync_files_to_db(username, server_folder):
    """Sync filesystem files to database for a specific server"""
    user_servers_dir = get_user_servers_dir(username)
    server_path = os.path.join(user_servers_dir, server_folder)
    if not os.path.exists(server_path):
        return
        
    for filename in os.listdir(server_path):
        if filename in ["meta.json", "server.log"]:
            continue
        file_path = os.path.join(server_path, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
                existing = UserFile.query.filter_by(
                    username=username, 
                    server_folder=server_folder, 
                    filename=filename
                ).first()
                if existing:
                    existing.content = content
                else:
                    new_file = UserFile(
                        username=username,
                        server_folder=server_folder,
                        filename=filename,
                        content=content
                    )
                    db.session.add(new_file)
    db.session.commit()

def save_file_to_db_and_fs(username, server_folder, filename, content_bytes):
    """Save file exclusively to DB"""
    # Save to DB
    existing = UserFile.query.filter_by(
        username=username, 
        server_folder=server_folder, 
        filename=filename
    ).first()
    if existing:
        existing.content = content_bytes
    else:
        new_file = UserFile(
            username=username,
            server_folder=server_folder,
            filename=filename,
            content=content_bytes
        )
        db.session.add(new_file)
    db.session.commit()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, "USERS")
os.makedirs(USERS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=BASE_DIR)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
if not app.config["SQLALCHEMY_DATABASE_URI"]:
    raise ValueError("DATABASE_URL environment variable is not set!")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

running_procs = {}

# الحساب الرئيسي (المسؤول)
ADMIN_USERNAME = "abodiab"
ADMIN_PASSWORD = "ahmad2005sh@@A"

# ============== Helper Functions ==============

def init_users_db():
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=ADMIN_USERNAME,
                password=hash_password(ADMIN_PASSWORD),
                theme="premium",
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_remember_token(username):
    """إنشاء رمز تذكر جديد للمستخدم"""
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(days=30)
    
    new_token = RememberToken(
        token=token,
        username=username,
        expires_at=expires
    )
    db.session.add(new_token)
    db.session.commit()
    return token

def validate_remember_token(token_str):
    """التحقق من رمز التذكر"""
    token_data = RememberToken.query.get(token_str)
    if not token_data:
        return None
    
    if datetime.now() > token_data.expires_at:
        db.session.delete(token_data)
        db.session.commit()
        return None
    
    token_data.last_used = datetime.now()
    db.session.commit()
    return token_data.username

def delete_remember_token(token_str):
    """حذف رمز التذكر"""
    token_data = RememberToken.query.get(token_str)
    if token_data:
        db.session.delete(token_data)
        db.session.commit()

def delete_all_user_tokens(username):
    """حذف جميع رموز التذكر للمستخدم"""
    RememberToken.query.filter_by(username=username).delete()
    db.session.commit()

def register_user(username, password, created_by_admin=False):
    if User.query.filter_by(username=username).first():
        return False, "المستخدم موجود بالفعل"
    
    if len(password) < 6:
        return False, "كلمة المرور يجب أن تكون 6 أحرف على الأقل"
    
    new_user = User(
        username=username,
        password=hash_password(password),
        is_admin=(username == ADMIN_USERNAME),
        theme="blue"
    )
    db.session.add(new_user)
    db.session.commit()
    
    user_dir = os.path.join(USERS_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, "SERVERS"), exist_ok=True)
    
    return True, "تم إنشاء الحساب بنجاح"

def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if not user:
        return False, "المستخدم غير موجود"
    
    if user.password != hash_password(password):
        return False, "كلمة المرور غير صحيحة"
    
    user.last_login = datetime.now()
    db.session.commit()
    return True, "تم تسجيل الدخول بنجاح"

def is_admin(username):
    user = User.query.filter_by(username=username).first()
    return user.is_admin if user else False


def get_user_servers_dir(username):
    return os.path.join(USERS_DIR, username, "SERVERS")

def ensure_user_servers_dir():
    if 'username' not in session:
        return None
    user_dir = get_user_servers_dir(session['username'])
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def sanitize_folder_name(name):
    if not name: return ""
    name = name.strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^A-Za-z0-9\-\_\.]", "", name)
    return name[:200]

def sanitize_filename(name):
    if not name: return ""
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9\-\_\.]", "", name)
    return name[:200]

def ensure_meta(folder):
    user_servers_dir = ensure_user_servers_dir()
    if not user_servers_dir:
        return None
    
    meta_path = os.path.join(user_servers_dir, folder, "meta.json")
    if not os.path.exists(meta_path):
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"display_name": folder, "startup_file": ""}, f)
    return meta_path

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: 
        return '127.0.0.1'

def load_servers_list():
    if 'username' not in session:
        return []
    
    user_servers_dir = ensure_user_servers_dir()
    if not user_servers_dir or not os.path.exists(user_servers_dir):
        return []
    
    try:
        entries = [d for d in os.listdir(user_servers_dir) 
                  if os.path.isdir(os.path.join(user_servers_dir, d))]
    except: 
        entries = []
    
    servers = []
    for i, folder in enumerate(entries, start=1):
        ensure_meta(folder)
        meta_path = os.path.join(user_servers_dir, folder, "meta.json")
        display_name, startup_file = folder, ""
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                display_name = meta.get("display_name", folder)
                startup_file = meta.get("startup_file", "")
        except: 
            pass
        servers.append({
            "id": i, 
            "title": display_name, 
            "folder": folder, 
            "subtitle": f"Node-{i} · Local", 
            "startup_file": startup_file
        })
    return servers

# ============== Routes ==============

@app.before_request
def check_remember_token():
    """فحص رمز التذكر قبل كل طلب"""
    if 'username' in session:
        return
    
    remember_token = request.cookies.get('remember_token')
    if remember_token:
        username = validate_remember_token(remember_token)
        if username:
            session['username'] = username
            session.permanent = True

@app.route("/")
def home():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    # إذا كان المستخدم مسؤولاً، توجيهه لوحة إنشاء الحسابات
    if is_admin(session['username']):
        return send_from_directory(BASE_DIR, "admin_panel.html")
    
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/index.html")
def serve_index():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    if is_admin(session['username']):
        return redirect(url_for('home'))
    
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/login")
def login_page():
    if 'username' in session:
        return redirect(url_for('home'))
    return send_from_directory(BASE_DIR, "login.html")

@app.route("/admin")
def admin_panel():
    if 'username' not in session or not is_admin(session['username']):
        return redirect(url_for('login_page'))
    return send_from_directory(BASE_DIR, "admin_panel.html")

@app.route("/api/register", methods=["POST"])
def api_register():
    # فقط المسؤول يمكنه إنشاء حسابات
    if 'username' not in session or not is_admin(session['username']):
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({"success": False, "message": "اسم المستخدم وكلمة المرور مطلوبان"})
    
    success, message = register_user(username, password, created_by_admin=True)
    return jsonify({"success": success, "message": message})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    remember_me = data.get("remember_me", False)
    
    if not username or not password:
        return jsonify({"success": False, "message": "اسم المستخدم وكلمة المرور مطلوبان"})
    
    success, message = authenticate_user(username, password)
    if success:
        session['username'] = username
        session.permanent = True  # تفعيل الجلسة الدائمة
        
        response_data = {
            "success": True, 
            "message": message,
            "username": username,
            "is_admin": is_admin(username)
        }
        
        if remember_me:
            token = create_remember_token(username)
            response = make_response(jsonify(response_data))
            response.set_cookie(
                'remember_token',
                token,
                max_age=30*24*60*60,
                httponly=True,
                secure=False,
                samesite='Strict'
            )
            return response
        
        return jsonify(response_data)
    
    return jsonify({"success": False, "message": message})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    username = session.get('username')
    
    if username:
        delete_all_user_tokens(username)
    
    session.pop('username', None)
    
    response = make_response(jsonify({"success": True, "message": "تم تسجيل الخروج"}))
    response.set_cookie('remember_token', '', expires=0)
    
    return response

@app.route("/api/current_user")
def api_current_user():
    if 'username' in session:
        admin = is_admin(session['username'])
        return jsonify({
            "success": True, 
            "username": session['username'],
            "is_admin": admin,
            "has_remember_token": bool(request.cookies.get('remember_token'))
        })
    return jsonify({"success": False})

@app.route("/api/user/settings", methods=["GET", "POST"])
def user_settings():
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return jsonify({"success": False, "message": "المستخدم غير موجود"}), 404

    if request.method == "GET":
        return jsonify({
            "success": True,
            "username": user.username,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "theme": user.theme,
            "is_admin": user.is_admin
        })
    
    data = request.get_json()
    user.theme = data.get("theme", "blue")
    db.session.commit()
    
    return jsonify({"success": True, "message": "تم تحديث الإعدادات"})

# ============== Protected Routes ==============

@app.route("/servers")
def get_servers():
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    return jsonify({"success": True, "servers": load_servers_list()})

@app.route("/add", methods=["POST"])
def add_server():
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    folder = sanitize_folder_name(name)
    
    user_servers_dir = ensure_user_servers_dir()
    target = os.path.join(user_servers_dir, folder)
    
    if os.path.exists(target): 
        return jsonify({"success": False, "message": "Exists"}), 409
    
    os.makedirs(target)
    ensure_meta(folder)
    open(os.path.join(target, "server.log"), "w").close()
    return jsonify({"success": True, "servers": load_servers_list()})

@app.route("/server/stats/<folder>")
def get_stats(folder):
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    
    proc_key = f"{session['username']}_{folder}"
    proc = running_procs.get(proc_key)
    running = False
    cpu, mem = "0%", "0 MB"
    
    if proc and psutil.pid_exists(proc.pid):
        try:
            p = psutil.Process(proc.pid)
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                running = True
                cpu = f"{p.cpu_percent(interval=None)}%"
                mem = f"{p.memory_info().rss / 1024 / 1024:.1f} MB"
        except: 
            pass
    
    # قراءة السجلات بطريقة بسيطة ومباشرة لضمان الموثوقية
    user_servers_dir = ensure_user_servers_dir()
    log_path = os.path.join(user_servers_dir, folder, "server.log")
    logs = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                # نأخذ آخر 20000 حرف فقط لتجنب الثقل
                logs = content[-20000:] if len(content) > 20000 else content
        except Exception as e:
            logs = f"Error reading logs: {str(e)}"
    
    return jsonify({
        "status": "Running" if running else "Offline", 
        "cpu": cpu, 
        "mem": mem, 
        "logs": logs, 
        "ip": get_ip()
    })

@app.route("/server/action/<folder>/<act>", methods=["POST"])
def server_action(folder, act):
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    
    proc_key = f"{session['username']}_{folder}"
    
    if proc_key in running_procs:
        try:
            p = psutil.Process(running_procs[proc_key].pid)
            for child in p.children(recursive=True): 
                child.kill()
            p.kill()
        except: 
            pass
        if act == "stop": 
            del running_procs[proc_key]
    
    if act == "stop": 
        return jsonify({"success": True})

    user_servers_dir = ensure_user_servers_dir()
    log_path = os.path.join(user_servers_dir, folder, "server.log")
    open(log_path, "w").close()
    
    meta_path = ensure_meta(folder)
    if not meta_path:
        return jsonify({"success": False, "message": "مجلد غير موجود"})
    
    with open(meta_path, "r") as f:
        startup = json.load(f).get("startup_file")
    
    if not startup: 
        return jsonify({"success": False, "message": "No main file set."})
    
    if not os.path.exists(os.path.join(user_servers_dir, folder, startup)):
        return jsonify({"success": False, "message": "الملف غير موجود"})
    
    # تجهيز متغيرات البيئة
    meta_path = ensure_meta(folder)
    with open(meta_path, "r") as f:
        meta = json.load(f)
    
    env_vars = os.environ.copy()
    env_vars.update(meta.get("env", {}))
    env_vars["PYTHONUNBUFFERED"] = "1"
    
    # استخدام PIPE وموضوع (Thread) لنقل المخرجات للملف مع Flush فوري
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", startup], 
            cwd=os.path.join(user_servers_dir, folder), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            env=env_vars,
            universal_newlines=True,
            bufsize=1
        )
        
        def pipe_to_file(p, path):
            try:
                # Use "a" mode to ensure we don't overwrite if multiple threads/processes start
                # or just stay with "w" but make sure it's handled carefully.
                # Actually, the user wants to see the output immediately.
                with open(path, "w", encoding="utf-8", buffering=1) as f:
                    for line in p.stdout:
                        f.write(line)
                        f.flush()
                        os.fsync(f.fileno()) # Force write to disk
            except Exception as e:
                print(f"Logging error: {e}")
        
        threading.Thread(target=pipe_to_file, args=(proc, log_path), daemon=True).start()
        running_procs[proc_key] = proc
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/files/list/<folder>")
def list_files(folder):
    if 'username' not in session:
        return jsonify([]), 401
    
    # Get all user files from DB without limit
    files = UserFile.query.filter_by(
        username=session['username'],
        server_folder=folder
    ).order_by(UserFile.filename).all()
    
    results = []
    for f in files:
        results.append({
            "name": f.filename,
            "size": f"{len(f.content) / 1024:.1f} KB"
        })
    return jsonify(results)

@app.route("/files/content/<folder>/<filename>")
def get_file_content(folder, filename):
    if 'username' not in session:
        return jsonify({"content": ""}), 401
    
    # Try DB first
    user_file = UserFile.query.filter_by(
        username=session['username'],
        server_folder=folder,
        filename=filename
    ).first()
    
    if user_file:
        try:
            return jsonify({"content": user_file.content.decode('utf-8')})
        except:
            return jsonify({"content": "[Binary Content]"})
            
    # Fallback to FS for operational files
    user_servers_dir = ensure_user_servers_dir()
    file_path = os.path.join(user_servers_dir, folder, filename)
    
    if not file_path.startswith(user_servers_dir):
        return jsonify({"content": ""}), 403
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return jsonify({"content": f.read()})
    except: 
        pass
    return jsonify({"content": ""})

@app.route("/files/save/<folder>/<filename>", methods=["POST"])
def save_file_content(folder, filename):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    data = request.json
    content = data.get('content', '')
    save_file_to_db_and_fs(session['username'], folder, filename, content.encode('utf-8'))
    return jsonify({"success": True})

@app.route("/files/upload/<folder>", methods=["POST"])
def upload_file(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    uploaded_files = request.files.getlist('files[]')
    results = []
    
    for f in uploaded_files:
        if f and f.filename:
            safe_name = sanitize_filename(f.filename)
            content = f.read()
            save_file_to_db_and_fs(session['username'], folder, safe_name, content)
            results.append({
                "name": safe_name,
                "size": f"{len(content) / 1024:.2f} KB"
            })
    
    return jsonify({
        "success": True, 
        "message": f"تم رفع {len(results)} ملف بنجاح",
        "uploaded_files": results
    })

@app.route("/files/upload-single/<folder>", methods=["POST"])
def upload_single_file(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "لم يتم اختيار ملف"})
    
    f = request.files['file']
    if f and f.filename:
        safe_name = sanitize_filename(f.filename)
        content = f.read()
        save_file_to_db_and_fs(session['username'], folder, safe_name, content)
        return jsonify({
            "success": True,
            "message": "تم رفع الملف بنجاح",
            "file": {
                "name": safe_name,
                "size": f"{len(content) / 1024:.2f} KB"
            }
        })
    return jsonify({"success": False, "message": "فشل رفع الملف"})

@app.route("/files/rename/<folder>", methods=["POST"])
def rename_file(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    data = request.get_json()
    old_name = data['old']
    new_name = data['new']
    
    # Rename in DB
    user_file = UserFile.query.filter_by(
        username=session['username'],
        server_folder=folder,
        filename=old_name
    ).first()
    if user_file:
        user_file.filename = new_name
        
    # Rename in FS (for operational files)
    user_servers_dir = ensure_user_servers_dir()
    old_path = os.path.join(user_servers_dir, folder, old_name)
    new_path = os.path.join(user_servers_dir, folder, new_name)
    if os.path.exists(old_path) and old_path.startswith(user_servers_dir):
        os.rename(old_path, new_path)
        
    db.session.commit()
    return jsonify({"success": True})

@app.route("/files/delete/<folder>", methods=["POST"])
def delete_file(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    data = request.get_json()
    filename = data['name']
    
    # Delete from DB
    UserFile.query.filter_by(
        username=session['username'],
        server_folder=folder,
        filename=filename
    ).delete()
    
    # Delete from FS (for operational files)
    user_servers_dir = ensure_user_servers_dir()
    file_path = os.path.join(user_servers_dir, folder, filename)
    if os.path.exists(file_path) and file_path.startswith(user_servers_dir):
        os.remove(file_path)
        
    db.session.commit()
    return jsonify({"success": True})

@app.route("/files/extract/<folder>/<filename>", methods=["POST"])
def extract_zip(folder, filename):
    if 'username' not in session:
        return jsonify({"success": False, "message": "غير مصرح"}), 401
    
    user_servers_dir = ensure_user_servers_dir()
    zip_path = os.path.join(user_servers_dir, folder, filename)
    extract_to = os.path.join(user_servers_dir, folder)
    
    if not zip_path.startswith(user_servers_dir):
        return jsonify({"success": False, "message": "مسار غير صالح"}), 403
    
    if not os.path.exists(zip_path) or not filename.lower().endswith('.zip'):
        return jsonify({"success": False, "message": "الملف غير موجود أو ليس Zip"}), 400
    
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return jsonify({"success": True, "message": "تم استخراج الملف بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": f"فشل الاستخراج: {str(e)}"})

@app.route("/files/install/<folder>", methods=["POST"])
def install_req(folder):
    """تثبيت تلقائي للمكاتب من ملف requirements.txt في خلفية النظام"""
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    user_servers_dir = ensure_user_servers_dir()
    req_path = os.path.join(user_servers_dir, folder, "requirements.txt")
    
    if not os.path.exists(req_path):
        return jsonify({"success": False, "message": "ملف requirements.txt غير موجود"})
    
    log_path = os.path.join(user_servers_dir, folder, "server.log")
    
    def run_installation():
        try:
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write("[SYSTEM] Starting Installation...\n")
                log_file.write(f"[SYSTEM] Installing packages from requirements.txt\n")
                log_file.write("="*50 + "\n")
                log_file.flush()

            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--break-system-packages"], 
                cwd=os.path.join(user_servers_dir, folder), 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            for line in proc.stdout:
                with open(log_path, "a", encoding="utf-8") as log_file:
                    log_file.write(line)
                    log_file.flush()
            
            proc.wait()
            
            with open(log_path, "a", encoding="utf-8") as log_file:
                if proc.returncode == 0:
                    log_file.write("\n" + "="*50 + "\n")
                    log_file.write("[SYSTEM] Installation completed successfully!\n")
                else:
                    log_file.write("\n" + "="*50 + "\n")
                    log_file.write(f"[SYSTEM] Installation failed with exit code: {proc.returncode}\n")
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"\n[ERROR] Internal error: {str(e)}\n")

    thread = threading.Thread(target=run_installation)
    thread.start()
    
    return jsonify({"success": True, "message": "تم بدء تثبيت المكتبات في الخلفية. يمكنك متابعة السجل."})

@app.route("/server/set-startup/<folder>", methods=["POST"])
def set_startup(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    meta_path = ensure_meta(folder)
    if not meta_path:
        return jsonify({"success": False}), 404
    
    with open(meta_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    m["startup_file"] = request.get_json().get('file', '')
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(m, f)
    return jsonify({"success": True})

@app.route("/server/delete/<folder>", methods=["POST"])
def delete_server(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    user_servers_dir = ensure_user_servers_dir()
    target = os.path.join(user_servers_dir, folder)
    
    if not target.startswith(user_servers_dir) or not os.path.exists(target):
        return jsonify({"success": False, "message": "Not found"}), 404
        
    # إيقاف السيرفر إذا كان يعمل
    proc_key = f"{session['username']}_{folder}"
    if proc_key in running_procs:
        try:
            p = psutil.Process(running_procs[proc_key].pid)
            for child in p.children(recursive=True): child.kill()
            p.kill()
        except: pass
        del running_procs[proc_key]
        
    import shutil
    shutil.rmtree(target)
    return jsonify({"success": True})

@app.route("/server/rename/<folder>", methods=["POST"])
def rename_server(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    data = request.get_json()
    new_display_name = data.get("name", "").strip()
    if not new_display_name:
        return jsonify({"success": False, "message": "Name required"}), 400
        
    meta_path = ensure_meta(folder)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    meta["display_name"] = new_display_name
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    return jsonify({"success": True})

@app.route("/server/env/<folder>", methods=["GET", "POST", "DELETE"])
def manage_env(folder):
    if 'username' not in session:
        return jsonify({"success": False}), 401
    
    user_servers_dir = ensure_user_servers_dir()
    meta_path = ensure_meta(folder)
    
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    
    if "env" not in meta:
        meta["env"] = {}
        
    if request.method == "GET":
        return jsonify({"success": True, "env": meta["env"]})
    
    if request.method == "POST":
        data = request.get_json()
        key = data.get("key", "").strip()
        value = data.get("value", "").strip()
        if not key:
            return jsonify({"success": False, "message": "Key is required"})
        meta["env"][key] = value
        
    elif request.method == "DELETE":
        data = request.get_json()
        key = data.get("key", "").strip()
        if key in meta["env"]:
            del meta["env"][key]
            
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    return jsonify({"success": True})

@app.route("/api/admin/users", methods=["GET"])
def get_all_users():
    """الحصول على قائمة جميع المستخدمين (للمسؤول فقط)"""
    if 'username' not in session or not is_admin(session['username']):
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    users = User.query.all()
    
    user_list = []
    for user in users:
        if user.username != ADMIN_USERNAME:  # عدم عرض المسؤول نفسه
            user_list.append({
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "created_by": "system"
            })
    
    return jsonify({"success": True, "users": user_list})

@app.route("/api/admin/delete-user", methods=["POST"])
def delete_user():
    """حذف مستخدم (للمسؤول فقط)"""
    if 'username' not in session or not is_admin(session['username']):
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    username_to_delete = data.get("username", "").strip()
    
    if not username_to_delete or username_to_delete == ADMIN_USERNAME:
        return jsonify({"success": False, "message": "لا يمكن حذف هذا المستخدم"})
    
    user = User.query.filter_by(username=username_to_delete).first()
    if not user:
        return jsonify({"success": False, "message": "المستخدم غير موجود"})
    
    # حذف المستخدم
    db.session.delete(user)
    db.session.commit()
    
    # Delete from DB
    UserFile.query.filter_by(
        username=username_to_delete
    ).delete()
    db.session.commit()
    
    # حذف مجلد المستخدم إذا كان موجوداً
    user_dir = os.path.join(USERS_DIR, username_to_delete)
    if os.path.exists(user_dir):
        import shutil
        shutil.rmtree(user_dir)
    
    return jsonify({"success": True, "message": "تم حذف المستخدم بنجاح"})

@app.route("/api/admin/user-files/<username>")
def admin_get_user_files(username):
    if 'username' not in session or not is_admin(session['username']):
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    user_dir = os.path.join(USERS_DIR, username)
    if not os.path.exists(user_dir):
        return jsonify({"success": False, "message": "مجلد المستخدم غير موجود"})
    
    files_list = []
    for root, dirs, files in os.walk(user_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, user_dir)
            files_list.append({
                "name": file,
                "path": rel_path,
                "full_path": full_path,
                "size": f"{os.path.getsize(full_path) / 1024:.1f} KB"
            })
    return jsonify({"success": True, "files": files_list})

@app.route("/api/admin/download-file")
def admin_download_file():
    if 'username' not in session or not is_admin(session['username']):
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    file_path = request.args.get("path")
    if not file_path or not file_path.startswith(USERS_DIR):
        return "Invalid path", 400
    
    if not os.path.exists(file_path):
        return "File not found", 404
        
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path), as_attachment=True)

if __name__ == "__main__":
    init_users_db()
    app.run(host="0.0.0.0", port=5000)

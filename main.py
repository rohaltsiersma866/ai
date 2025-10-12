import os
import re
import json
import time
import queue
import threading
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests
import openpyxl
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, abort, session, flash
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

from database import Database

# =======================
# CONFIG
# =======================
db = Database()

def load_api_keys_from_db():
    """Load API keys from database"""
    keys = []
    api_keys_data = db.get_all_api_keys()

    for api_data in api_keys_data:
        keys.append({
            "id": api_data["id"],
            "key": api_data["key_value"],
            "name": api_data["name"],
            "remaining": api_data["remaining_credits"],
            "total_used": api_data["total_used"],
            "status": api_data["status"],
            "last_credit_check": api_data["last_credit_check"]
        })

    return keys


API_KEYS = load_api_keys_from_db()
WARNING_THRESHOLD = 10
current_api_index = 0

RESULT_DIR = Path("results")
RESULT_DIR.mkdir(exist_ok=True)

PROJECTS = {}
PROJECT_COUNTER = 0
PROJECT_LOCK = threading.Lock()


# =======================
# FLASK APP
# =======================
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')


# =======================
# JINJA2 FILTERS
# =======================
@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    """Format datetime for Jinja2 templates"""
    if value is None:
        return '-'

    # If already string, return as is (might need slicing)
    if isinstance(value, str):
        return value

    # If datetime object, format it
    if isinstance(value, datetime):
        return value.strftime(format)

    return str(value)


@app.template_filter('format_date')
def format_date(value):
    """Format date only"""
    if value is None:
        return '-'

    if isinstance(value, str):
        return value[:10] if len(value) >= 10 else value

    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')

    return str(value)


@app.template_filter('format_time')
def format_time(value):
    """Format datetime to show date and time"""
    if value is None:
        return '-'

    if isinstance(value, str):
        return value[:16] if len(value) >= 16 else value

    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')

    return str(value)


# =======================
# AUTH DECORATORS
# =======================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = session.get('session_token')
        if not session_token:
            return redirect(url_for('login'))

        user_data = db.get_session(session_token)
        if not user_data:
            session.clear()
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = session.get('session_token')
        if not session_token:
            return redirect(url_for('login'))

        user_data = db.get_session(session_token)
        if not user_data or user_data.get('role') != 'admin':
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get current logged in user"""
    session_token = session.get('session_token')
    if session_token:
        return db.get_session(session_token)
    return None


# =======================
# CREDIT CHECKING FUNCTIONS
# =======================
API_LOCK = threading.Lock()


def quick_check_credits(api_key: str) -> int:
    """Trả về số credits, 0 nếu có lỗi"""
    try:
        response = requests.get("https://google.serper.dev/account",
                                headers={
                                    "X-API-KEY": api_key,
                                    "Content-Type": "application/json"
                                },
                                timeout=10)
        return response.json().get('balance', 0) if response.status_code == 200 else 0
    except Exception as e:
        print(f"❌ Error checking credits: {e}")
        return 0


def update_all_api_credits():
    """Update real credits for all API keys"""
    print("🔍 Checking real credits for all API keys...")
    global API_KEYS

    with API_LOCK:
        for i, api_info in enumerate(API_KEYS):
            real_credits = quick_check_credits(api_info["key"])
            old_credits = api_info["remaining"]

            api_info["remaining"] = real_credits
            api_info["last_credit_check"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if real_credits > WARNING_THRESHOLD:
                api_info["status"] = "active"
            elif real_credits > 0:
                api_info["status"] = "low_credits"
            else:
                api_info["status"] = "exhausted"

            # Update in database
            db.update_api_key_credits(
                api_info["id"],
                real_credits,
                api_info["total_used"],
                api_info["status"]
            )

            print(f"🔑 API Key {i+1}: {old_credits} -> {real_credits} credits ({api_info['status']})")
            time.sleep(0.5)


def update_single_api_credit(api_index: int):
    """Update credits for a single API key"""
    global API_KEYS

    if 0 <= api_index < len(API_KEYS):
        with API_LOCK:
            api_info = API_KEYS[api_index]
            real_credits = quick_check_credits(api_info["key"])
            api_info["remaining"] = real_credits
            api_info["last_credit_check"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if real_credits > WARNING_THRESHOLD:
                api_info["status"] = "active"
            elif real_credits > 0:
                api_info["status"] = "low_credits"
            else:
                api_info["status"] = "exhausted"

            # Update in database
            db.update_api_key_credits(
                api_info["id"],
                real_credits,
                api_info["total_used"],
                api_info["status"]
            )


def get_api_key():
    """Get current API key with smart rotation"""
    global current_api_index, API_KEYS

    with API_LOCK:
        if not API_KEYS:
            return None

        start_index = current_api_index
        attempts = 0

        while attempts < len(API_KEYS):
            if current_api_index >= len(API_KEYS):
                current_api_index = 0

            api_info = API_KEYS[current_api_index]

            last_check = api_info.get("last_credit_check")
            should_update = False

            if last_check is None:
                should_update = True
            elif isinstance(last_check, str):
                try:
                    last_check_dt = datetime.strptime(last_check, '%Y-%m-%d %H:%M:%S')
                    should_update = (datetime.now() - last_check_dt).seconds > 300
                except:
                    should_update = True

            if should_update:
                print(f"🔄 Updating credits for API key {current_api_index + 1}")
                update_single_api_credit(current_api_index)

            if api_info["remaining"] > WARNING_THRESHOLD and api_info["status"] in ["active", "low_credits"]:
                return api_info["key"]

            current_api_index += 1
            attempts += 1

        current_api_index = start_index
        print(f"⚠️ All API keys exhausted or rate limited!")
        return None


def decrease_quota():
    """Decrease quota for current key"""
    global current_api_index, API_KEYS

    with API_LOCK:
        if 0 <= current_api_index < len(API_KEYS):
            if API_KEYS[current_api_index]["remaining"] > 0:
                API_KEYS[current_api_index]["remaining"] -= 1
            API_KEYS[current_api_index]["total_used"] += 1

            if API_KEYS[current_api_index]["remaining"] <= WARNING_THRESHOLD:
                print(f"🔄 API Key {current_api_index + 1} low quota, switching...")
                current_api_index += 1


# =======================
# INDEX CHECKING (same as before)
# =======================
BATCH_SIZE = 30

def check_index_optimized(url: str) -> str:
    """Optimized index checking with Serper"""
    base = url.rstrip("/")
    queries = [f"site:{url}"]

    for query in queries:
        retry_count = 0
        max_retries = 2

        while retry_count < max_retries:
            api_key = get_api_key()
            if not api_key:
                return "OUT_OF_QUERIES"

            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
            payload = {"q": query}

            try:
                resp = requests.post(
                    "https://google.serper.dev/search",
                    json=payload,
                    headers=headers,
                    timeout=10
                )

                if resp.status_code == 429:
                    with API_LOCK:
                        if current_api_index < len(API_KEYS):
                            API_KEYS[current_api_index]["remaining"] = 0
                            API_KEYS[current_api_index]["status"] = "rate_limited"
                        current_api_index += 1
                    retry_count += 1
                    time.sleep(1)
                    continue

                if resp.status_code != 200:
                    retry_count += 1
                    time.sleep(0.3 * (retry_count + random.random()))
                    continue

                decrease_quota()

                try:
                    data = resp.json()
                except ValueError:
                    retry_count += 1
                    continue

                organic = data.get("organic", [])
                if isinstance(organic, list):
                    for item in organic:
                        if not isinstance(item, dict):
                            continue

                        link = (item.get("link") or "").rstrip("/")
                        if not link:
                            continue

                        if link == base or link.startswith(base + "/"):
                            return "Indexed"

                break

            except requests.exceptions.Timeout:
                print(f"⏱️ Timeout for {url}")
                retry_count += 1
                time.sleep(0.2)
                continue
            except requests.RequestException as e:
                print(f"🌐 Network error for {url}: {e}")
                retry_count += 1
                time.sleep(0.5 * (retry_count + random.random()))
                continue
            except Exception as e:
                print(f"❌ Unexpected error for {url}: {e}")
                return "Error"

    return "No"


def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-. ]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:120] if len(name) > 120 else name


def process_project_background(project_id: int, project_name: str, urls: list[str], user_id: int):
    """Process project in background"""
    print(f"🚀 Starting project {project_id}: {project_name} ({len(urls)} URLs)")

    # Check user credits
    user = db.get_user_by_id(user_id)
    if not user or user['credits'] < len(urls):
        with PROJECT_LOCK:
            PROJECTS[project_id]["status"] = "error"
            PROJECTS[project_id]["error_message"] = "Insufficient credits"
        return

    # Deduct credits
    if not db.deduct_user_credits(user_id, len(urls)):
        with PROJECT_LOCK:
            PROJECTS[project_id]["status"] = "error"
            PROJECTS[project_id]["error_message"] = "Failed to deduct credits"
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["URL", "Index Status"])

    total_urls = len(urls)
    completed = 0
    indexed_count = 0
    error_count = 0
    final_results = {}

    with PROJECT_LOCK:
        PROJECTS[project_id]["total_urls"] = total_urls
        PROJECTS[project_id]["progress"] = f"0/{total_urls}"

    # Process URLs (same logic as before)
    error_urls = []

    for i in range(0, total_urls, BATCH_SIZE):
        batch_urls = urls[i:i + BATCH_SIZE]
        results = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(check_index_optimized, url): url
                for url in batch_urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    status = future.result(timeout=15)
                    if status == "Indexed":
                        indexed_count += 1
                    elif status.startswith("Error") or status in ["OUT_OF_QUERIES", "TIMEOUT"]:
                        error_urls.append(url)
                        error_count += 1
                except Exception as e:
                    status = f"Error: {str(e)[:30]}"
                    error_urls.append(url)
                    error_count += 1

                results[url] = status
                final_results[url] = {"status": status, "retry_count": 0}
                completed += 1

                with PROJECT_LOCK:
                    PROJECTS[project_id]["progress"] = f"{completed}/{total_urls}"
                    PROJECTS[project_id]["indexed_count"] = indexed_count
                    PROJECTS[project_id]["error_count"] = error_count

                time.sleep(random.uniform(0.1, 0.2))

        if get_api_key() is None:
            print("🚫 No more API keys available!")
            break

        time.sleep(0.5)

    # Write results
    for url in urls:
        if url in final_results:
            result = final_results[url]
            status = result["status"]
            ws.append([url, status])
        else:
            ws.append([url, "Error: Not processed"])

    # Save file
    fname = f"{safe_filename(project_name)}.xlsx"
    fpath = RESULT_DIR / fname
    wb.save(fpath)

    # Final update
    with PROJECT_LOCK:
        PROJECTS[project_id]["status"] = "done"
        PROJECTS[project_id]["filename"] = fname
        PROJECTS[project_id]["completed_at"] = datetime.now().isoformat()
        PROJECTS[project_id]["final_stats"] = {
            "total": total_urls,
            "indexed": indexed_count,
            "errors": error_count,
            "index_rate": round((indexed_count / total_urls * 100), 2) if total_urls > 0 else 0,
            "success_rate": round((total_urls - error_count) / total_urls * 100, 1)
        }

    print(f"🎉 Project {project_id} completed!")


# ============= AUTH ROUTES =============

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = db.verify_user(email, password)
        if user:
            session_token = db.create_session(user['id'])
            session['session_token'] = session_token
            session['user_id'] = user['id']
            session['user_role'] = user['role']

            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Email hoặc mật khẩu không đúng!', 'error')

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        # Validation
        if not email or not password:
            flash('Vui lòng nhập đầy đủ thông tin!', 'error')
            return render_template("register.html")

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp!', 'error')
            return render_template("register.html")

        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự!', 'error')
            return render_template("register.html")

        # Check if email exists
        if db.get_user_by_email(email):
            flash('Email đã được sử dụng!', 'error')
            return render_template("register.html")

        # Create user with 10 free credits
        user_id = db.create_user(email, password, role='user', credits=10)

        if user_id:
            flash('Đăng ký thành công! Bạn nhận được 10 credits miễn phí.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Có lỗi xảy ra, vui lòng thử lại!', 'error')

    return render_template("register.html")


@app.route("/logout")
def logout():
    session_token = session.get('session_token')
    if session_token:
        db.delete_session(session_token)

    session.clear()
    return redirect(url_for('login'))


# ============= USER ROUTES =============

@app.route("/")
@login_required
def index():
    user = get_current_user()

    if user and user.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    return render_template("index.html", user=user)


@app.route("/contact", methods=["GET", "POST"])
@login_required
def contact():
    user = get_current_user()

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not subject or not message:
            flash('Vui lòng nhập đầy đủ thông tin!', 'error')
            return render_template("contact.html", user=user)

        message_id = db.create_contact_message(user['id'], subject, message)

        if message_id:
            flash('Tin nhắn đã được gửi! Admin sẽ phản hồi sớm.', 'success')
            return redirect(url_for('my_messages'))
        else:
            flash('Có lỗi xảy ra, vui lòng thử lại!', 'error')

    return render_template("contact.html", user=user)


@app.route("/my-messages")
@login_required
def my_messages():
    user = get_current_user()
    messages = db.get_user_messages(user['id'])

    return render_template("my_messages.html", user=user, messages=messages)


@app.route("/my-credits")
@login_required
def my_credits():
    user = get_current_user()
    transactions = db.get_user_transactions(user['id'])

    return render_template("my_credits.html", user=user, transactions=transactions)


@app.route("/submit", methods=["POST"])
@login_required
def submit():
    user = get_current_user()

    project_name = (request.form.get("projectName") or "").strip()
    url_text = (request.form.get("urlList") or "").strip()

    if not project_name or not url_text:
        flash('Vui lòng nhập đầy đủ thông tin!', 'error')
        return redirect(url_for("index"))

    urls = [u.strip() for u in url_text.splitlines() if u.strip()]
    if not urls:
        flash('Danh sách URL trống!', 'error')
        return redirect(url_for("index"))

    # Check credits
    if user['credits'] < len(urls):
        flash(f'Không đủ credits! Cần {len(urls)} credits, bạn có {user["credits"]} credits.', 'error')
        return redirect(url_for("index"))

    # Create project
    global PROJECT_COUNTER
    with PROJECT_LOCK:
        PROJECT_COUNTER += 1
        pid = PROJECT_COUNTER
        PROJECTS[pid] = {
            "name": project_name,
            "status": "running",
            "filename": None,
            "progress": "0/0",
            "total_urls": len(urls),
            "indexed_count": 0,
            "error_count": 0,
            "retry_progress": "0/0",
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "user_id": user['id']
        }

    # Start processing
    t = threading.Thread(
        target=process_project_background,
        args=(pid, project_name, urls, user['id']),
        daemon=True
    )
    t.start()

    flash(f'Đã bắt đầu kiểm tra {len(urls)} URLs! Chi phí: {len(urls)} credits.', 'success')
    return redirect(url_for("index"))


@app.route("/projects", methods=["GET"])
@login_required
def projects_list():
    user = get_current_user()

    with PROJECT_LOCK:
        if user['role'] == 'admin':
            # Admin sees all projects
            data = [{
                "id": pid,
                "name": info["name"],
                "status": info["status"],
                "filename": info["filename"],
                "progress": info.get("progress", "0/0"),
                "indexed_count": info.get("indexed_count", 0),
                "error_count": info.get("error_count", 0),
                "total_urls": info.get("total_urls", 0),
                "retry_progress": info.get("retry_progress", "0/0"),
                "final_stats": info.get("final_stats", {}),
                "created_at": info["created_at"],
            } for pid, info in sorted(PROJECTS.items(), key=lambda kv: kv[0], reverse=True)]
        else:
            # User sees only their projects
            data = [{
                "id": pid,
                "name": info["name"],
                "status": info["status"],
                "filename": info["filename"],
                "progress": info.get("progress", "0/0"),
                "indexed_count": info.get("indexed_count", 0),
                "error_count": info.get("error_count", 0),
                "total_urls": info.get("total_urls", 0),
                "retry_progress": info.get("retry_progress", "0/0"),
                "final_stats": info.get("final_stats", {}),
                "created_at": info["created_at"],
            } for pid, info in sorted(PROJECTS.items(), key=lambda kv: kv[0], reverse=True)
            if info.get("user_id") == user['id']]

    return jsonify(data)


@app.route("/api/status", methods=["GET"])
@login_required
def api_status():
    """API keys status"""
    user = get_current_user()

    if user['role'] == 'admin':
        # Admin sees full API status
        with API_LOCK:
            status_data = []
            total_remaining = 0
            active_keys = 0

            for i, api_info in enumerate(API_KEYS):
                remaining = api_info["remaining"]
                total_remaining += remaining

                if api_info["status"] in ["active", "low_credits"] and remaining > 0:
                    active_keys += 1

                status_data.append({
                    "index": i + 1,
                    "name": api_info.get("name", f"Key {i+1}"),
                    "remaining": remaining,
                    "total_used": api_info["total_used"],
                    "status": api_info["status"],
                    "is_current": i == current_api_index,
                    "last_check": api_info.get("last_credit_check", "Never")
                })

        return jsonify({
            "current_api_index": current_api_index + 1,
            "warning_threshold": WARNING_THRESHOLD,
            "apis": status_data,
            "total_remaining": total_remaining,
            "active_keys": active_keys,
            "total_projects": len(PROJECTS),
            "is_admin": True
        })
    else:
        # User only sees their credits
        return jsonify({
            "user_credits": user['credits'],
            "is_admin": False
        })


@app.route("/api/refresh-credits", methods=["POST"])
@admin_required
def refresh_credits():
    """Manually refresh all API credits (admin only)"""
    try:
        update_all_api_credits()

        # Reload API keys from database
        global API_KEYS
        API_KEYS = load_api_keys_from_db()

        return jsonify({
            "status": "success",
            "message": "Credits updated successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/download/<int:pid>", methods=["GET"])
@login_required
def download(pid: int):
    user = get_current_user()

    with PROJECT_LOCK:
        info = PROJECTS.get(pid)
        if not info or info.get("status") != "done" or not info.get("filename"):
            abort(404)

        # Check permission
        if user['role'] != 'admin' and info.get("user_id") != user['id']:
            abort(403)

        fname = info["filename"]

    return send_from_directory(
        directory=str(RESULT_DIR),
        path=fname,
        as_attachment=True,
        download_name=fname
    )


# ============= ADMIN ROUTES =============

@app.route("/admin")
@admin_required
def admin_dashboard():
    user = get_current_user()
    users = db.get_all_users()
    messages = db.get_contact_messages(status='pending')

    return render_template("admin_dashboard.html", user=user, users=users, pending_messages=len(messages))


@app.route("/admin/users")
@admin_required
def admin_users():
    user = get_current_user()
    users = db.get_all_users()

    return render_template("admin_users.html", user=user, users=users)


@app.route("/admin/user/<int:user_id>/credits", methods=["POST"])
@admin_required
def admin_adjust_credits(user_id):
    admin = get_current_user()

    amount = request.form.get("amount", type=int)
    description = request.form.get("description", "").strip()

    if amount is None:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    if db.update_user_credits(user_id, amount, admin['id'], description):
        return jsonify({"status": "success", "message": "Credits updated"})
    else:
        return jsonify({"status": "error", "message": "Failed to update credits"}), 500


@app.route("/admin/api-keys")
@admin_required
def admin_api_keys():
    user = get_current_user()
    api_keys = db.get_all_api_keys()

    return render_template("admin_api_keys.html", user=user, api_keys=api_keys)


@app.route("/admin/api-keys/add", methods=["POST"])
@admin_required
def admin_add_api_key():
    key_value = request.form.get("key_value", "").strip()
    name = request.form.get("name", "").strip()

    if not key_value:
        flash('Vui lòng nhập API key!', 'error')
        return redirect(url_for('admin_api_keys'))

    key_id = db.add_api_key(key_value, name)

    if key_id:
        # Reload API keys
        global API_KEYS
        API_KEYS = load_api_keys_from_db()

        flash('API key đã được thêm!', 'success')
    else:
        flash('Có lỗi xảy ra!', 'error')

    return redirect(url_for('admin_api_keys'))


@app.route("/admin/api-keys/<int:key_id>/delete", methods=["POST"])
@admin_required
def admin_delete_api_key(key_id):
    if db.delete_api_key(key_id):
        # Reload API keys
        global API_KEYS
        API_KEYS = load_api_keys_from_db()

        return jsonify({"status": "success", "message": "API key deleted"})
    else:
        return jsonify({"status": "error", "message": "Failed to delete"}), 500


@app.route("/admin/messages")
@admin_required
def admin_messages():
    user = get_current_user()
    messages = db.get_contact_messages()

    return render_template("admin_messages.html", user=user, messages=messages)


@app.route("/admin/messages/<int:message_id>/reply", methods=["POST"])
@admin_required
def admin_reply_message(message_id):
    admin_reply = request.form.get("admin_reply", "").strip()

    if not admin_reply:
        return jsonify({"status": "error", "message": "Reply cannot be empty"}), 400

    if db.reply_contact_message(message_id, admin_reply):
        return jsonify({"status": "success", "message": "Reply sent"})
    else:
        return jsonify({"status": "error", "message": "Failed to send reply"}), 500


@app.route("/health")
def health():
    with API_LOCK:
        total_quota = sum(api["remaining"] for api in API_KEYS)
        active_keys = sum(1 for api in API_KEYS if api["status"] in ["active", "low_credits"])

    return jsonify({
        "status": "ok",
        "api_keys": f"{active_keys}/{len(API_KEYS)} active",
        "total_quota": total_quota,
        "active_projects": len([p for p in PROJECTS.values() if p["status"] == "running"])
    })


if __name__ == "__main__":
    print("🔧 Initializing database...")

    # Check if we need to migrate existing API keys from env
    if not db.get_all_api_keys():
        print("📥 Migrating API keys from environment variables...")
        idx = 1
        while True:
            key_name = f"API_KEY_{idx}"
            api_key = os.getenv(key_name)
            if not api_key:
                break
            db.add_api_key(api_key, f"Key {idx}")
            print(f"✅ Migrated {key_name}")
            idx += 1

    # Load API keys
    API_KEYS = load_api_keys_from_db()

    if not API_KEYS:
        print("⚠️  WARNING: No API keys found!")
        print("Please add API keys through admin dashboard")
    else:
        print(f"✅ Loaded {len(API_KEYS)} API keys from database")

        # Check real credits at startup
        print("🔍 Checking real credits for all API keys at startup...")
        update_all_api_credits()

        total_quota = sum(api["remaining"] for api in API_KEYS)
        active_keys = sum(1 for api in API_KEYS if api["status"] in ["active", "low_credits"])

        print(f"📊 Real total quota: {total_quota} searches")
        print(f"🔑 Active keys: {active_keys}/{len(API_KEYS)}")

    print("🚀 Starting Google Index Checker with User System...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
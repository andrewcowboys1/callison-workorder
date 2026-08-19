#!/usr/bin/env python3
"""
Callison Electric Heating & Cooling - Work Order App
Simple, mobile-friendly work order management for technicians and office staff.
"""

import os
import sqlite3
import uuid
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "callison-electric-hvac-2026-secret-change-me")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = os.path.join(os.path.dirname(__file__), "workorders.db")

# ---------- Database helpers ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'tech')),
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wo_number TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            created_by INTEGER,
            status TEXT NOT NULL DEFAULT 'New',
            priority TEXT NOT NULL DEFAULT 'Normal',
            job_type TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT,
            customer_email TEXT,
            service_address TEXT NOT NULL,
            city TEXT DEFAULT 'Staunton',
            description TEXT,
            equipment_info TEXT,
            assigned_to INTEGER,
            scheduled_date TEXT,
            arrival_time TEXT,
            departure_time TEXT,
            work_performed TEXT,
            parts_used TEXT,
            notes TEXT,
            customer_signature TEXT,
            completed_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_order_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            caption TEXT,
            uploaded_at TEXT NOT NULL,
            uploaded_by INTEGER,
            FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        );
    """)
    db.commit()

    # Seed default users if empty
    cur = db.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        users = [
            ("admin", generate_password_hash("callison2026"), "Andrew Callison", "admin"),
            ("melissa", generate_password_hash("office123"), "Melissa Callison", "admin"),
            ("jimmy", generate_password_hash("tech123"), "Jimmy Callison", "tech"),
            ("tech1", generate_password_hash("tech123"), "Technician 1", "tech"),
            ("tech2", generate_password_hash("tech123"), "Technician 2", "tech"),
        ]
        db.executemany(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            users
        )
        db.commit()
        print("Seeded default users.")

# ---------- Auth helpers ----------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_wo_number():
    today = date.today().strftime("%Y%m%d")
    db = get_db()
    cur = db.execute(
        "SELECT COUNT(*) FROM work_orders WHERE wo_number LIKE ?",
        (f"WO-{today}-%",)
    )
    count = cur.fetchone()[0] + 1
    return f"WO-{today}-{count:03d}"

# ---------- Routes ----------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    role = session["role"]

    if role == "admin":
        # Admin sees overview stats + recent / open orders
        stats = {
            "open": db.execute(
                "SELECT COUNT(*) FROM work_orders WHERE status NOT IN ('Completed', 'Invoiced', 'Cancelled')"
            ).fetchone()[0],
            "today": db.execute(
                "SELECT COUNT(*) FROM work_orders WHERE date(created_at) = date('now')"
            ).fetchone()[0],
            "assigned": db.execute(
                "SELECT COUNT(*) FROM work_orders WHERE status = 'Assigned'"
            ).fetchone()[0],
            "in_progress": db.execute(
                "SELECT COUNT(*) FROM work_orders WHERE status IN ('En Route', 'On Site')"
            ).fetchone()[0],
            "completed_today": db.execute(
                "SELECT COUNT(*) FROM work_orders WHERE status = 'Completed' AND date(completed_at) = date('now')"
            ).fetchone()[0],
        }
        recent = db.execute("""
            SELECT wo.*, u.full_name as tech_name
            FROM work_orders wo
            LEFT JOIN users u ON wo.assigned_to = u.id
            ORDER BY wo.created_at DESC
            LIMIT 15
        """).fetchall()
        techs = db.execute(
            "SELECT id, full_name FROM users WHERE role = 'tech' AND active = 1 ORDER BY full_name"
        ).fetchall()
        return render_template(
            "dashboard.html", stats=stats, recent=recent, techs=techs, user=user
        )
    else:
        # Technician sees only their assigned jobs
        my_jobs = db.execute("""
            SELECT wo.*, u.full_name as tech_name
            FROM work_orders wo
            LEFT JOIN users u ON wo.assigned_to = u.id
            WHERE wo.assigned_to = ?
              AND wo.status NOT IN ('Completed', 'Invoiced', 'Cancelled')
            ORDER BY
                CASE wo.priority
                    WHEN 'Emergency' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Normal' THEN 3
                    ELSE 4
                END,
                wo.scheduled_date ASC,
                wo.created_at ASC
        """, (user["id"],)).fetchall()
        completed = db.execute("""
            SELECT wo.*, u.full_name as tech_name
            FROM work_orders wo
            LEFT JOIN users u ON wo.assigned_to = u.id
            WHERE wo.assigned_to = ? AND wo.status IN ('Completed', 'Invoiced')
            ORDER BY wo.completed_at DESC
            LIMIT 10
        """, (user["id"],)).fetchall()
        return render_template(
            "dashboard_tech.html", my_jobs=my_jobs, completed=completed, user=user
        )

@app.route("/workorders")
@login_required
def list_workorders():
    db = get_db()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    tech_id = request.args.get("tech", "")
    search = request.args.get("q", "").strip()

    query = """
        SELECT wo.*, u.full_name as tech_name
        FROM work_orders wo
        LEFT JOIN users u ON wo.assigned_to = u.id
        WHERE 1=1
    """
    params = []

    if session["role"] == "tech":
        query += " AND wo.assigned_to = ?"
        params.append(session["user_id"])

    if status:
        query += " AND wo.status = ?"
        params.append(status)
    if priority:
        query += " AND wo.priority = ?"
        params.append(priority)
    if tech_id and session["role"] == "admin":
        query += " AND wo.assigned_to = ?"
        params.append(tech_id)
    if search:
        query += """ AND (
            wo.wo_number LIKE ? OR wo.customer_name LIKE ? OR
            wo.service_address LIKE ? OR wo.description LIKE ?
        )"""
        like = f"%{search}%"
        params.extend([like, like, like, like])

    query += " ORDER BY wo.created_at DESC LIMIT 100"
    rows = db.execute(query, params).fetchall()

    techs = []
    if session["role"] == "admin":
        techs = db.execute(
            "SELECT id, full_name FROM users WHERE role = 'tech' AND active = 1 ORDER BY full_name"
        ).fetchall()

    return render_template(
        "list.html",
        work_orders=rows,
        techs=techs,
        filters={"status": status, "priority": priority, "tech": tech_id, "q": search},
    )

@app.route("/workorders/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_workorder():
    db = get_db()
    techs = db.execute(
        "SELECT id, full_name FROM users WHERE role = 'tech' AND active = 1 ORDER BY full_name"
    ).fetchall()

    if request.method == "POST":
        wo_number = generate_wo_number()
        now = datetime.now().isoformat(timespec="seconds")
        data = {
            "wo_number": wo_number,
            "created_at": now,
            "created_by": session["user_id"],
            "status": request.form.get("status", "New"),
            "priority": request.form.get("priority", "Normal"),
            "job_type": request.form.get("job_type", "Other"),
            "customer_name": request.form.get("customer_name", "").strip(),
            "customer_phone": request.form.get("customer_phone", "").strip(),
            "customer_email": request.form.get("customer_email", "").strip(),
            "service_address": request.form.get("service_address", "").strip(),
            "city": request.form.get("city", "Staunton").strip(),
            "description": request.form.get("description", "").strip(),
            "equipment_info": request.form.get("equipment_info", "").strip(),
            "assigned_to": request.form.get("assigned_to") or None,
            "scheduled_date": request.form.get("scheduled_date") or None,
            "notes": request.form.get("notes", "").strip(),
        }

        if not data["customer_name"] or not data["service_address"]:
            flash("Customer name and service address are required.", "danger")
            return render_template("create_wo.html", techs=techs, form=request.form)

        if data["assigned_to"]:
            data["status"] = "Assigned"

        db.execute("""
            INSERT INTO work_orders (
                wo_number, created_at, created_by, status, priority, job_type,
                customer_name, customer_phone, customer_email, service_address, city,
                description, equipment_info, assigned_to, scheduled_date, notes
            ) VALUES (
                :wo_number, :created_at, :created_by, :status, :priority, :job_type,
                :customer_name, :customer_phone, :customer_email, :service_address, :city,
                :description, :equipment_info, :assigned_to, :scheduled_date, :notes
            )
        """, data)
        db.commit()
        flash(f"Work order {wo_number} created successfully.", "success")
        return redirect(url_for("list_workorders"))

    return render_template("create_wo.html", techs=techs, form={})

@app.route("/workorders/<int:wo_id>")
@login_required
def view_workorder(wo_id):
    db = get_db()
    wo = db.execute("""
        SELECT wo.*, u.full_name as tech_name, c.full_name as created_by_name
        FROM work_orders wo
        LEFT JOIN users u ON wo.assigned_to = u.id
        LEFT JOIN users c ON wo.created_by = c.id
        WHERE wo.id = ?
    """, (wo_id,)).fetchone()

    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("dashboard"))

    # Techs can only see their own jobs
    if session["role"] == "tech" and wo["assigned_to"] != session["user_id"]:
        flash("You do not have access to this work order.", "danger")
        return redirect(url_for("dashboard"))

    photos = db.execute(
        "SELECT * FROM photos WHERE work_order_id = ? ORDER BY uploaded_at",
        (wo_id,)
    ).fetchall()

    techs = []
    if session["role"] == "admin":
        techs = db.execute(
            "SELECT id, full_name FROM users WHERE role = 'tech' AND active = 1 ORDER BY full_name"
        ).fetchall()

    return render_template(
        "view_wo.html", wo=wo, photos=photos, techs=techs
    )

@app.route("/workorders/<int:wo_id>/update", methods=["POST"])
@login_required
def update_workorder(wo_id):
    db = get_db()
    wo = db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("dashboard"))

    if session["role"] == "tech" and wo["assigned_to"] != session["user_id"]:
        flash("You do not have permission to update this work order.", "danger")
        return redirect(url_for("dashboard"))

    # Collect updatable fields
    updates = {}
    fields = [
        "status", "priority", "job_type", "customer_name", "customer_phone",
        "customer_email", "service_address", "city", "description",
        "equipment_info", "scheduled_date", "arrival_time", "departure_time",
        "work_performed", "parts_used", "notes"
    ]

    for f in fields:
        val = request.form.get(f)
        if val is not None:
            updates[f] = val.strip() if isinstance(val, str) else val

    # Assignment only for admin
    if session["role"] == "admin":
        assigned = request.form.get("assigned_to")
        updates["assigned_to"] = int(assigned) if assigned else None
        if updates.get("assigned_to") and updates.get("status") == "New":
            updates["status"] = "Assigned"

    # Auto-set completed_at
    if updates.get("status") == "Completed" and not wo["completed_at"]:
        updates["completed_at"] = datetime.now().isoformat(timespec="seconds")

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [wo_id]
        db.execute(f"UPDATE work_orders SET {set_clause} WHERE id = ?", values)
        db.commit()
        flash("Work order updated.", "success")

    return redirect(url_for("view_workorder", wo_id=wo_id))

@app.route("/workorders/<int:wo_id>/photo", methods=["POST"])
@login_required
def upload_photo(wo_id):
    db = get_db()
    wo = db.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("dashboard"))

    if session["role"] == "tech" and wo["assigned_to"] != session["user_id"]:
        flash("Permission denied.", "danger")
        return redirect(url_for("dashboard"))

    if "photo" not in request.files:
        flash("No file selected.", "warning")
        return redirect(url_for("view_workorder", wo_id=wo_id))

    file = request.files["photo"]
    if file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("view_workorder", wo_id=wo_id))

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"wo{wo_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        caption = request.form.get("caption", "").strip()
        db.execute(
            "INSERT INTO photos (work_order_id, filename, caption, uploaded_at, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            (wo_id, filename, caption, datetime.now().isoformat(timespec="seconds"), session["user_id"])
        )
        db.commit()
        flash("Photo uploaded.", "success")
    else:
        flash("Invalid file type. Allowed: png, jpg, jpeg, gif, webp.", "danger")

    return redirect(url_for("view_workorder", wo_id=wo_id))

@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/workorders/<int:wo_id>/print")
@login_required
def print_workorder(wo_id):
    db = get_db()
    wo = db.execute("""
        SELECT wo.*, u.full_name as tech_name
        FROM work_orders wo
        LEFT JOIN users u ON wo.assigned_to = u.id
        WHERE wo.id = ?
    """, (wo_id,)).fetchone()
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("dashboard"))
    if session["role"] == "tech" and wo["assigned_to"] != session["user_id"]:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    photos = db.execute(
        "SELECT * FROM photos WHERE work_order_id = ?", (wo_id,)
    ).fetchall()
    return render_template("print_wo.html", wo=wo, photos=photos)

# ---------- Startup ----------

@app.cli.command("init-db")
def init_db_command():
    """Initialize the database."""
    init_db()
    print("Database initialized.")

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

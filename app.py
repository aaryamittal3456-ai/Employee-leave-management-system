from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from functools import wraps
import os

app = Flask(__name__)   # Flask will automatically look for /templates and /static
app.secret_key = 'leaveflow-secret-key-2024'

# ─── DB CONFIG ────────────────────────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'ROOT12345',
    'database': 'leave_management'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# ─── INIT DATABASE ────────────────────────────────────────────────────────────
def init_db():
    conn = mysql.connector.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS leave_management")
    conn.database = 'leave_management'

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            username         VARCHAR(100) NOT NULL UNIQUE,
            email            VARCHAR(150) NOT NULL UNIQUE,
            password         VARCHAR(255) NOT NULL,
            role             ENUM('admin','employee') NOT NULL DEFAULT 'employee',
            total_leaves     INT NOT NULL DEFAULT 20,
            remaining_leaves INT NOT NULL DEFAULT 20,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id                      INT AUTO_INCREMENT PRIMARY KEY,
            employee_id             INT NOT NULL,
            start_date              DATE NOT NULL,
            end_date                DATE NOT NULL,
            number_of_days          INT NOT NULL,
            reason                  TEXT NOT NULL,
            status                  ENUM('Pending','Approved','Denied') DEFAULT 'Pending',
            replacement_employee_id INT DEFAULT NULL,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # ── Migrate: add missing columns to existing tables ──────────────────────
    # This handles cases where the table already exists without newer columns.
    migrations = [
        ("leave_requests", "replacement_employee_id", "ALTER TABLE leave_requests ADD COLUMN replacement_employee_id INT DEFAULT NULL"),
        ("leave_requests", "updated_at",              "ALTER TABLE leave_requests ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ("users",          "total_leaves",            "ALTER TABLE users ADD COLUMN total_leaves INT NOT NULL DEFAULT 20"),
        ("users",          "remaining_leaves",        "ALTER TABLE users ADD COLUMN remaining_leaves INT NOT NULL DEFAULT 20"),
    ]
    for table, column, sql in migrations:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA='leave_management' AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """, (table, column))
        exists = cur.fetchone()[0]
        if not exists:
            cur.execute(sql)
            print(f"✅ Migration applied: added {table}.{column}")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database ready.")

# ─── DECORATORS ───────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('employee_dashboard'))
        return f(*args, **kwargs)
    return decorated

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session['role'] == 'admin' else url_for('employee_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        role     = request.form['role']

        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s AND role=%s", (email, role))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user is None:
            flash('No account found with that email and role. Please sign up first.', 'error')
        elif not check_password_hash(user['password'], password):
            flash('Incorrect password. Please try again.', 'error')
        else:
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['role']     = user['role']
            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('admin_dashboard') if role == 'admin' else url_for('employee_dashboard'))

    return render_template('auth.html', page='login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        confirm  = request.form['confirm_password']
        role     = request.form['role']

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth.html', page='signup')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth.html', page='signup')

        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                (username, email, hashed, role)
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username or email already exists.', 'error')

    return render_template('auth.html', page='signup')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# ─── EMPLOYEE ROUTES ──────────────────────────────────────────────────────────
@app.route('/employee/dashboard')
@login_required
def employee_dashboard():
    conn = get_db()
    cur  = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cur.fetchone()

    cur.execute("""
        SELECT lr.*, u.username AS replacement_name
        FROM leave_requests lr
        LEFT JOIN users u ON lr.replacement_employee_id = u.id
        WHERE lr.employee_id = %s
        ORDER BY lr.created_at DESC
    """, (session['user_id'],))
    leaves = cur.fetchall()

    cur.close()
    conn.close()

    today        = date.today()
    leaves_taken = sum(l['number_of_days'] for l in leaves if l['status'] == 'Approved')
    on_leave     = any(
        l['status'] == 'Approved' and l['start_date'] <= today <= l['end_date']
        for l in leaves
    )

    return render_template('employee_dashboard.html',
        user=user, leaves=leaves,
        leaves_taken=leaves_taken, on_leave=on_leave
    )

@app.route('/employee/apply', methods=['POST'])
@login_required
def apply_leave():
    start_date = request.form['start_date']
    end_date   = request.form['end_date']
    reason     = request.form['reason'].strip()

    try:
        sd   = datetime.strptime(start_date, '%Y-%m-%d').date()
        ed   = datetime.strptime(end_date,   '%Y-%m-%d').date()
        days = (ed - sd).days + 1

        if days <= 0:
            flash('End date must be after start date.', 'error')
            return redirect(url_for('employee_dashboard'))

        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT remaining_leaves FROM users WHERE id=%s", (session['user_id'],))
        user = cur.fetchone()

        if user['remaining_leaves'] < days:
            flash(f'Not enough leave balance. You have {user["remaining_leaves"]} day(s) remaining.', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('employee_dashboard'))

        cur.execute("""
            INSERT INTO leave_requests (employee_id, start_date, end_date, number_of_days, reason)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], sd, ed, days, reason))
        conn.commit()
        cur.close()
        conn.close()
        flash(f'Leave request for {days} day(s) submitted! Awaiting admin approval.', 'success')

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('employee_dashboard'))

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    cur  = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT lr.*, u.username AS employee_name, u.email AS employee_email,
               r.username AS replacement_name
        FROM leave_requests lr
        JOIN  users u ON lr.employee_id = u.id
        LEFT JOIN users r ON lr.replacement_employee_id = r.id
        ORDER BY lr.created_at DESC
    """)
    requests = cur.fetchall()

    cur.execute("SELECT * FROM users WHERE role='employee' ORDER BY username")
    employees = cur.fetchall()

    today = date.today()
    for emp in employees:
        cur.execute("""
            SELECT id FROM leave_requests
            WHERE employee_id=%s AND status='Approved'
              AND start_date <= %s AND end_date >= %s
            LIMIT 1
        """, (emp['id'], today, today))
        emp['on_leave'] = cur.fetchone() is not None

    cur.close()
    conn.close()

    pending_count  = sum(1 for r in requests if r['status'] == 'Pending')
    approved_count = sum(1 for r in requests if r['status'] == 'Approved')
    denied_count   = sum(1 for r in requests if r['status'] == 'Denied')
    on_leave_count = sum(1 for e in employees if e['on_leave'])

    return render_template('admin_dashboard.html',
        requests=requests, employees=employees,
        pending_count=pending_count, approved_count=approved_count,
        denied_count=denied_count, on_leave_count=on_leave_count
    )

@app.route('/admin/action/<int:leave_id>/<action>', methods=['POST'])
@login_required
@admin_required
def leave_action(leave_id, action):
    if action not in ('approve', 'deny'):
        flash('Invalid action.', 'error')
        return redirect(url_for('admin_dashboard'))

    replacement_id = request.form.get('replacement_id') or None
    new_status     = 'Approved' if action == 'approve' else 'Denied'

    conn = get_db()
    cur  = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM leave_requests WHERE id=%s", (leave_id,))
    leave = cur.fetchone()

    if not leave:
        flash('Leave request not found.', 'error')
    elif leave['status'] != 'Pending':
        flash('This request has already been processed.', 'error')
    else:
        cur.execute(
            "UPDATE leave_requests SET status=%s, replacement_employee_id=%s WHERE id=%s",
            (new_status, replacement_id, leave_id)
        )
        if action == 'approve':
            cur.execute("""
                UPDATE users SET remaining_leaves = remaining_leaves - %s
                WHERE id=%s AND remaining_leaves >= %s
            """, (leave['number_of_days'], leave['employee_id'], leave['number_of_days']))
        conn.commit()
        flash(f'Leave request {new_status.lower()} successfully.', 'success')

    cur.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/employee/<int:emp_id>')
@login_required
@admin_required
def employee_detail(emp_id):
    conn = get_db()
    cur  = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM users WHERE id=%s AND role='employee'", (emp_id,))
    emp = cur.fetchone()

    if not emp:
        flash('Employee not found.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))

    cur.execute("SELECT * FROM leave_requests WHERE employee_id=%s ORDER BY created_at DESC", (emp_id,))
    leaves = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('employee_detail.html', emp=emp, leaves=leaves)

# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True)

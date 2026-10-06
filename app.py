# ==============================================================================
# SECTION 1: LIBRARIES IMPORT KARNA
# ==============================================================================
import os                       # System level file path operations ke liye
import sqlite3                  # SQLite Database ke sath kaam karne ke liye
from functools import wraps     # Custom decorators (e.g., login_required) banane ke liye
from datetime import datetime   # Date and Time formatting ke liye

from flask import (             # Flask Web Framework ke core functions
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash # Passwords Security/Hashing ke liye


# ==============================================================================
# SECTION 2: APPLICATION CONFIGURATION & DATABASE SETTINGS
# ==============================================================================
app = Flask(__name__)           # Main Flask Application Object shuru ho raha hai
app.secret_key = 'super_secret_housing_scheme_key_2026' # Session encryption key

DB_NAME = 'database.db'        # SQLite database file ka naam

# Available Housing Schemes ki global list
AVAILABLE_SCHEMES = [
    "Village Bijar Khan Talpur Housing Scheme",
    "Anwarabad Housing Scheme",
    "Bhitai One Housing Scheme"
]


# ==============================================================================
# SECTION 3: CUSTOM JINJA TEMPLATE FILTERS & HELPERS
# ==============================================================================

# --- START: Filter accounting_format ---
# Maqsad: Numbers ko commas aur 2 decimals ke saath format karna (e.g. 15000 -> 15,000.00)
@app.template_filter('accounting')
def accounting_format(value):
    try:
        if value is None:
            return "0.00"
        val = float(value)
        return "{:,.2f}".format(val)
    except (ValueError, TypeError):
        return "0.00"
# --- END: Filter accounting_format ---


# --- START: Filter custom_date_format ---
# Maqsad: Dates ko 'YYYY-MM-DD' se 'DD-Mon-YYYY' (e.g. 06-Oct-2026) mein convert karna
@app.template_filter('custom_date')
def custom_date_format(value):
    if not value:
        return ""
    try:
        date_obj = datetime.strptime(str(value).split(' ')[0], '%Y-%m-%d')
        return date_obj.strftime('%d-%b-%Y')
    except (ValueError, TypeError):
        return str(value)
# --- END: Filter custom_date_format ---


# --- START: Helper safe_float ---
# Maqsad: Kisi bhi input ko safe tarike se float/number mein convert karna taakay code crash na ho
def safe_float(val):
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0
# --- END: Helper safe_float ---


# ==============================================================================
# SECTION 4: DATABASE SETUP & INITIALIZATION FUNCTION
# ==============================================================================

# --- START: Function init_db ---
# Maqsad: App start hotay hi zaroori tables (users, plots, payments) aur default accounts banana
def init_db():
    conn = sqlite3.connect(DB_NAME)  # Database se connection قائم hua
    cursor = conn.cursor()            # SQL queries chalane ke liye cursor banaya

    # 1. Users Table (System Login Users ke liye)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            plain_password TEXT DEFAULT '',
            role TEXT DEFAULT 'officeboy'
        )
    ''')

    # Migration Check: Agar purani database mein 'plain_password' column na ho to add karo
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'plain_password' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN plain_password TEXT DEFAULT ''")

    # 2. Plots Table (Plot Registration aur Owner Details ke liye)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_name TEXT NOT NULL DEFAULT 'Village Bijar Khan Talpur Housing Scheme',
            plot_number TEXT NOT NULL,
            plot_type TEXT NOT NULL,
            plot_size REAL NOT NULL,
            owner_name TEXT NOT NULL,
            nic_no TEXT NOT NULL,
            mobile_no TEXT NOT NULL,
            rate_per_sqft REAL NOT NULL,
            total_cost REAL NOT NULL,
            advance REAL NOT NULL,
            payment_type TEXT DEFAULT 'Cash',
            payment_date TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            remarks TEXT,
            UNIQUE(scheme_name, plot_type, plot_number)
        )
    ''')

    # 3. Payments Table (Installments record karne ke liye)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            receipt_no TEXT,
            remarks TEXT,
            FOREIGN KEY (plot_id) REFERENCES plots (id) ON DELETE CASCADE
        )
    ''')

    # 4. Installments Alias Table (Backward Compatibility ke liye)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS installments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            receipt_no TEXT,
            remarks TEXT,
            FOREIGN KEY (plot_id) REFERENCES plots (id)
        )
    ''')

    # Default Users Setup: Admin Account (agar exist nahi karta)
    cursor.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, plain_password, role) VALUES (?, ?, ?, ?)", 
                       ('admin', generate_password_hash('admin123'), 'admin123', 'admin'))

    # Default Users Setup: Officeboy Account (agar exist nahi karta)
    cursor.execute("SELECT * FROM users WHERE username = ?", ('officeboy',))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, plain_password, role) VALUES (?, ?, ?, ?)", 
                       ('officeboy', generate_password_hash('boy123'), 'boy123', 'officeboy'))

    conn.commit()  # Tamam DB updates save kiye gaye
    conn.close()   # Connection close kar diya gaya
# --- END: Function init_db ---

# Database Function Run karna
init_db()


# ==============================================================================
# SECTION 5: SECURITY GUARDS (DECORATORS)
# ==============================================================================

# --- START: Decorator login_required ---
# Maqsad: Check karta hai ke user login hai ya nahi, agar nahi to login page par bhejta hai
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in first!', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
# --- END: Decorator login_required ---


# --- START: Decorator admin_required ---
# Maqsad: Check karta hai ke login user Admin hai ya nahi, officeboy ko block karta hai
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Access Denied: Admin privileges required!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function
# --- END: Decorator admin_required ---


# ==============================================================================
# SECTION 6: APPLICATION ROUTES & CONTROLLERS
# ==============================================================================

# --- START: Route / (Login Screen) ---
# Maqsad: User login authentication handle karna aur active housing scheme set karna
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user' in session and not request.args.get('force'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        category = request.form.get('plot_category', '').strip().upper()
        scheme_name = request.form.get('scheme_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Verification: Dropdowns select karna lazmi hain
        if not scheme_name or not category:
            flash('Please select both Housing Scheme and Plot Category!', 'danger')
            return render_template('login.html', schemes_list=AVAILABLE_SCHEMES)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        # Password matching verification
        if user and check_password_hash(user[2], password):
            session['user'] = user[1]
            session['role'] = user[3]
            session['active_category'] = category
            session['active_scheme'] = scheme_name
            flash(f'Welcome back, {user[1].upper()}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Username or Password!', 'danger')

    return render_template('login.html', schemes_list=AVAILABLE_SCHEMES)
# --- END: Route / (Login Screen) ---


# --- START: Route /logout ---
# Maqsad: User session clear karke system se bahar nikalna
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))
# --- END: Route /logout ---


# --- START: Route /dashboard ---
# Maqsad: Main Dashboard jahan selected scheme ke sare plots aur financial totals dikhte hain
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # Context apply update handle karna
    if request.method == 'POST':
        scheme = request.form.get('scheme_name')
        category = request.form.get('plot_category')
        if scheme:
            session['active_scheme'] = scheme.strip()
        if category:
            session['active_category'] = category.strip().upper()
        flash('Active Context Updated!', 'info')
        return redirect(url_for('dashboard'))

    active_scheme = session.get('active_scheme', AVAILABLE_SCHEMES[0]).strip()
    active_category = session.get('active_category', 'RESIDENTIAL').strip().upper()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    search_query = request.args.get('search', '').strip()

    # Search filter query
    if search_query:
        cursor.execute("""
            SELECT id, plot_number, owner_name, mobile_no, total_cost, advance 
            FROM plots 
            WHERE LOWER(scheme_name) = LOWER(?) AND UPPER(plot_type) = UPPER(?)
              AND (plot_number LIKE ? OR owner_name LIKE ? OR nic_no LIKE ?)
            ORDER BY id DESC
        """, (active_scheme, active_category, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("""
            SELECT id, plot_number, owner_name, mobile_no, total_cost, advance 
            FROM plots 
            WHERE LOWER(scheme_name) = LOWER(?) AND UPPER(plot_type) = UPPER(?)
            ORDER BY id DESC
        """, (active_scheme, active_category))
        
    raw_plots = cursor.fetchall()
    
    plots_summary = []
    total_scheme_cost = 0.0
    total_scheme_collected = 0.0

    # Calculated totals per plot
    for p in raw_plots:
        plot_id = p[0]
        plot_number = p[1]
        owner_name = p[2]
        mobile_no = p[3]
        total_cost = safe_float(p[4])
        advance = safe_float(p[5])

        cursor.execute("SELECT SUM(amount) FROM payments WHERE plot_id = ?", (plot_id,))
        p_sum = safe_float(cursor.fetchone()[0])
        cursor.execute("SELECT SUM(amount) FROM installments WHERE plot_id = ?", (plot_id,))
        i_sum = safe_float(cursor.fetchone()[0])
        
        installments_sum = max(p_sum, i_sum)
        total_paid = advance + installments_sum
        remaining_balance = total_cost - total_paid

        total_scheme_cost += total_cost
        total_scheme_collected += total_paid

        plots_summary.append({
            'id': plot_id,
            'plot_number': plot_number,
            'owner_name': owner_name,
            'mobile_no': mobile_no,
            'total_cost': total_cost,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance
        })

    conn.close()

    total_scheme_remaining = total_scheme_cost - total_scheme_collected

    return render_template('dashboard.html',
                           schemes_list=AVAILABLE_SCHEMES,
                           active_scheme=active_scheme,
                           active_category=active_category,
                           plots=plots_summary,
                           total_cost=total_scheme_cost,
                           total_collected=total_scheme_collected,
                           total_remaining=total_scheme_remaining,
                           search_query=search_query)
# --- END: Route /dashboard ---


# --- START: Route /register-plot ---
# Maqsad: Active scheme aur category mein naya plot register karna
@app.route('/register-plot', methods=['GET', 'POST'])
@login_required
def register_plot():
    active_scheme = session.get('active_scheme', AVAILABLE_SCHEMES[0]).strip()
    active_category = session.get('active_category', 'RESIDENTIAL').strip().upper()

    if request.method == 'POST':
        plot_number = request.form.get('plot_number', '').strip().upper()
        owner_name = request.form.get('owner_name', '').strip()
        nic_no = request.form.get('nic_no', '').strip()
        mobile_no = request.form.get('mobile_no', '').strip()

        plot_size = safe_float(request.form.get('plot_size', 0))
        rate_per_sqft = safe_float(request.form.get('rate_per_sqft', 0))
        advance = safe_float(request.form.get('advance', 0))
        payment_type = request.form.get('payment_type', 'Cash').strip()
        payment_date = request.form.get('payment_date') or datetime.now().strftime('%Y-%m-%d')
        remarks = request.form.get('remarks', '')

        total_cost = plot_size * rate_per_sqft

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO plots (scheme_name, plot_type, plot_number, owner_name, nic_no, mobile_no, 
                                   plot_size, rate_per_sqft, total_cost, advance, payment_type, payment_date, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (active_scheme, active_category, plot_number, owner_name, nic_no, mobile_no, 
                  plot_size, rate_per_sqft, total_cost, advance, payment_type, payment_date, remarks))
            
            conn.commit()
            flash(f'Plot #{plot_number} ({active_category}) registered successfully!', 'success')
            conn.close()
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            conn.close()
            flash(f'Plot #{plot_number} already exists in {active_scheme} ({active_category})!', 'danger')
            return redirect(url_for('register_plot'))

    return render_template('register_plot.html', active_scheme=active_scheme, active_category=active_category)
# --- END: Route /register-plot ---


# --- START: Route /add-installment ---
# Maqsad: Selected plot ke liye installment / payment enter karna
@app.route('/add-installment', methods=['GET', 'POST'])
@login_required
def add_installment():
    default_category = session.get('active_category', 'RESIDENTIAL').strip().upper()
    entered_plot_number = request.args.get('plot_number', '')

    if request.method == 'POST':
        active_scheme = session.get('active_scheme', AVAILABLE_SCHEMES[0]).strip()
        category = request.form.get('plot_category', default_category).strip().upper()
        plot_number = request.form.get('plot_number', '').strip().upper()
        receipt_no = request.form.get('receipt_no', '').strip()
        payment_date = request.form.get('payment_date') or datetime.now().strftime('%Y-%m-%d')
        remarks = request.form.get('remarks', '').strip()
        amount = safe_float(request.form.get('amount', 0))

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, owner_name FROM plots 
            WHERE LOWER(scheme_name) = LOWER(?) AND UPPER(plot_type) = UPPER(?) AND UPPER(plot_number) = UPPER(?)
        """, (active_scheme, category, plot_number))
        plot = cursor.fetchone()

        if not plot:
            conn.close()
            flash(f'Plot Number "{plot_number}" not found in {active_scheme} ({category})!', 'danger')
            return render_template('add_installment.html', default_category=category, entered_plot_number=plot_number)

        plot_id = plot[0]

        cursor.execute('''
            INSERT INTO payments (plot_id, amount, payment_date, receipt_no, remarks)
            VALUES (?, ?, ?, ?, ?)
        ''', (plot_id, amount, payment_date, receipt_no, remarks))

        cursor.execute('''
            INSERT INTO installments (plot_id, amount, payment_date, receipt_no, remarks)
            VALUES (?, ?, ?, ?, ?)
        ''', (plot_id, amount, payment_date, receipt_no, remarks))

        conn.commit()
        conn.close()

        flash(f'Payment saved successfully for Plot #{plot_number} ({plot[1]})!', 'success')
        return redirect(url_for('ledger', plot_id=plot_id))

    return render_template('add_installment.html', default_category=default_category, entered_plot_number=entered_plot_number)
# --- END: Route /add-installment ---


# --- START: Route /ledger/<plot_id> ---
# Maqsad: Kisi bhi single plot ka mukammal Customer Account Ledger Statement aur Transaction History dikhana
@app.route('/ledger/<int:plot_id>')
@login_required
def ledger(plot_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Database Column Query Mapping
    cursor.execute("""
        SELECT id, scheme_name, plot_number, plot_type, plot_size, 
               owner_name, nic_no, mobile_no, rate_per_sqft, total_cost, 
               advance, payment_type, payment_date, remarks
        FROM plots 
        WHERE id = ?
    """, (plot_id,))
    p = cursor.fetchone()

    if not p:
        conn.close()
        flash('Plot not found!', 'danger')
        return redirect(url_for('dashboard'))

    plot = {
        'id': p[0],
        'scheme_name': p[1],
        'plot_number': p[2],
        'plot_type': p[3],
        'plot_size': safe_float(p[4]),
        'owner_name': p[5],
        'nic_no': p[6],
        'mobile_no': p[7],
        'rate_per_sqft': safe_float(p[8]),
        'total_cost': safe_float(p[9]),
        'advance': safe_float(p[10]),
        'payment_type': p[11] if p[11] else 'Advance',
        'payment_date': p[12],
        'remarks': p[13] if p[13] else ''
    }

    cursor.execute("""
        SELECT amount, payment_date, receipt_no, remarks 
        FROM payments 
        WHERE plot_id = ? 
        ORDER BY payment_date ASC, id ASC
    """, (plot_id,))
    payments_raw = cursor.fetchall()
    
    if not payments_raw:
        cursor.execute("""
            SELECT amount, payment_date, receipt_no, remarks 
            FROM installments 
            WHERE plot_id = ? 
            ORDER BY payment_date ASC, id ASC
        """, (plot_id,))
        payments_raw = cursor.fetchall()

    conn.close()

    payments = []
    running_balance = plot['total_cost'] - plot['advance']
    total_paid = plot['advance']

    for pay in payments_raw:
        amt = safe_float(pay[0])
        total_paid += amt
        running_balance -= amt
        payments.append({
            'amount': amt,
            'payment_date': pay[1],
            'receipt_no': pay[2],
            'remarks': pay[3],
            'running_balance': running_balance
        })

    plot['total_paid'] = total_paid
    plot['remaining_balance'] = plot['total_cost'] - total_paid

    return render_template('ledger.html', plot=plot, payments=payments)
# --- END: Route /ledger/<plot_id> ---


# --- START: Route /manage-users (Admin Panel) ---
# Maqsad: Admin ke zariye system ke new users create karna aur directory list dikhana
@app.route('/manage-users', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip().lower()
        new_password = request.form.get('password', '').strip()
        new_role = request.form.get('role', 'officeboy').strip()

        if not new_username or not new_password:
            flash('Username and Password are required!', 'danger')
        else:
            cursor.execute("SELECT id FROM users WHERE username = ?", (new_username,))
            if cursor.fetchone():
                flash(f'Username "{new_username}" already exists!', 'danger')
            else:
                hashed_pw = generate_password_hash(new_password)
                cursor.execute("INSERT INTO users (username, password, plain_password, role) VALUES (?, ?, ?, ?)",
                               (new_username, hashed_pw, new_password, new_role))
                conn.commit()
                flash(f'User "{new_username}" created successfully as {new_role.upper()}!', 'success')

    cursor.execute("SELECT id, username, plain_password, role FROM users ORDER BY id ASC")
    raw_users = cursor.fetchall()
    conn.close()

    users_list = []
    for u in raw_users:
        user_id, username, plain_pw, role = u
        if not plain_pw:
            if username == 'admin':
                plain_pw = 'admin123'
            elif username == 'officeboy':
                plain_pw = 'boy123'
            else:
                plain_pw = 'Password Set'

        users_list.append({
            'id': user_id,
            'username': username,
            'password': plain_pw,
            'role': role
        })

    return render_template('manage_users.html', users_list=users_list)
# --- END: Route /manage-users ---


# --- START: Route /change-password/<user_id> ---
# Maqsad: Admin dwara kisi bhi specific user ka password update/change karna
@app.route('/change-password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def change_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if not new_password:
        flash('Password cannot be empty!', 'danger')
        return redirect(url_for('manage_users'))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hashed_pw = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ?, plain_password = ? WHERE id = ?", (hashed_pw, new_password, user_id))
    conn.commit()
    conn.close()

    flash('User password updated successfully!', 'success')
    return redirect(url_for('manage_users'))
# --- END: Route /change-password/<user_id> ---


# --- START: Route /delete-user/<user_id> ---
# Maqsad: Admin dwara kisi user ko system se delete karna
@app.route('/delete-user/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        if user[0] == 'admin' or user[0] == session.get('user'):
            flash('Cannot delete primary Admin or currently logged in user!', 'danger')
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash(f'User "{user[0]}" deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('manage_users'))
# --- END: Route /delete-user/<user_id> ---


# ==============================================================================
# SECTION 7: SERVER EXECUTION
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)  # Application development mode mein start ho rahi hai
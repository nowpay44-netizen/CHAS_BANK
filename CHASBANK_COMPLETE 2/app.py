from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, hashlib, secrets, os, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("CHASBANK_SECRET", "CHANGE-ME-IN-PRODUCTION")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chasbank.db")

DEMO_BANKS = [
    {"name": "CHASBANK Demo", "routing": "000000001"},
    {"name": "Access Bank Demo", "routing": "000000002"},
    {"name": "GTBank Demo", "routing": "000000003"},
    {"name": "Zenith Bank Demo", "routing": "000000004"},
    {"name": "First Bank Demo", "routing": "000000005"},
    {"name": "UBA Demo", "routing": "000000006"},
    {"name": "Moniepoint Demo", "routing": "000000007"},
    {"name": "Opay Demo", "routing": "000000008"},
    {"name": "Kuda Demo", "routing": "000000009"},
]

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def hp(p):
    return hashlib.sha256(p.encode()).hexdigest()

def money(v):
    try:
        x = float(v)
        return x if x == x and x != float("inf") and x != float("-inf") else 0.0
    except (TypeError, ValueError):
        return 0.0

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      pin_hash TEXT,
      balance REAL NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      kind TEXT NOT NULL,
      amount REAL NOT NULL,
      direction TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'completed',
      note TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      sender TEXT NOT NULL,
      body TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reset_tokens(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      token TEXT UNIQUE NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS beneficiaries(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      beneficiary_name TEXT NOT NULL,
      bank_name TEXT NOT NULL,
      routing_code TEXT NOT NULL,
      account_number TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(user_id, bank_name, routing_code, account_number)
    );
    CREATE TABLE IF NOT EXISTS transfer_records(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      reference TEXT UNIQUE NOT NULL,
      beneficiary_name TEXT NOT NULL,
      bank_name TEXT NOT NULL,
      routing_code TEXT NOT NULL,
      account_number TEXT NOT NULL,
      amount REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'successful',
      created_at TEXT NOT NULL
    );
    """)
    if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        c.execute("INSERT INTO users(username,name,password_hash,created_at) VALUES(?,?,?,?)",
                  ("admin", "CHASBANK Administrator", hp("admin123"), now()))
    c.commit(); c.close()

def user():
    uid = session.get("uid")
    if not uid:
        return None
    c = conn(); u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); c.close()
    return u

@app.context_processor
def inject():
    return {"user": user()}

def login_required():
    return user() is not None

def admin_required():
    u = user()
    return u is not None and u["username"] == "admin"

@app.route("/")
def home():
    return redirect(url_for("dashboard") if login_required() else url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        if not name or len(username) < 3 or len(password) < 6:
            flash("Enter a name, a username of at least 3 characters, and a password of at least 6 characters.")
            return redirect(url_for("signup"))
        c = conn()
        try:
            c.execute("INSERT INTO users(username,name,password_hash,created_at) VALUES(?,?,?,?)",
                      (username, name, hp(password), now()))
            c.commit()
            new_user = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            session.clear(); session["uid"] = new_user["id"]
            flash("Account created successfully. Your starting demo balance is $0.00.")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
        finally:
            c.close()
    return render_template("auth.html", mode="signup")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        c = conn(); u = c.execute("SELECT * FROM users WHERE username=? AND password_hash=?", (username, hp(password))).fetchone(); c.close()
        if u and u["status"] == "active":
            session.clear(); session["uid"] = u["id"]
            return redirect(url_for("admin") if u["username"] == "admin" else url_for("dashboard"))
        flash("Invalid login or account is disabled.")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    link = None
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        c = conn(); u = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if u:
            token = secrets.token_urlsafe(24)
            c.execute("INSERT INTO reset_tokens(user_id,token,created_at) VALUES(?,?,?)", (u["id"], token, now()))
            c.commit(); link = url_for("reset", token=token, _external=True)
        c.close(); flash("If the account exists, a reset link has been generated for this local demo.")
    return render_template("forgot.html", link=link)

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    c = conn(); r = c.execute("SELECT * FROM reset_tokens WHERE token=?", (token,)).fetchone()
    if not r:
        c.close(); return "Invalid or expired reset link", 404
    if request.method == "POST":
        p = request.form["password"]
        if len(p) < 6:
            flash("Password must be at least 6 characters.")
        else:
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hp(p), r["user_id"]))
            c.execute("DELETE FROM reset_tokens WHERE id=?", (r["id"],)); c.commit(); c.close()
            flash("Password changed successfully."); return redirect(url_for("login"))
    c.close(); return render_template("reset.html")

@app.route("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    u = user()
    if u and u["username"] == "admin": return redirect(url_for("admin"))
    c = conn()
    tx = c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (u["id"],)).fetchall()
    msgs = c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 8", (u["id"],)).fetchall()
    beneficiaries = c.execute("SELECT * FROM beneficiaries WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    c.close()
    return render_template("dashboard.html", tx=tx, msgs=msgs, beneficiaries=beneficiaries, banks=DEMO_BANKS)

@app.route("/history")
def history():
    if not login_required(): return redirect(url_for("login"))
    c = conn(); tx = c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC", (user()["id"],)).fetchall(); c.close()
    return render_template("history.html", tx=tx)

def add_tx(c, uid, kind, amount, direction, note):
    c.execute("INSERT INTO transactions(user_id,kind,amount,direction,status,note,created_at) VALUES(?,?,?,?,?,?,?)",
              (uid, kind, amount, direction, "completed", note, now()))

@app.route("/action/deposit", methods=["POST"])
def deposit():
    if not login_required(): return redirect(url_for("login"))
    flash("Deposits are disabled for customer self-funding. The administrator must add demo credits.")
    return redirect(url_for("dashboard"))

@app.route("/action/withdraw", methods=["POST"])
def withdraw():
    u = user()
    if not u: return redirect(url_for("login"))
    amount = money(request.form.get("amount")); pin = request.form.get("pin", "")
    if amount <= 0 or amount > u["balance"]: flash("Invalid amount or insufficient demo balance."); return redirect(url_for("dashboard"))
    if not u["pin_hash"] or hp(pin) != u["pin_hash"]: flash("Incorrect transaction PIN."); return redirect(url_for("dashboard"))
    c = conn(); c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, u["id"]))
    add_tx(c, u["id"], "Withdrawal", amount, "debit", "Demo withdrawal")
    c.commit(); c.close(); flash("Demo withdrawal completed."); return redirect(url_for("dashboard"))

@app.route("/action/transfer", methods=["POST"])
def transfer():
    u = user()
    if not u: return redirect(url_for("login"))
    beneficiary = request.form.get("beneficiary_name", "").strip()
    bank = request.form.get("bank_name", "").strip()
    routing = request.form.get("routing_code", "").strip()
    account = request.form.get("account_number", "").strip()
    amount = money(request.form.get("amount")); pin = request.form.get("pin", "")
    if not beneficiary or not bank or not account or not re.fullmatch(r"\d{6,20}", account):
        flash("Enter valid beneficiary and account details."); return redirect(url_for("dashboard"))
    if not re.fullmatch(r"[A-Za-z0-9-]{4,20}", routing):
        flash("Enter a valid demo routing code."); return redirect(url_for("dashboard"))
    if amount <= 0 or amount > u["balance"]: flash("Invalid amount or insufficient demo balance."); return redirect(url_for("dashboard"))
    if not u["pin_hash"] or hp(pin) != u["pin_hash"]: flash("Incorrect transaction PIN."); return redirect(url_for("dashboard"))
    c = conn()
    c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, u["id"]))
    reference = "CHS" + datetime.now().strftime("%Y%m%d") + secrets.token_hex(4).upper()
    add_tx(c, u["id"], "Bank Transfer", amount, "debit", f"Demo transfer to {beneficiary} · {bank} · Routing {routing} · A/C {account}")
    c.execute("INSERT OR IGNORE INTO beneficiaries(user_id,beneficiary_name,bank_name,routing_code,account_number,created_at) VALUES(?,?,?,?,?,?)",
              (u["id"], beneficiary, bank, routing, account, now()))
    c.execute("INSERT INTO transfer_records(user_id,reference,beneficiary_name,bank_name,routing_code,account_number,amount,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (u["id"], reference, beneficiary, bank, routing, account, amount, "successful", now()))
    c.commit(); c.close()
    return redirect(url_for("receipt", reference=reference))

@app.route("/receipt/<reference>")
def receipt(reference):
    if not login_required(): return redirect(url_for("login"))
    c = conn(); r = c.execute("SELECT tr.*,u.username,u.name FROM transfer_records tr JOIN users u ON u.id=tr.user_id WHERE tr.reference=?", (reference,)).fetchone(); c.close()
    if not r: return "Receipt not found", 404
    if user()["username"] != "admin" and r["user_id"] != user()["id"]: return "Forbidden", 403
    return render_template("receipt.html", receipt=r)

@app.route("/beneficiary/delete/<int:bid>", methods=["POST"])
def delete_beneficiary(bid):
    u = user()
    if not u: return redirect(url_for("login"))
    c = conn(); c.execute("DELETE FROM beneficiaries WHERE id=? AND user_id=?", (bid, u["id"])); c.commit(); c.close(); return redirect(url_for("dashboard"))

@app.route("/set-pin", methods=["POST"])
def set_pin():
    u = user()
    if not u: return redirect(url_for("login"))
    pin = request.form.get("pin", "")
    if len(pin) != 4 or not pin.isdigit(): flash("PIN must be exactly 4 digits.")
    else:
        c = conn(); c.execute("UPDATE users SET pin_hash=? WHERE id=?", (hp(pin), u["id"])); c.commit(); c.close(); flash("Transaction PIN updated.")
    return redirect(url_for("dashboard"))

@app.route("/support", methods=["POST"])
def support():
    u = user()
    if not u: return redirect(url_for("login"))
    body = request.form.get("body", "").strip()
    if body:
        c = conn(); c.execute("INSERT INTO messages(user_id,sender,body,created_at) VALUES(?,?,?,?)", (u["id"], "customer", body, now())); c.commit(); c.close()
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin():
    if not admin_required(): return "Admin only", 403
    c = conn()
    users = c.execute("SELECT * FROM users WHERE username!='admin' ORDER BY id DESC").fetchall()
    tx = c.execute("SELECT t.*,u.username FROM transactions t JOIN users u ON u.id=t.user_id ORDER BY t.id DESC LIMIT 50").fetchall()
    msgs = c.execute("SELECT m.*,u.username FROM messages m JOIN users u ON u.id=m.user_id ORDER BY m.id DESC LIMIT 50").fetchall()
    transfers = c.execute("SELECT tr.*,u.username FROM transfer_records tr JOIN users u ON u.id=tr.user_id ORDER BY tr.id DESC LIMIT 30").fetchall()
    total = c.execute("SELECT COALESCE(SUM(balance),0) v FROM users WHERE username!='admin'").fetchone()["v"]
    count = c.execute("SELECT COUNT(*) v FROM users WHERE username!='admin'").fetchone()["v"]
    open_msgs = c.execute("SELECT COUNT(*) v FROM messages WHERE status='open'").fetchone()["v"]
    c.close()
    return render_template("admin.html", users=users, tx=tx, msgs=msgs, transfers=transfers, total=total, count=count, open_msgs=open_msgs)

@app.route("/admin/generate-funds", methods=["POST"])
def admin_generate_funds():
    if not admin_required(): return "Admin only", 403
    amount = money(request.form.get("amount"))
    if amount <= 0: flash("Enter a positive amount."); return redirect(url_for("admin"))
    c = conn(); admin_id = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
    c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, admin_id))
    add_tx(c, admin_id, "Generated demo funds", amount, "credit", "Virtual simulation funds created by administrator")
    c.commit(); c.close(); flash(f"${amount:,.2f} virtual demo funds generated for the administrator."); return redirect(url_for("admin"))

@app.route("/admin/fund", methods=["POST"])
def admin_fund():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); amount = money(request.form.get("amount"))
    if amount <= 0: flash("Enter a positive amount."); return redirect(url_for("admin"))
    c = conn(); admin_row = c.execute("SELECT id,balance FROM users WHERE username='admin'").fetchone()
    target = c.execute("SELECT id,username,status FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if not target or target["status"] != "active": c.close(); flash("Customer not found or is disabled."); return redirect(url_for("admin"))
    if amount > admin_row["balance"]: c.close(); flash("Insufficient admin demo balance. Generate virtual funds first."); return redirect(url_for("admin"))
    c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, admin_row["id"]))
    c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
    add_tx(c, admin_row["id"], "Customer funding", amount, "debit", f"Demo funds sent to @{target['username']}")
    add_tx(c, uid, "Admin credit", amount, "credit", "Demo credit added by administrator")
    c.commit(); c.close(); flash(f"${amount:,.2f} demo credits added to @{target['username']}."); return redirect(url_for("admin"))

@app.route("/admin/set-balance", methods=["POST"])
def admin_set_balance():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); amount = max(0.0, money(request.form.get("amount")))
    c = conn(); u = c.execute("SELECT balance,username FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if not u: c.close(); return redirect(url_for("admin"))
    delta = amount - u["balance"]; c.execute("UPDATE users SET balance=? WHERE id=?", (amount, uid))
    if delta: add_tx(c, uid, "Admin balance adjustment", abs(delta), "credit" if delta > 0 else "debit", "Demo balance adjustment by administrator")
    c.commit(); c.close(); flash(f"Balance for @{u['username']} set to ${amount:,.2f}."); return redirect(url_for("admin"))

@app.route("/admin/customer-debit", methods=["POST"])
def admin_customer_debit():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); amount = money(request.form.get("amount")); note = request.form.get("note", "Admin debit")[:160]
    if amount <= 0: flash("Enter a positive amount."); return redirect(url_for("admin"))
    c = conn(); u = c.execute("SELECT balance,username FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if not u or amount > u["balance"]: c.close(); flash("Customer not found or insufficient customer demo balance."); return redirect(url_for("admin"))
    c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, uid)); add_tx(c, uid, "Admin debit", amount, "debit", note or "Admin debit")
    c.commit(); c.close(); flash(f"${amount:,.2f} debited from @{u['username']}."); return redirect(url_for("admin"))

@app.route("/admin/customer-credit", methods=["POST"])
def admin_customer_credit():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); amount = money(request.form.get("amount")); note = request.form.get("note", "Admin credit")[:160]
    if amount <= 0: flash("Enter a positive amount."); return redirect(url_for("admin"))
    c = conn(); u = c.execute("SELECT username FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if not u: c.close(); flash("Customer not found."); return redirect(url_for("admin"))
    c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid)); add_tx(c, uid, "Admin credit", amount, "credit", note or "Admin credit")
    c.commit(); c.close(); flash(f"${amount:,.2f} credited to @{u['username']}."); return redirect(url_for("admin"))

@app.route("/admin/create-history", methods=["POST"])
def admin_create_history():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); kind = request.form.get("kind", "Admin entry")[:80]; amount = money(request.form.get("amount")); direction = request.form.get("direction", "credit")
    note = request.form.get("note", "Admin-created demo history")[:180]
    if amount <= 0 or direction not in ("credit", "debit"): flash("Enter a valid amount and direction."); return redirect(url_for("admin"))
    c = conn(); u = c.execute("SELECT username FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if not u: c.close(); flash("Customer not found."); return redirect(url_for("admin"))
    add_tx(c, uid, kind, amount, direction, note); c.commit(); c.close(); flash(f"History entry created for @{u['username']}."); return redirect(url_for("admin"))

@app.route("/admin/toggle-user", methods=["POST"])
def toggle_user():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); c = conn(); u = c.execute("SELECT status,username FROM users WHERE id=? AND username!='admin'", (uid,)).fetchone()
    if u: c.execute("UPDATE users SET status=? WHERE id=?", ("disabled" if u["status"] == "active" else "active", uid))
    c.commit(); c.close(); return redirect(url_for("admin"))

@app.route("/admin/message", methods=["POST"])
def admin_message():
    if not admin_required(): return "Admin only", 403
    uid = int(request.form["user_id"]); body = request.form.get("body", "").strip()
    if body:
        c = conn(); c.execute("INSERT INTO messages(user_id,sender,body,status,created_at) VALUES(?,?,?,?,?)", (uid, "admin", body, "replied", now())); c.commit(); c.close()
    return redirect(url_for("admin"))

@app.route("/admin/close-message", methods=["POST"])
def close_message():
    if not admin_required(): return "Admin only", 403
    mid = int(request.form["message_id"]); c = conn(); c.execute("UPDATE messages SET status='closed' WHERE id=?", (mid,)); c.commit(); c.close(); return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)

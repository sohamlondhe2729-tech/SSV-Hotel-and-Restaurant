import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restaurant.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        capacity INTEGER NOT NULL DEFAULT 4,
        section TEXT NOT NULL DEFAULT 'Main Hall',
        status TEXT NOT NULL DEFAULT 'Available'
    );

    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Main Course',
        price REAL NOT NULL,
        is_veg INTEGER NOT NULL DEFAULT 1,
        available INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS khata_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        billing_cycle TEXT NOT NULL DEFAULT 'Monthly',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_type TEXT NOT NULL DEFAULT 'Dine-In',
        table_id INTEGER,
        table_name TEXT,
        status TEXT NOT NULL DEFAULT 'Open',
        discount REAL NOT NULL DEFAULT 0,
        payment_mode TEXT,
        khata_customer_id INTEGER,
        total_amount REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        closed_at TEXT,
        FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE SET NULL,
        FOREIGN KEY (khata_customer_id) REFERENCES khata_customers(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        menu_item_id INTEGER,
        item_name TEXT NOT NULL,
        price REAL NOT NULL,
        qty INTEGER NOT NULL DEFAULT 1,
        kot_status TEXT NOT NULL DEFAULT 'Pending',
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS khata_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        tx_type TEXT NOT NULL, -- 'DEBIT' (udhari added) or 'CREDIT' (payment received)
        amount REAL NOT NULL,
        payment_mode TEXT DEFAULT 'Cash',
        note TEXT DEFAULT '',
        order_id INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES khata_customers(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def get_full_state():
    conn = get_db()
    tables = [dict(r) for r in conn.execute("SELECT * FROM tables ORDER BY id").fetchall()]
    menu = [dict(r) for r in conn.execute("SELECT * FROM menu_items ORDER BY category, name").fetchall()]

    orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()]
    for o in orders:
        o["items"] = [
            dict(i)
            for i in conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
        ]

    customers = [dict(r) for r in conn.execute("SELECT * FROM khata_customers ORDER BY name").fetchall()]
    txs = [dict(r) for r in conn.execute("SELECT * FROM khata_transactions ORDER BY id DESC").fetchall()]
    for c in customers:
        c_txs = [t for t in txs if t["customer_id"] == c["id"]]
        debit = sum(t["amount"] for t in c_txs if t["tx_type"] == "DEBIT")
        credit = sum(t["amount"] for t in c_txs if t["tx_type"] == "CREDIT")
        c["balance"] = round(debit - credit, 2)
        c["transactions"] = c_txs

    conn.close()
    return jsonify({"tables": tables, "menu": menu, "orders": orders, "khata_customers": customers})


@app.route("/api/tables", methods=["POST"])
def add_table():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    capacity = int(data.get("capacity") or 4)
    section = (data.get("section") or "Main Hall").strip()
    if not name:
        return jsonify({"error": "Table name is required"}), 400
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO tables (name, capacity, section, status) VALUES (?, ?, ?, 'Available')",
            (name, capacity, section),
        )
        conn.commit()
        row = dict(conn.execute("SELECT * FROM tables WHERE id = ?", (cur.lastrowid,)).fetchone())
        return jsonify(row), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Table name already exists"}), 400
    finally:
        conn.close()


@app.route("/api/tables/<int:table_id>", methods=["DELETE"])
def delete_table(table_id):
    conn = get_db()
    table = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
    if not table:
        conn.close()
        return jsonify({"error": "Table not found"}), 404
    if table["status"] == "Occupied":
        conn.close()
        return jsonify({"error": "Cannot delete an occupied table"}), 400
    conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/menu", methods=["POST"])
def add_menu_item():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "Main Course").strip()
    price = float(data.get("price") or 0)
    is_veg = 1 if data.get("is_veg", True) else 0
    if not name or price <= 0:
        return jsonify({"error": "Valid item name and price required"}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO menu_items (name, category, price, is_veg) VALUES (?, ?, ?, ?)",
        (name, category, price, is_veg),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM menu_items WHERE id = ?", (cur.lastrowid,)).fetchone())
    conn.close()
    return jsonify(row), 201


@app.route("/api/menu/<int:item_id>", methods=["DELETE"])
def delete_menu_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json() or {}
    order_type = data.get("order_type", "Dine-In")
    table_id = data.get("table_id")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    table_name = "Takeaway"
    if order_type == "Dine-In" and table_id:
        t = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
        if not t:
            conn.close()
            return jsonify({"error": "Table not found"}), 404
        table_name = t["name"]
        conn.execute("UPDATE tables SET status = 'Occupied' WHERE id = ?", (table_id,))
    cur = conn.execute(
        "INSERT INTO orders (order_type, table_id, table_name, status, created_at) VALUES (?, ?, ?, 'Open', ?)",
        (order_type, table_id, table_name, now),
    )
    conn.commit()
    order_id = cur.lastrowid
    conn.close()
    return jsonify({"id": order_id}), 201


@app.route("/api/orders/<int:order_id>/items", methods=["POST"])
def add_order_item(order_id):
    data = request.get_json() or {}
    item_name = (data.get("item_name") or "").strip()
    price = float(data.get("price") or 0)
    qty = int(data.get("qty") or 1)
    menu_item_id = data.get("menu_item_id")
    if not item_name or price <= 0 or qty <= 0:
        return jsonify({"error": "Invalid item details"}), 400
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? AND item_name = ? AND price = ?",
        (order_id, item_name, price),
    ).fetchone()
    if existing:
        conn.execute("UPDATE order_items SET qty = qty + ? WHERE id = ?", (qty, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO order_items (order_id, menu_item_id, item_name, price, qty) VALUES (?, ?, ?, ?, ?)",
            (order_id, menu_item_id, item_name, price, qty),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/order-items/<int:oi_id>", methods=["PATCH", "DELETE"])
def update_order_item(oi_id):
    conn = get_db()
    if request.method == "DELETE":
        conn.execute("DELETE FROM order_items WHERE id = ?", (oi_id,))
    else:
        data = request.get_json() or {}
        if "qty" in data:
            qty = int(data["qty"])
            if qty <= 0:
                conn.execute("DELETE FROM order_items WHERE id = ?", (oi_id,))
            else:
                conn.execute("UPDATE order_items SET qty = ? WHERE id = ?", (qty, oi_id))
        if "kot_status" in data:
            conn.execute("UPDATE order_items SET kot_status = ? WHERE id = ?", (data["kot_status"], oi_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/orders/<int:order_id>/bill", methods=["POST"])
def settle_bill(order_id):
    data = request.get_json() or {}
    discount = float(data.get("discount") or 0)
    payment_mode = data.get("payment_mode", "Cash")
    khata_customer_id = data.get("khata_customer_id")

    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    subtotal = sum(i["price"] * i["qty"] for i in items)
    total = max(0.0, round(subtotal - discount, 2))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if payment_mode == "Khata" and not khata_customer_id:
        conn.close()
        return jsonify({"error": "Select a Khata customer for Udhari"}), 400

    conn.execute(
        """UPDATE orders
           SET status = 'Paid', discount = ?, payment_mode = ?, khata_customer_id = ?, total_amount = ?, closed_at = ?
           WHERE id = ?""",
        (discount, payment_mode, khata_customer_id if payment_mode == "Khata" else None, total, now, order_id),
    )

    if order["table_id"]:
        conn.execute("UPDATE tables SET status = 'Available' WHERE id = ?", (order["table_id"],))

    if payment_mode == "Khata" and khata_customer_id:
        conn.execute(
            """INSERT INTO khata_transactions (customer_id, tx_type, amount, payment_mode, note, order_id, created_at)
               VALUES (?, 'DEBIT', ?, 'Khata', ?, ?, ?)""",
            (khata_customer_id, total, f"Bill #{order_id} ({order['table_name']})", order_id, now),
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "total_amount": total})


@app.route("/api/khata/customers", methods=["POST"])
def add_khata_customer():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    billing_cycle = data.get("billing_cycle", "Monthly")
    notes = (data.get("notes") or "").strip()
    if not name or not phone:
        return jsonify({"error": "Name and phone are required"}), 400
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO khata_customers (name, phone, billing_cycle, notes, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, phone, billing_cycle, notes, now),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM khata_customers WHERE id = ?", (cur.lastrowid,)).fetchone())
    conn.close()
    return jsonify(row), 201


@app.route("/api/khata/customers/<int:customer_id>/debit", methods=["POST"])
def add_khata_debit(customer_id):
    data = request.get_json() or {}
    amount = float(data.get("amount") or 0)
    note = (data.get("note") or "Direct Udhari entry").strip()
    if amount <= 0:
        return jsonify({"error": "Udhari amount must be greater than 0"}), 400
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute(
        """INSERT INTO khata_transactions (customer_id, tx_type, amount, payment_mode, note, created_at)
           VALUES (?, 'DEBIT', ?, 'Khata', ?, ?)""",
        (customer_id, amount, note, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/khata/customers/<int:customer_id>/pay", methods=["POST"])
def record_khata_payment(customer_id):
    data = request.get_json() or {}
    amount = float(data.get("amount") or 0)
    payment_mode = data.get("payment_mode", "Cash")
    note = (data.get("note") or "Khata settlement").strip()
    if amount <= 0:
        return jsonify({"error": "Payment amount must be greater than 0"}), 400
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute(
        """INSERT INTO khata_transactions (customer_id, tx_type, amount, payment_mode, note, created_at)
           VALUES (?, 'CREDIT', ?, ?, ?, ?)""",
        (customer_id, amount, payment_mode, note, now),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)

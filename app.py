
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, g

app = Flask(__name__)

DATABASE = os.path.join(
    app.instance_path,
    "businesspulse.db"
)

os.makedirs(app.instance_path, exist_ok=True)


# -----------------------------------
# DATABASE CONNECTION
# -----------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


# -----------------------------------
# DATABASE INITIALIZATION
# -----------------------------------

def init_db():
    db = get_db()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK(price >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE SET NULL
        );
    """)

    product_count = db.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    if product_count == 0:
        products = [
            ("Laptop", "Electronics", 55000, 12),
            ("Smartphone", "Electronics", 18000, 25),
            ("Keyboard", "Accessories", 1200, 40),
            ("Mouse", "Accessories", 650, 35),
            ("Monitor", "Electronics", 12000, 8),
            ("Headphones", "Accessories", 2200, 4),
            ("Office Chair", "Furniture", 6500, 15),
            ("Desk", "Furniture", 8500, 10)
        ]

        db.executemany("""
            INSERT INTO products
            (name, category, price, stock)
            VALUES (?, ?, ?, ?)
        """, products)

        # Demo transaction history for analytics
        sample_sales = [
            (1, "Laptop", 1, 55000, 55000, 150),
            (2, "Smartphone", 2, 18000, 36000, 125),
            (3, "Keyboard", 3, 1200, 3600, 95),
            (4, "Mouse", 5, 650, 3250, 75),
            (5, "Monitor", 1, 12000, 12000, 60),
            (6, "Headphones", 2, 2200, 4400, 45),
            (7, "Office Chair", 1, 6500, 6500, 25),
            (8, "Desk", 2, 8500, 17000, 10)
        ]

        for product_id, name, quantity, price, total, days_ago in sample_sales:
            sale_date = (
                datetime.now() - timedelta(days=days_ago)
            ).strftime("%Y-%m-%d %H:%M:%S")

            db.execute("""
                INSERT INTO sales
                (product_id, product_name, quantity,
                 unit_price, total, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                product_id, name, quantity,
                price, total, sale_date
            ))

    db.commit()


# -----------------------------------
# HELPER FUNCTIONS
# -----------------------------------

def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status


def get_json():
    return request.get_json(silent=True) or {}


# -----------------------------------
# FRONTEND ROUTE
# -----------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------------
# DASHBOARD API
# -----------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():

    db = get_db()

    stats = db.execute("""
        SELECT
            COALESCE(SUM(total), 0) AS revenue,
            COUNT(*) AS orders,
            COALESCE(SUM(quantity), 0) AS units_sold
        FROM sales
    """).fetchone()

    products = db.execute("""
        SELECT COUNT(*) FROM products
    """).fetchone()[0]

    low_stock = db.execute("""
        SELECT COUNT(*) FROM products
        WHERE stock <= 5
    """).fetchone()[0]

    return jsonify({
        "success": True,
        "revenue": stats["revenue"],
        "orders": stats["orders"],
        "units_sold": stats["units_sold"],
        "products": products,
        "low_stock": low_stock
    })


# -----------------------------------
# PRODUCT APIs - CRUD
# -----------------------------------

@app.route("/api/products", methods=["GET"])
def get_products():

    db = get_db()

    products = db.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """).fetchall()

    return jsonify({
        "success": True,
        "products": [dict(p) for p in products]
    })


@app.route("/api/products", methods=["POST"])
def add_product():

    data = get_json()

    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()

    if not name or not category:
        return error_response("Name and category are required")

    try:
        price = float(data["price"])
        stock = int(data["stock"])

        if not 0 <= price <= 100000000:
            raise ValueError()

        if not 0 <= stock <= 10000000:
            raise ValueError()

    except (ValueError, TypeError, KeyError):
        return error_response("Enter valid price and stock values")

    db = get_db()

    cursor = db.execute("""
        INSERT INTO products
        (name, category, price, stock)
        VALUES (?, ?, ?, ?)
    """, (name, category, price, stock))

    db.commit()

    return jsonify({
        "success": True,
        "message": "Product added successfully",
        "id": cursor.lastrowid
    }), 201


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):

    data = get_json()

    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()

    if not name or not category:
        return error_response("Name and category are required")

    try:
        price = float(data["price"])
        stock = int(data["stock"])

        if not 0 <= price <= 100000000:
            raise ValueError()

        if not 0 <= stock <= 10000000:
            raise ValueError()

    except (ValueError, TypeError, KeyError):
        return error_response("Invalid price or stock")

    db = get_db()

    result = db.execute("""
        UPDATE products
        SET name = ?, category = ?, price = ?, stock = ?
        WHERE id = ?
    """, (name, category, price, stock, product_id))

    if result.rowcount == 0:
        db.rollback()
        return error_response("Product not found", 404)

    db.commit()

    return jsonify({
        "success": True,
        "message": "Product updated successfully"
    })


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):

    db = get_db()

    result = db.execute("""
        DELETE FROM products WHERE id = ?
    """, (product_id,))

    if result.rowcount == 0:
        return error_response("Product not found", 404)

    db.commit()

    return jsonify({
        "success": True,
        "message": "Product deleted successfully"
    })


# -----------------------------------
# SALES APIs
# -----------------------------------

@app.route("/api/sales", methods=["GET"])
def get_sales():

    db = get_db()

    sales = db.execute("""
        SELECT * FROM sales
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    return jsonify({
        "success": True,
        "sales": [dict(s) for s in sales]
    })


@app.route("/api/sales", methods=["POST"])
def create_sale():

    data = get_json()

    try:
        product_id = int(data["product_id"])
        quantity = int(data["quantity"])

        if product_id <= 0 or quantity <= 0:
            raise ValueError()

    except (ValueError, TypeError, KeyError):
        return error_response("Invalid product or quantity")

    db = get_db()

    try:
        # Acquire a write lock before checking stock
        db.execute("BEGIN IMMEDIATE")

        product = db.execute("""
            SELECT * FROM products WHERE id = ?
        """, (product_id,)).fetchone()

        if product is None:
            db.rollback()
            return error_response("Product not found", 404)

        if product["stock"] < quantity:
            db.rollback()
            return error_response("Insufficient inventory", 409)

        total = product["price"] * quantity

        db.execute("""
            INSERT INTO sales
            (product_id, product_name, quantity,
             unit_price, total)
            VALUES (?, ?, ?, ?, ?)
        """, (
            product_id,
            product["name"],
            quantity,
            product["price"],
            total
        ))

        db.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE id = ?
        """, (quantity, product_id))

        db.commit()

        return jsonify({
            "success": True,
            "message": "Sale recorded successfully",
            "total": total
        }), 201

    except sqlite3.Error:
        db.rollback()
        app.logger.exception("Sale transaction failed")
        return error_response("Database transaction failed", 500)


# -----------------------------------
# ANALYTICS API
# -----------------------------------

@app.route("/api/analytics/monthly", methods=["GET"])
def monthly_analytics():

    db = get_db()

    rows = db.execute("""
        SELECT
            strftime('%Y-%m', created_at) AS month,
            SUM(total) AS revenue
        FROM sales
        WHERE created_at >= date('now', '-5 months', 'start of month')
        GROUP BY month
        ORDER BY month
    """).fetchall()

    top_products = db.execute("""
        SELECT
            product_name,
            SUM(quantity) AS quantity,
            SUM(total) AS revenue
        FROM sales
        GROUP BY product_name
        ORDER BY quantity DESC
        LIMIT 5
    """).fetchall()

    return jsonify({
        "success": True,
        "monthly": [dict(r) for r in rows],
        "top_products": [dict(p) for p in top_products]
    })


# -----------------------------------
# APPLICATION STARTUP
# -----------------------------------

with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)

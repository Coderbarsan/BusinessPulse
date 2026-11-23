
import os
import sqlite3
import pandas as pd
import math
from io import BytesIO
from flask import send_file
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, g
from datetime import timedelta
from functools import wraps

from flask import (
    session,
    redirect,
    url_for
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-only-change-this-secret"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("FLASK_ENV") == "production"
)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

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

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'staff'
                CHECK(role IN ('admin', 'staff')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()


# -----------------------------------
# HELPER FUNCTIONS
# -----------------------------------

def error_response(message, status=400):
    return jsonify({"success": False, "error": message}), status


def get_json():
    return request.get_json(silent=True) or {}

# ==========================================
# ROLE-BASED ACCESS CONTROL
# ==========================================

def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if session.get("user_role") != "admin":
            return jsonify({
                "success": False,
                "error": "Admin permission required"
            }), 403

        return function(*args, **kwargs)

    return decorated_function


# -----------------------------------
# FRONTEND ROUTE
# -----------------------------------


# ==========================================
# PAGE ROUTES
# ==========================================

@app.route("/")
def index():

    if not session.get("user_id"):
        return redirect(url_for("login_page"))

    return render_template("index.html")


@app.route("/login")
def login_page():

    if session.get("user_id"):
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/register")
def register_page():

    if session.get("user_id"):
        return redirect(url_for("index"))

    return render_template("register.html")


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
# CSV EXPORT - PRODUCTS
# -----------------------------------

@app.route("/api/export/products", methods=["GET"])
def export_products():

    db = get_db()

    rows = db.execute("""
        SELECT id, name, category, price, stock, created_at
        FROM products
        ORDER BY id DESC
    """).fetchall()

    df = pd.DataFrame(
        [dict(row) for row in rows],
        columns=[
            "id", "name", "category",
            "price", "stock", "created_at"
        ]
    )

    output = BytesIO()

    output.write(
        df.to_csv(index=False).encode("utf-8-sig")
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="businesspulse_products.csv"
    )


# -----------------------------------
# CSV EXPORT - SALES
# -----------------------------------

@app.route("/api/export/sales", methods=["GET"])
def export_sales():

    db = get_db()

    rows = db.execute("""
        SELECT id, product_id, product_name,
               quantity, unit_price, total, created_at
        FROM sales
        ORDER BY id DESC
    """).fetchall()

    df = pd.DataFrame(
        [dict(row) for row in rows],
        columns=[
            "id", "product_id", "product_name",
            "quantity", "unit_price", "total",
            "created_at"
        ]
    )

    output = BytesIO()

    output.write(
        df.to_csv(index=False).encode("utf-8-sig")
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="businesspulse_sales.csv"
    )


# -----------------------------------
# JSON ERROR FOR LARGE UPLOADS
# -----------------------------------

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "success": False,
        "error": "File too large. Maximum upload size is 5 MB."
    }), 413




# -----------------------------------
# CSV IMPORT - PANDAS
# -----------------------------------

@app.route("/api/import/products", methods=["POST"])
@admin_required
def import_products():

    if "file" not in request.files:
        return error_response("No CSV file uploaded")

    file = request.files["file"]

    if not file.filename:
        return error_response("Please select a CSV file")

    if not file.filename.lower().endswith(".csv"):
        return error_response("Only CSV files are supported")

    try:
        # Read uploaded CSV using Pandas
        df = pd.read_csv(
            file.stream,
            encoding="utf-8-sig",
            dtype=object
        )

        # Normalize column names
        df.columns = (
            df.columns.astype(str)
            .str.strip()
            .str.lower()
        )

        required_columns = {
            "name", "category", "price", "stock"
        }

        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)

            return error_response(
                "Missing columns: " + ", ".join(sorted(missing))
            )

        if df.empty:
            return error_response("CSV file contains no records")

        if len(df) > 1000:
            return error_response(
                "Maximum 1000 products allowed per upload"
            )

        # Select only required columns
        df = df[
            ["name", "category", "price", "stock"]
        ].copy()

        # Clean text fields
        df["name"] = df["name"].fillna("").astype(str).str.strip()
        df["category"] = (
            df["category"].fillna("").astype(str).str.strip()
        )

        # Validate empty fields
        if (df["name"] == "").any():
            return error_response(
                "Product names cannot be empty"
            )

        if (df["category"] == "").any():
            return error_response(
                "Product categories cannot be empty"
            )

        # Convert numeric fields
        df["price"] = pd.to_numeric(
            df["price"], errors="coerce"
        )

        df["stock"] = pd.to_numeric(
            df["stock"], errors="coerce"
        )

        # Reject invalid numeric values
        if df[["price", "stock"]].isna().any().any():
            return error_response(
                "Price and stock must contain valid numbers"
            )

        # Validate price
        if not df["price"].between(
            0, 100000000
        ).all():
            return error_response(
                "Price must be between 0 and 100000000"
            )

        # Stock must be a non-negative integer
        if not df["stock"].between(
            0, 10000000
        ).all() or not (df["stock"] % 1 == 0).all():

            return error_response(
                "Stock must be a non-negative integer"
            )

        # Reject duplicate products within uploaded CSV
        duplicate_mask = df.duplicated(
            subset=["name", "category"],
            keep=False
        )

        if duplicate_mask.any():
            return error_response(
                "Duplicate product names found in CSV"
            )

        # Prepare records
        records = [
            (
                row["name"],
                row["category"],
                float(row["price"]),
                int(row["stock"])
            )
            for _, row in df.iterrows()
        ]

        db = get_db()
        # Atomic database transaction
        db.execute("BEGIN IMMEDIATE")

        # Check whether products already exist in database
        for name, category, price, stock in records:
            existing = db.execute("""
            SELECT id FROM products
            WHERE LOWER(name) = LOWER(?)
            AND LOWER(category) = LOWER(?)
            """, (name, category)).fetchone()

            if existing:
                db.rollback()

                return error_response(
                    f"Product already exists: {name}"
                )

        # Insert all records together
        db.executemany("""
            INSERT INTO products
            (name, category, price, stock)
            VALUES (?, ?, ?, ?)
        """, records)

        db.commit()

        return jsonify({
            "success": True,
            "message": "CSV imported successfully",
            "total_imported": len(records)
        }), 201

    except (pd.errors.ParserError, UnicodeDecodeError):
        return error_response("Invalid or corrupted CSV file")

    except pd.errors.EmptyDataError:
        return error_response("CSV file is empty")

    except sqlite3.Error:
        get_db().rollback()
        app.logger.exception("CSV database import failed")

        return error_response(
            "Database import failed. No products were imported.",
            500
        )

    except Exception:
        app.logger.exception("Unexpected CSV import error")

        return error_response(
            "Unable to process CSV file",
            500
        )





# ==========================================
# PHASE 3: USER AUTHENTICATION
# ==========================================

@app.route("/api/auth/register", methods=["POST"])
def api_register():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "error": "All fields are required"
        }), 400

    if len(name) > 100 or len(email) > 254:
        return jsonify({
            "success": False,
            "error": "Name or email is too long"
        }), 400

    import re

    if not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
        email
    ):
        return jsonify({
            "success": False,
            "error": "Please enter a valid email address"
        }), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "success": False,
            "error": "Password must contain at least 8 characters"
        }), 400

    if len(password) > 128:
        return jsonify({
            "success": False,
            "error": "Password is too long"
        }), 400

    db = get_db()

    password_hash = generate_password_hash(password)

    try:
        db.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, 'staff')
        """, (name, email, password_hash))

        db.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful. Please login."
        }), 201

    except sqlite3.IntegrityError:
        db.rollback()

        return jsonify({
            "success": False,
            "error": "An account with this email already exists"
        }), 409


# ==========================================
# API AUTHENTICATION MIDDLEWARE
# ==========================================


@app.before_request
def protect_api_routes():

    if not request.path.startswith("/api/"):
        return None

    public_endpoints = {
        "api_register",
        "api_login",
        "api_logout"
    }

    if request.endpoint in public_endpoints:
        return None

    if not session.get("user_id"):
        return jsonify({
            "success": False,
            "error": "Authentication required. Please login."
        }), 401

    return None






# ==========================================
# LOGIN API
# ==========================================

@app.route("/api/auth/login", methods=["POST"])
def api_login():

    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not isinstance(password, str) or not password:
        return jsonify({
            "success": False,
            "error": "Email and password are required"
        }), 400

    db = get_db()

    user = db.execute("""
        SELECT id, name, email, password_hash, role
        FROM users
        WHERE email = ?
    """, (email,)).fetchone()

    if not user or not check_password_hash(
        user["password_hash"], password
    ):
        return jsonify({
            "success": False,
            "error": "Invalid email or password"
        }), 401

    # Prevent session fixation
    session.clear()

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_role"] = user["role"]

    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    }), 200


# ==========================================
# LOGOUT API
# ==========================================

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200


# ==========================================
# CURRENT USER API
# ==========================================

@app.route("/api/auth/me", methods=["GET"])
def api_current_user():

    return jsonify({
        "success": True,
        "user": {
            "id": session["user_id"],
            "name": session["user_name"],
            "role": session["user_role"]
        }
    }), 200

# -----------------------------------
# APPLICATION STARTUP
# -----------------------------------

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
import pytest
import sqlite3
import io
import app as businesspulse

from werkzeug.security import generate_password_hash


# -----------------------------------------
# TEST DATABASE FIXTURE
# -----------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):

    # Create a separate temporary database
    test_database = tmp_path / "test_businesspulse.db"

    # Replace the original database path
    monkeypatch.setattr(
        businesspulse,
        "DATABASE",
        str(test_database)
    )

    # Configure Flask for testing
    businesspulse.app.config.update(
        TESTING=True,
        SECRET_KEY="pytest-test-secret",

        # Disable CSRF for existing business-logic tests.
        # Dedicated security tests will enable it separately.
        WTF_CSRF_ENABLED=False
    )

    # Initialize the temporary database
    with businesspulse.app.app_context():
        businesspulse.init_db()

    # Create test client
    with businesspulse.app.test_client() as test_client:
        yield test_client


# -----------------------------------------
# HELPER FUNCTION
# -----------------------------------------

def register_test_user(client):

    return client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "testuser@example.com",
            "password": "TestPassword123"
        }
    )


# -----------------------------------------
# EXISTING BASIC TESTS
# -----------------------------------------

def test_login_page(client):

    response = client.get("/login")

    assert response.status_code == 200


def test_register_page(client):

    response = client.get("/register")

    assert response.status_code == 200


def test_dashboard_requires_login(client):

    response = client.get("/api/dashboard")

    assert response.status_code == 401


def test_current_user_requires_login(client):

    response = client.get("/api/auth/me")

    assert response.status_code == 401


# -----------------------------------------
# PHASE 5.2: REGISTRATION TESTS
# -----------------------------------------

def test_register_success_and_staff_role(client):

    response = register_test_user(client)

    assert response.status_code == 201
    assert response.json["success"] is True

    # Login to verify the newly registered user's role
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200
    assert login_response.json["user"]["role"] == "staff"


def test_register_rejects_invalid_email(client):

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "invalid-email",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 400


def test_register_rejects_short_password(client):

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "shortpass@example.com",
            "password": "123"
        }
    )

    assert response.status_code == 400


def test_duplicate_registration_rejected(client):

    first_response = register_test_user(client)

    second_response = register_test_user(client)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


# -----------------------------------------
# PHASE 5.2: LOGIN TESTS
# -----------------------------------------

def test_login_rejects_invalid_password(client):

    register_test_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "WrongPassword123"
        }
    )

    assert response.status_code == 401


def test_login_requires_credentials(client):

    response = client.post(
        "/api/auth/login",
        json={}
    )

    assert response.status_code == 400


# -----------------------------------------
# PHASE 5.2: LOGOUT TEST
# -----------------------------------------

def test_logout_clears_session(client):

    # First register a user
    register_test_user(client)

    # Login
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200

    # Logout
    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 200
    assert logout_response.json["success"] is True

    # Verify session is cleared
    current_user_response = client.get("/api/auth/me")

    assert current_user_response.status_code == 401


# -----------------------------------------
# PHASE 5.3: ROLE TEST HELPERS
# -----------------------------------------

def login_as_staff(client):

    register_response = register_test_user(client)

    assert register_response.status_code == 201

    return client.post(
        "/api/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "TestPassword123"
        }
    )


def create_admin_user():

    connection = sqlite3.connect(businesspulse.DATABASE)

    password_hash = generate_password_hash("AdminPassword123")

    connection.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """,
        (
            "Test Admin",
            "testadmin@example.com",
            password_hash,
            "admin"
        )
    )

    connection.commit()
    connection.close()


def login_as_admin(client):

    create_admin_user()

    return client.post(
        "/api/auth/login",
        json={
            "email": "testadmin@example.com",
            "password": "AdminPassword123"
        }
    )


# -----------------------------------------
# PHASE 5.3: STAFF PERMISSION TESTS
# -----------------------------------------

def test_staff_cannot_add_product(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/products",
        json={
            "name": "Unauthorized Product",
            "category": "Test",
            "price": 100,
            "stock": 10
        }
    )

    assert response.status_code == 403


def test_staff_cannot_edit_product(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.put(
        "/api/products/1",
        json={
            "name": "Unauthorized Edit",
            "category": "Test",
            "price": 200,
            "stock": 20
        }
    )

    assert response.status_code == 403


def test_staff_cannot_delete_product(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.delete("/api/products/1")

    assert response.status_code == 403


def test_staff_cannot_import_products(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.post("/api/import/products")

    assert response.status_code == 403


def test_staff_cannot_export_products(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get("/api/export/products")

    assert response.status_code == 403


def test_staff_cannot_export_sales(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get("/api/export/sales")

    assert response.status_code == 403


# -----------------------------------------
# PHASE 5.3: STAFF ALLOWED ACCESS
# -----------------------------------------

def test_staff_can_view_products(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get("/api/products")

    assert response.status_code == 200


def test_staff_can_view_sales(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get("/api/sales")

    assert response.status_code == 200


# -----------------------------------------
# PHASE 5.3: ADMIN ACCESS TESTS
# -----------------------------------------

def test_admin_can_view_products(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.get("/api/products")

    assert response.status_code == 200


def test_admin_can_export_products(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.get("/api/export/products")

    assert response.status_code == 200


def test_admin_can_export_sales(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.get("/api/export/sales")

    assert response.status_code == 200


# -----------------------------------------
# PHASE 5.4: PRODUCT AND SALES API TESTS
# -----------------------------------------

# Helper: Create a product directly in the test database

def create_test_product():

    connection = sqlite3.connect(businesspulse.DATABASE)

    cursor = connection.execute(
        """
        INSERT INTO products (name, category, price, stock)
        VALUES (?, ?, ?, ?)
        """,
        ("Phase 5 Test Product", "Testing", 25.0, 10)
    )

    product_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return product_id


# -----------------------------------------
# PRODUCT CREATION TESTS
# -----------------------------------------

def test_admin_can_add_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/products",
        json={
            "name": "New Test Product",
            "category": "Electronics",
            "price": 500,
            "stock": 20
        }
    )

    assert response.status_code == 201
    assert response.json["success"] is True
    assert "id" in response.json


def test_admin_cannot_add_product_with_missing_fields(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/products",
        json={
            "name": "",
            "category": "Electronics",
            "price": 500,
            "stock": 20
        }
    )

    assert response.status_code == 400
    assert response.json["success"] is False


def test_admin_cannot_add_product_with_invalid_price(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/products",
        json={
            "name": "Invalid Product",
            "category": "Testing",
            "price": -100,
            "stock": 10
        }
    )

    assert response.status_code == 400


# -----------------------------------------
# PRODUCT RETRIEVAL TEST
# -----------------------------------------

def test_admin_can_view_product_list(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.json["success"] is True
    assert "products" in response.json


# -----------------------------------------
# PRODUCT UPDATE TESTS
# -----------------------------------------

def test_admin_can_update_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    response = client.put(
        f"/api/products/{product_id}",
        json={
            "name": "Updated Test Product",
            "category": "Updated Category",
            "price": 750,
            "stock": 30
        }
    )

    assert response.status_code == 200
    assert response.json["success"] is True

    products_response = client.get("/api/products")

    updated_product = next(
        p for p in products_response.json["products"]
        if p["id"] == product_id
    )

    assert updated_product["name"] == "Updated Test Product"
    assert updated_product["price"] == 750
    assert updated_product["stock"] == 30


def test_admin_cannot_update_nonexistent_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.put(
        "/api/products/999999",
        json={
            "name": "Unknown Product",
            "category": "Testing",
            "price": 100,
            "stock": 10
        }
    )

    assert response.status_code == 404


# -----------------------------------------
# PRODUCT DELETE TESTS
# -----------------------------------------

def test_admin_can_delete_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    response = client.delete(
        f"/api/products/{product_id}"
    )

    assert response.status_code == 200
    assert response.json["success"] is True

    products_response = client.get("/api/products")

    product_ids = [
        p["id"] for p in products_response.json["products"]
    ]

    assert product_id not in product_ids


def test_admin_cannot_delete_nonexistent_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.delete("/api/products/999999")

    assert response.status_code == 404


# -----------------------------------------
# SALES CREATION TESTS
# -----------------------------------------

def test_staff_can_create_sale_and_reduce_stock(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    response = client.post(
        "/api/sales",
        json={
            "product_id": product_id,
            "quantity": 3
        }
    )

    assert response.status_code == 201
    assert response.json["success"] is True
    assert response.json["total"] == 75.0

    # Verify stock was reduced from 10 to 7

    connection = sqlite3.connect(businesspulse.DATABASE)

    product = connection.execute(
        "SELECT stock FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    connection.close()

    assert product[0] == 7


def test_sale_rejects_invalid_quantity(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    response = client.post(
        "/api/sales",
        json={
            "product_id": product_id,
            "quantity": 0
        }
    )

    assert response.status_code == 400


def test_sale_rejects_insufficient_stock(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    response = client.post(
        "/api/sales",
        json={
            "product_id": product_id,
            "quantity": 50
        }
    )

    assert response.status_code == 409

    # Verify stock was not changed

    connection = sqlite3.connect(businesspulse.DATABASE)

    product = connection.execute(
        "SELECT stock FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    sale_count = connection.execute(
        "SELECT COUNT(*) FROM sales WHERE product_id = ?",
        (product_id,)
    ).fetchone()[0]

    connection.close()

    assert product[0] == 10
    assert sale_count == 0


def test_sale_rejects_nonexistent_product(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/sales",
        json={
            "product_id": 999999,
            "quantity": 2
        }
    )

    assert response.status_code == 404


# =========================================
# PHASE 5.5: CSV IMPORT / EXPORT TESTING
# =========================================


# -----------------------------------------
# HELPER: CREATE CSV UPLOAD
# -----------------------------------------

def make_csv_upload(content, filename="products.csv"):

    return {
        "file": (
            io.BytesIO(content.encode("utf-8")),
            filename
        )
    }


# -----------------------------------------
# CSV IMPORT TESTS
# -----------------------------------------

def test_admin_can_import_valid_csv(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    csv_content = (
        "name,category,price,stock\n"
        "CSV Laptop,Electronics,50000,10\n"
        "CSV Mouse,Accessories,500,20\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 201
    assert response.json["success"] is True
    assert response.json["total_imported"] == 2

    # Verify imported products in database

    connection = sqlite3.connect(businesspulse.DATABASE)

    products = connection.execute(
        """
        SELECT name FROM products
        WHERE name IN (?, ?)
        """,
        ("CSV Laptop", "CSV Mouse")
    ).fetchall()

    connection.close()

    assert len(products) == 2


def test_import_rejects_missing_file(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/import/products"
    )

    assert response.status_code == 400
    assert response.json["success"] is False


def test_import_rejects_non_csv_file(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(
            "name,category,price,stock\nTest,Demo,100,10",
            "products.txt"
        ),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_import_rejects_missing_columns(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    csv_content = (
        "name,price,stock\n"
        "Test Product,100,10\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert response.json["success"] is False


def test_import_rejects_empty_csv(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(""),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_import_rejects_invalid_price_or_stock(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    csv_content = (
        "name,category,price,stock\n"
        "Invalid Product,Testing,invalid,10\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_import_rejects_duplicate_products_in_csv(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    csv_content = (
        "name,category,price,stock\n"
        "Duplicate Product,Testing,100,10\n"
        "Duplicate Product,Testing,200,20\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_import_rejects_existing_product(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    # Create an existing product

    product_id = create_test_product()

    csv_content = (
        "name,category,price,stock\n"
        "Phase 5 Test Product,Testing,100,10\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400

    # Verify existing product was not duplicated

    connection = sqlite3.connect(businesspulse.DATABASE)

    count = connection.execute(
        """
        SELECT COUNT(*) FROM products
        WHERE name = ?
        """,
        ("Phase 5 Test Product",)
    ).fetchone()[0]

    connection.close()

    assert count == 1


def test_failed_import_does_not_partially_insert_products(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    # Create one existing product

    create_test_product()

    csv_content = (
        "name,category,price,stock\n"
        "New CSV Product,Testing,100,10\n"
        "Phase 5 Test Product,Testing,200,20\n"
    )

    response = client.post(
        "/api/import/products",
        data=make_csv_upload(csv_content),
        content_type="multipart/form-data"
    )

    assert response.status_code == 400

    # Verify the new product was not inserted

    connection = sqlite3.connect(businesspulse.DATABASE)

    result = connection.execute(
        """
        SELECT COUNT(*) FROM products
        WHERE name = ?
        """,
        ("New CSV Product",)
    ).fetchone()[0]

    connection.close()

    assert result == 0


# -----------------------------------------
# CSV EXPORT: PRODUCTS
# -----------------------------------------

def test_admin_can_export_products_csv(client):

    login_response = login_as_admin(client)
    assert login_response.status_code == 200

    response = client.get(
        "/api/export/products"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"

    csv_content = response.data.decode("utf-8-sig")

    assert "id,name,category,price,stock,created_at" in csv_content
    assert "Laptop" in csv_content


# -----------------------------------------
# CSV EXPORT: SALES
# -----------------------------------------

def test_admin_can_export_sales_csv(client):

    # Login as staff to create a sale

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    sale_response = client.post(
        "/api/sales",
        json={
            "product_id": product_id,
            "quantity": 2
        }
    )

    assert sale_response.status_code == 201

    # Login as admin to export sales

    admin_response = login_as_admin(client)
    assert admin_response.status_code == 200

    response = client.get(
        "/api/export/sales"
    )

    assert response.status_code == 200
    assert response.mimetype == "text/csv"

    csv_content = response.data.decode("utf-8-sig")

    assert "product_name" in csv_content
    assert "Phase 5 Test Product" in csv_content


# =========================================
# PHASE 5.6: FINAL REGRESSION TESTING
# =========================================


# -----------------------------------------
# REGRESSION: API AUTHENTICATION
# -----------------------------------------

def test_all_business_apis_require_authentication(client):

    protected_requests = [
        ("GET", "/api/dashboard"),
        ("GET", "/api/products"),
        ("POST", "/api/products"),
        ("PUT", "/api/products/1"),
        ("DELETE", "/api/products/1"),
        ("GET", "/api/sales"),
        ("POST", "/api/sales"),
        ("GET", "/api/analytics/monthly"),
        ("GET", "/api/export/products"),
        ("GET", "/api/export/sales"),
        ("POST", "/api/import/products"),
    ]

    for method, endpoint in protected_requests:

        response = client.open(
            endpoint,
            method=method,
            json={}
        )

        assert response.status_code == 401, (
            f"{method} {endpoint} should require login, "
            f"but returned {response.status_code}"
        )


# -----------------------------------------
# REGRESSION: ROLE SECURITY
# -----------------------------------------

def test_user_cannot_register_as_admin(client):

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Unauthorized Admin",
            "email": "fakeadmin@example.com",
            "password": "TestPassword123",
            "role": "admin"
        }
    )

    assert response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "fakeadmin@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200
    assert login_response.json["user"]["role"] == "staff"


# -----------------------------------------
# REGRESSION: DASHBOARD API
# -----------------------------------------

def test_dashboard_returns_valid_statistics(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json["success"] is True

    required_fields = [
        "revenue",
        "orders",
        "units_sold",
        "products",
        "low_stock"
    ]

    for field in required_fields:
        assert field in response.json
        assert isinstance(
            response.json[field],
            (int, float)
        )


# -----------------------------------------
# REGRESSION: ANALYTICS API
# -----------------------------------------

def test_monthly_analytics_returns_valid_data(client):

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    response = client.get(
        "/api/analytics/monthly"
    )

    assert response.status_code == 200
    assert response.json["success"] is True

    assert "monthly" in response.json
    assert "top_products" in response.json

    assert isinstance(response.json["monthly"], list)
    assert isinstance(response.json["top_products"], list)


# -----------------------------------------
# REGRESSION: SALES HISTORY
# -----------------------------------------

def test_sales_history_preserved_after_product_deletion(client):

    # Login as staff and create a product sale

    login_response = login_as_staff(client)
    assert login_response.status_code == 200

    product_id = create_test_product()

    sale_response = client.post(
        "/api/sales",
        json={
            "product_id": product_id,
            "quantity": 2
        }
    )

    assert sale_response.status_code == 201

    # Login as admin and delete the product

    admin_response = login_as_admin(client)
    assert admin_response.status_code == 200

    delete_response = client.delete(
        f"/api/products/{product_id}"
    )

    assert delete_response.status_code == 200

    # Verify historical sales record remains

    connection = sqlite3.connect(businesspulse.DATABASE)
    connection.row_factory = sqlite3.Row

    sale = connection.execute(
        """
        SELECT product_id, product_name,
               quantity, unit_price, total
        FROM sales
        WHERE product_id IS NULL
          AND product_name = ?
        """,
        ("Phase 5 Test Product",)
    ).fetchone()

    connection.close()

    assert sale is not None
    assert sale["product_id"] is None
    assert sale["product_name"] == "Phase 5 Test Product"
    assert sale["quantity"] == 2
    assert sale["total"] == 50.0


# -----------------------------------------
# REGRESSION: SESSION COOKIE SECURITY
# -----------------------------------------

def test_session_cookie_has_security_attributes(client):

    register_response = register_test_user(client)
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert login_response.status_code == 200

    set_cookie = login_response.headers.get("Set-Cookie", "")

    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


# =========================================
# PHASE 6.2: CSRF SECURITY TESTS
# =========================================


# -----------------------------------------
# TEST: CSRF REJECTS REQUEST WITHOUT TOKEN
# -----------------------------------------

def test_csrf_rejects_request_without_token(client):

    # Enable CSRF protection for this test
    businesspulse.app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(
        "/api/auth/register",
        json={
            "name": "CSRF Test User",
            "email": "csrfuser@example.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 400


# -----------------------------------------
# TEST: CSRF ACCEPTS REQUEST WITH VALID TOKEN
# -----------------------------------------

def test_csrf_accepts_request_with_valid_token(client):

    # Enable CSRF protection for this test
    businesspulse.app.config["WTF_CSRF_ENABLED"] = True

    # First, obtain a CSRF token
    token_response = client.get("/api/auth/csrf")

    assert token_response.status_code == 200
    assert token_response.json["success"] is True

    csrf_token = token_response.json["csrf_token"]

    # Send registration request with the valid token
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Valid CSRF User",
            "email": "validcsrf@example.com",
            "password": "TestPassword123"
        },
        headers={
            "X-CSRFToken": csrf_token
        }
    )

    assert response.status_code == 201
    assert response.json["success"] is True

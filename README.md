# BusinessPulse - Sales & Inventory Intelligence Platform

BusinessPulse is a full-stack business management application
designed to manage products, inventory, sales transactions,
and business performance analytics.

## Features

- Interactive business analytics dashboard
- Product and inventory management
- Complete CRUD operations
- Sales transaction management
- Automatic inventory updates
- Monthly revenue analytics
- Top-selling product analysis
- RESTful API architecture
- SQLite database integration
- Responsive user interface

## Technology Stack

**Frontend**

- HTML5
- CSS3
- JavaScript
- Bootstrap 5
- Chart.js

**Backend**

- Python
- Flask
- REST APIs

**Database**

- SQLite

## Project Structure

```text
BusinessPulse/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── instance/
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Coderbarsan/BusinessPulse.git
cd BusinessPulse
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

### 3. Install dependencies

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Run the application

```powershell
.\.venv\Scripts\python.exe app.py
```

### 5. Open in browser

http://127.0.0.1:5000

The SQLite database is created automatically on first startup,
along with sample products and sales transactions.

## REST API Endpoints

| Method | Endpoint               | Description          |
| ------ | ---------------------- | -------------------- |
| GET    | /api/dashboard         | Dashboard statistics |
| GET    | /api/products          | List products        |
| POST   | /api/products          | Add product          |
| PUT    | /api/products/:id      | Update product       |
| DELETE | /api/products/:id      | Delete product       |
| GET    | /api/sales             | List sales           |
| POST   | /api/sales             | Record sale          |
| GET    | /api/analytics/monthly | Sales analytics      |

## Business Logic

- Product stock is updated automatically after a sale.
- Transactions are validated before database insertion.
- Sales exceeding available inventory are rejected.
- Historical sales retain the product name and sale price.

## Future Improvements

- User authentication and role-based access
- CSV import and export
- PDF sales reports
- Advanced filtering and pagination
- Cloud database integration
- Automated testing

## Author

Barsan Sahu

GitHub: https://github.com/Coderbarsan

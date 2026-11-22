const API = "/api";

let revenueChart = null;
let productsChart = null;
let allProducts = [];

// --------------------------------
// HELPER FUNCTIONS
// --------------------------------

const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value) || 0);

const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(API + endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Something went wrong");
  }

  return data;
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");

  toast.textContent = message;
  toast.className = "toast-message show";

  if (isError) {
    toast.classList.add("error");
  }

  setTimeout(() => {
    toast.classList.remove("show", "error");
  }, 3000);
}

function showPage(page) {
  document.querySelectorAll(".page-section").forEach((section) => {
    section.classList.remove("active");
  });

  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.remove("active");
  });

  document.getElementById(page + "-page").classList.add("active");

  document.querySelector(`[data-page="${page}"]`)?.classList.add("active");

  const titles = {
    dashboard: "Dashboard",
    products: "Inventory Management",
    sales: "Sales Management",
  };

  document.getElementById("page-title").textContent = titles[page];

  if (page === "dashboard") loadDashboard();
  if (page === "products") loadProducts();
  if (page === "sales") loadSales();
}

// --------------------------------
// NAVIGATION
// --------------------------------

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    showPage(link.dataset.page);
  });
});

// --------------------------------
// DASHBOARD
// --------------------------------

async function loadDashboard() {
  try {
    const data = await apiRequest("/dashboard");

    document.getElementById("total-revenue").textContent = money(data.revenue);

    document.getElementById("total-orders").textContent = data.orders;

    document.getElementById("total-products").textContent = data.products;

    document.getElementById("low-stock").textContent = data.low_stock;

    await Promise.all([loadAnalytics(), loadRecentSales()]);
  } catch (error) {
    showToast(error.message, true);
  }
}

// --------------------------------
// ANALYTICS CHARTS
// --------------------------------

async function loadAnalytics() {
  try {
    const data = await apiRequest("/analytics/monthly");

    const monthlyLabels = [];
    const monthlyRevenue = [];

    // Include months with zero revenue.
    const now = new Date();

    for (let i = 5; i >= 0; i--) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);

      const key =
        date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0");

      monthlyLabels.push(date.toLocaleString("en-IN", { month: "short" }));

      const match = data.monthly.find((item) => item.month === key);

      monthlyRevenue.push(match ? Number(match.revenue) : 0);
    }

    if (revenueChart) revenueChart.destroy();

    revenueChart = new Chart(document.getElementById("revenueChart"), {
      type: "line",
      data: {
        labels: monthlyLabels,
        datasets: [
          {
            label: "Revenue",
            data: monthlyRevenue,
            borderColor: "#635bff",
            backgroundColor: "rgba(99,91,255,0.12)",
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: (value) => "₹" + Number(value).toLocaleString("en-IN"),
            },
          },
        },
      },
    });

    const labels = data.top_products.map((item) => item.product_name);

    const quantities = data.top_products.map((item) => Number(item.quantity));

    if (productsChart) productsChart.destroy();

    productsChart = new Chart(document.getElementById("productsChart"), {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data: quantities,
            backgroundColor: [
              "#635bff",
              "#24b78b",
              "#ffb648",
              "#ed6a78",
              "#39a4db",
            ],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });
  } catch (error) {
    showToast(error.message, true);
  }
}

// --------------------------------
// PRODUCT MANAGEMENT
// --------------------------------

async function loadProducts() {
  try {
    const data = await apiRequest("/products");

    allProducts = data.products;

    renderProducts(allProducts);
    updateProductOptions();
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderProducts(products) {
  const table = document.getElementById("products-table");

  if (!products.length) {
    table.innerHTML = `<tr><td colspan="6" class="empty-row">No products found</td></tr>`;
    return;
  }

  table.innerHTML = products
    .map((product) => {
      const stockClass =
        product.stock === 0
          ? "stock-out"
          : product.stock <= 5
            ? "stock-low"
            : "stock-good";

      const stockLabel =
        product.stock === 0
          ? "Out of stock"
          : product.stock <= 5
            ? "Low stock"
            : "In stock";

      return `
            <tr>
                <td>#${product.id}</td>
                <td><strong>${escapeHTML(product.name)}</strong></td>
                <td>${escapeHTML(product.category)}</td>
                <td>${money(product.price)}</td>
                <td>
                    <span class="stock-badge ${stockClass}">
                        ${product.stock} - ${stockLabel}
                    </span>
                </td>
                <td>
                    <button class="action-btn"
                        data-action="edit"
                        data-id="${product.id}"
                        title="Edit">
                        <i class="fa-solid fa-pen"></i>
                    </button>

                    <button class="action-btn delete-btn"
                        data-action="delete"
                        data-id="${product.id}"
                        title="Delete">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    })
    .join("");
}

// ADD / UPDATE PRODUCT

document
  .getElementById("product-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();

    const id = document.getElementById("product-id").value;

    const product = {
      name: document.getElementById("product-name").value.trim(),
      category: document.getElementById("product-category").value.trim(),
      price: document.getElementById("product-price").value,
      stock: document.getElementById("product-stock").value,
    };

    try {
      const endpoint = id ? `/products/${id}` : "/products";

      const method = id ? "PUT" : "POST";

      const result = await apiRequest(endpoint, {
        method,
        body: JSON.stringify(product),
      });

      showToast(result.message);

      resetProductForm();

      await loadProducts();
      await loadDashboard();
    } catch (error) {
      showToast(error.message, true);
    }
  });

// EDIT / DELETE PRODUCT

document
  .getElementById("products-table")
  .addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");

    if (!button) return;

    const id = Number(button.dataset.id);
    const action = button.dataset.action;

    const product = allProducts.find((item) => item.id === id);

    if (!product) return;

    if (action === "edit") {
      document.getElementById("product-id").value = product.id;
      document.getElementById("product-name").value = product.name;
      document.getElementById("product-category").value = product.category;
      document.getElementById("product-price").value = product.price;
      document.getElementById("product-stock").value = product.stock;

      document.getElementById("product-form-title").textContent =
        "Update Product";

      document.getElementById("product-submit").textContent = "Update Product";

      document.getElementById("cancel-edit").hidden = false;

      document.getElementById("product-form").scrollIntoView({
        behavior: "smooth",
      });
    }

    if (action === "delete") {
      if (!confirm(`Delete ${product.name}?`)) return;

      try {
        const result = await apiRequest(`/products/${id}`, {
          method: "DELETE",
        });

        showToast(result.message);

        resetProductForm();

        await loadProducts();
        await loadDashboard();
      } catch (error) {
        showToast(error.message, true);
      }
    }
  });

function resetProductForm() {
  document.getElementById("product-form").reset();
  document.getElementById("product-id").value = "";

  document.getElementById("product-form-title").textContent = "Add New Product";

  document.getElementById("product-submit").textContent = "Add Product";

  document.getElementById("cancel-edit").hidden = true;
}

document
  .getElementById("cancel-edit")
  .addEventListener("click", resetProductForm);

// PRODUCT SEARCH

document.getElementById("product-search").addEventListener("input", (event) => {
  const query = event.target.value.toLowerCase();

  const filtered = allProducts.filter(
    (product) =>
      product.name.toLowerCase().includes(query) ||
      product.category.toLowerCase().includes(query),
  );

  renderProducts(filtered);
});

// --------------------------------
// SALES MANAGEMENT
// --------------------------------

function updateProductOptions() {
  const select = document.getElementById("sale-product");

  const currentValue = select.value;

  select.innerHTML = '<option value="">Choose a product</option>';

  allProducts
    .filter((product) => product.stock > 0)
    .forEach((product) => {
      const option = document.createElement("option");

      option.value = product.id;
      option.textContent = `${product.name} (${product.stock} available)`;

      select.appendChild(option);
    });

  if ([...select.options].some((option) => option.value === currentValue)) {
    select.value = currentValue;
  }
}

// RECORD SALE

document
  .getElementById("sales-form")
  .addEventListener("submit", async (event) => {
    event.preventDefault();

    const sale = {
      product_id: document.getElementById("sale-product").value,
      quantity: document.getElementById("sale-quantity").value,
    };

    try {
      const result = await apiRequest("/sales", {
        method: "POST",
        body: JSON.stringify(sale),
      });

      showToast(`Sale recorded! Total: ${money(result.total)}`);

      document.getElementById("sales-form").reset();

      await loadProducts();
      await loadSales();
      await loadDashboard();
    } catch (error) {
      showToast(error.message, true);
    }
  });

// SALES HISTORY

async function loadSales() {
  try {
    const data = await apiRequest("/sales");

    const table = document.getElementById("sales-table");

    if (!data.sales.length) {
      table.innerHTML = `<tr><td colspan="6" class="empty-row">No sales recorded</td></tr>`;
      return;
    }

    table.innerHTML = data.sales
      .map(
        (sale) => `
            <tr>
                <td>#${sale.id}</td>
                <td>${escapeHTML(sale.product_name)}</td>
                <td>${sale.quantity}</td>
                <td>${money(sale.unit_price)}</td>
                <td><strong>${money(sale.total)}</strong></td>
                <td>${escapeHTML(sale.created_at)}</td>
            </tr>
        `,
      )
      .join("");

    updateProductOptions();
  } catch (error) {
    showToast(error.message, true);
  }
}

// RECENT SALES ON DASHBOARD

async function loadRecentSales() {
  try {
    const data = await apiRequest("/sales");

    const recent = data.sales.slice(0, 5);

    const table = document.getElementById("recent-sales");

    if (!recent.length) {
      table.innerHTML = `<tr><td colspan="5" class="empty-row">No sales yet</td></tr>`;
      return;
    }

    table.innerHTML = recent
      .map(
        (sale) => `
            <tr>
                <td>#${sale.id}</td>
                <td>${escapeHTML(sale.product_name)}</td>
                <td>${sale.quantity}</td>
                <td><strong>${money(sale.total)}</strong></td>
                <td>${escapeHTML(sale.created_at)}</td>
            </tr>
        `,
      )
      .join("");
  } catch (error) {
    showToast(error.message, true);
  }
}

// --------------------------------
// INITIALIZE APPLICATION
// --------------------------------

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();
  loadProducts();
});

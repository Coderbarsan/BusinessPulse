// ==========================================
// BUSINESSPULSE AUTHENTICATION
// ==========================================

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

const messageBox = document.getElementById("message");

// ==========================================
// DISPLAY MESSAGE
// ==========================================

function showMessage(message, type = "danger") {
  messageBox.textContent = message;

  messageBox.className = `alert alert-${type}`;
}

// ==========================================
// CSRF TOKEN HELPER
// ==========================================

async function getCsrfToken() {
  const response = await fetch("/api/auth/csrf", {
    method: "GET",
    credentials: "same-origin",
  });

  const data = await response.json();

  if (!response.ok || !data.success || !data.csrf_token) {
    throw new Error("Unable to obtain CSRF token.");
  }

  return data.csrf_token;
}

// ==========================================
// LOGIN
// ==========================================

if (loginForm) {
  loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    const button = document.getElementById("loginButton");

    button.disabled = true;
    button.textContent = "Logging in...";

    try {
      // Get CSRF token before login
      const csrfToken = await getCsrfToken();

      const response = await fetch("/api/auth/login", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },

        credentials: "same-origin",

        body: JSON.stringify({
          email: email,
          password: password,
        }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        showMessage(result.error || "Login failed. Please try again.");
        return;
      }

      showMessage("Login successful! Redirecting...", "success");

      window.location.href = "/";
    } catch (error) {
      console.error("Login error:", error);

      showMessage(error.message || "Unable to connect to the server.");
    } finally {
      button.disabled = false;
      button.textContent = "Login";
    }
  });
}

// ==========================================
// REGISTRATION
// ==========================================

if (registerForm) {
  registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    const button = document.getElementById("registerButton");

    button.disabled = true;
    button.textContent = "Creating account...";

    try {
      // Get CSRF token before registration
      const csrfToken = await getCsrfToken();

      const response = await fetch("/api/auth/register", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },

        credentials: "same-origin",

        body: JSON.stringify({
          name: name,
          email: email,
          password: password,
        }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        showMessage(result.error || "Registration failed. Please try again.");
        return;
      }

      showMessage(
        "Registration successful! Redirecting to login...",
        "success",
      );

      registerForm.reset();

      setTimeout(() => {
        window.location.href = "/login";
      }, 1500);
    } catch (error) {
      console.error("Registration error:", error);

      showMessage(error.message || "Unable to connect to the server.");
    } finally {
      button.disabled = false;
      button.textContent = "Create Account";
    }
  });
}

// ==========================================
// SHOW / HIDE PASSWORD
// ==========================================

const passwordToggleButtons = document.querySelectorAll(".toggle-password");

passwordToggleButtons.forEach(function (button) {
  button.addEventListener("click", function () {
    const targetId = button.getAttribute("data-target");

    const passwordInput = document.getElementById(targetId);

    const icon = button.querySelector("i");

    if (!passwordInput || !icon) {
      return;
    }

    if (passwordInput.type === "password") {
      // Show password
      passwordInput.type = "text";

      icon.classList.remove("fa-eye");
      icon.classList.add("fa-eye-slash");

      button.setAttribute("aria-label", "Hide password");
      button.setAttribute("aria-pressed", "true");
    } else {
      // Hide password
      passwordInput.type = "password";

      icon.classList.remove("fa-eye-slash");
      icon.classList.add("fa-eye");

      button.setAttribute("aria-label", "Show password");
      button.setAttribute("aria-pressed", "false");
    }
  });
});

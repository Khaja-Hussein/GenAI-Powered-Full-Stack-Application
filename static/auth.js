(() => {
    const authScreen = document.getElementById("auth-screen");
    const appShell = document.getElementById("app-shell");
    const loginForm = document.getElementById("login-form");
    const signupForm = document.getElementById("signup-form");
    const authError = document.getElementById("auth-error");
    const authTitle = document.getElementById("auth-title");
    const authSubtitle = document.getElementById("auth-subtitle");
    const authSwitchText = document.getElementById("auth-switch-text");
    const loginSwitchText = document.getElementById("login-switch-text");
    const loggedInUser = document.getElementById("logged-in-user");
    const logoutButton = document.getElementById("logout-button");

    let appScriptLoaded = false;

    function showError(message) {
        authError.textContent = message || "";
        authError.hidden = !message;
    }

    function showLogin() {
        showError("");
        loginForm.hidden = false;
        signupForm.hidden = true;
        authTitle.textContent = "Welcome back";
        authSubtitle.textContent = "Log in to your private AI workspace.";
        authSwitchText.hidden = false;
        loginSwitchText.hidden = true;
    }

    function showSignup() {
        showError("");
        loginForm.hidden = true;
        signupForm.hidden = false;
        authTitle.textContent = "Create your account";
        authSubtitle.textContent = "Your chats and AI memories will be private to your account.";
        authSwitchText.hidden = true;
        loginSwitchText.hidden = false;
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify(payload)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Request failed. Please try again.");
        return data;
    }

    async function enterWorkspace(user) {
        authScreen.hidden = true;
        appShell.hidden = false;
        loggedInUser.textContent = `Hi, ${user.username}`;
        showError("");
        if (!appScriptLoaded) {
            appScriptLoaded = true;
            const script = document.createElement("script");
            script.src = "/static/script.js";
            script.onerror = () => alert("Could not load the app script. Refresh the page and try again.");
            document.body.appendChild(script);
        }
    }

    document.getElementById("show-signup").addEventListener("click", showSignup);
    document.getElementById("show-login").addEventListener("click", showLogin);

    // Toggle password visibility on login and signup forms.
    document.querySelectorAll(".password-toggle[data-password-target]").forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const input = document.getElementById(toggle.dataset.passwordTarget);
            if (!input) return;

            const shouldShow = input.type === "password";
            input.type = shouldShow ? "text" : "password";
            toggle.textContent = shouldShow ? "🙈" : "👁️";
            toggle.setAttribute("aria-label", shouldShow ? "Hide password" : "Show password");
            toggle.setAttribute("title", shouldShow ? "Hide password" : "Show password");
        });
    });

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = loginForm.querySelector('button[type="submit"]');
        button.disabled = true;
        showError("");
        try {
            const data = await postJson("/api/auth/login", {
                email: document.getElementById("login-email").value,
                password: document.getElementById("login-password").value
            });
            await enterWorkspace(data.user);
        } catch (error) {
            showError(error.message);
        } finally {
            button.disabled = false;
        }
    });

    signupForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = signupForm.querySelector('button[type="submit"]');
        button.disabled = true;
        showError("");
        try {
            const data = await postJson("/api/auth/signup", {
                username: document.getElementById("signup-username").value,
                email: document.getElementById("signup-email").value,
                password: document.getElementById("signup-password").value
            });
            await enterWorkspace(data.user);
        } catch (error) {
            showError(error.message);
        } finally {
            button.disabled = false;
        }
    });

    logoutButton.addEventListener("click", async () => {
        logoutButton.disabled = true;
        try {
            await postJson("/api/auth/logout", {});
            window.location.reload();
        } catch (error) {
            alert(error.message);
            logoutButton.disabled = false;
        }
    });

    async function initializeAuth() {
        authScreen.hidden = false;
        appShell.hidden = true;
        try {
            const response = await fetch("/api/auth/me", { credentials: "same-origin" });
            const data = await response.json();
            if (data.authenticated && data.user) {
                await enterWorkspace(data.user);
            } else {
                showLogin();
            }
        } catch (_error) {
            showLogin();
            showError("Could not connect to the server. Make sure Flask is running, then refresh.");
        }
    }

    initializeAuth();
})();

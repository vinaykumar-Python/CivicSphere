"use strict";

const API_BASE_URL = "";
const TOKEN_KEY = "civiccare_access_token";

document.addEventListener("DOMContentLoaded", () => {
    const loginTab = document.getElementById("login-tab");
    const registerTab = document.getElementById("register-tab");
    const loginForm = document.getElementById("login-panel");
    const registerForm = document.getElementById("register-panel");
    const verificationForm = document.getElementById("verify-email-panel");
    const tabs = document.querySelector(".auth-tabs");
    const messageBox = document.getElementById("auth-message");

    function showMessage(message, type = "info", target = messageBox) {
        if (!target) return;

        target.textContent = message;
        target.className = "auth-message";

        if (type === "error") {
            target.classList.add("error");
        } else if (type === "success") {
            target.classList.add("success");
        }

        target.hidden = false;
    }

    function clearMessage(target = messageBox) {
        if (!target) return;

        target.hidden = true;
        target.textContent = "";
        target.className = "auth-message";
    }

    function switchTab(showLogin) {
        if (!loginForm || !registerForm || !loginTab || !registerTab) return;

        if (verificationForm) verificationForm.hidden = true;
        if (tabs) tabs.hidden = false;
        loginForm.hidden = !showLogin;
        registerForm.hidden = showLogin;

        loginTab.classList.toggle("active", showLogin);
        registerTab.classList.toggle("active", !showLogin);

        loginTab.setAttribute("aria-selected", String(showLogin));
        registerTab.setAttribute("aria-selected", String(!showLogin));

        clearMessage();
    }

    function showVerification(email) {
        if (!verificationForm) return;

        loginForm.hidden = true;
        registerForm.hidden = true;
        verificationForm.hidden = false;
        if (tabs) tabs.hidden = true;
        document.getElementById("verification-email").value = email;
        document.getElementById("verification-code").value = "";
        clearMessage();
        document.getElementById("verification-code").focus();
    }

    loginTab?.addEventListener("click", () => switchTab(true));
    registerTab?.addEventListener("click", () => switchTab(false));

    async function readResponse(response) {
        const text = await response.text();

        if (!text) return {};

        try {
            return JSON.parse(text);
        } catch {
            return { detail: text };
        }
    }

    async function authenticate(email, password, expectedRole) {
        const formData = new URLSearchParams();
        formData.append("username", email);
        formData.append("password", password);

        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData.toString()
        });

        const data = await readResponse(response);

        if (!response.ok) {
            if (
                response.status === 403 &&
                String(data.detail || "").toLowerCase().includes("verify your email")
            ) {
                if (expectedRole === "citizen") {
                    showVerification(email);
                    throw new Error("Please verify your email address to continue.");
                }

                throw new Error(
                    "Your authority account needs email verification. Contact your department administrator."
                );
            }
            throw new Error(response.status === 401
                ? "Email or password is incorrect. Please try again."
                : "Sign-in is temporarily unavailable. Please try again later.");
        }

        if (!data.access_token) {
            throw new Error("Sign-in is temporarily unavailable. Please try again later.");
        }

        // Read the authenticated user's role from the protected profile API.
        const profileResponse = await fetch(`${API_BASE_URL}/api/users/me`, {
            headers: {
                Authorization: `Bearer ${data.access_token}`
            }
        });

        const profile = await readResponse(profileResponse);

        if (!profileResponse.ok) {
            throw new Error("We couldn't verify your account. Please try again.");
        }

        if (!["citizen", "authority"].includes(profile.role)) {
            throw new Error("We couldn't find a matching CivicCare portal for this account.");
        }

        return {
            token: data.access_token,
            profile
        };
    }

    function setupLoginForm(form, expectedRole) {
        if (!form) return;

        const formMessageBox = expectedRole === "authority"
            ? document.getElementById("authority-auth-message")
            : messageBox;

        form.addEventListener("submit", async event => {
            event.preventDefault();
            clearMessage(formMessageBox);

            const emailInput = form.querySelector('input[type="email"]');
            const passwordInput = form.querySelector('input[type="password"]');

            const email = emailInput?.value.trim() || "";
            const password = passwordInput?.value || "";

            if (!email || !password) {
                showMessage(
                    "Please enter your email address and password.",
                    "error",
                    formMessageBox
                );
                return;
            }

            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = submitButton?.textContent || "Sign in";

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = "Signing in...";
            }

            try {
                const { token, profile } = await authenticate(
                    email,
                    password,
                    expectedRole
                );

                if (profile.role !== expectedRole) {
                    throw new Error(
                        expectedRole === "citizen"
                            ? "This is an authority account. Please use the authority portal."
                            : "This is a citizen account. Please use the citizen portal."
                    );
                }

                sessionStorage.setItem(TOKEN_KEY, token);

                showMessage(
                    "Sign-in successful. Opening your dashboard...",
                    "success",
                    formMessageBox
                );

                const destination = expectedRole === "authority"
                    ? "authority-dashboard.html"
                    : "citizen-dashboard.html";

                window.location.replace(destination);

            } catch (error) {
                console.error("Login error:", error);

                const errorMessage = String(error?.message || "");
                const message = errorMessage.includes("Please use the")
                    || errorMessage.includes("Please verify your email")
                    || errorMessage.includes("needs email verification")
                    ? errorMessage
                    : "We couldn't sign you in. Check your details and try again.";

                showMessage(
                    message,
                    "error",
                    formMessageBox
                );
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText;
                }
            }
        });
    }

    // Citizen registration
    if (registerForm) {
        registerForm.addEventListener("submit", async event => {
            event.preventDefault();
            clearMessage();

            const fullName = document.getElementById("register-name")?.value.trim() || "";
            const email = document.getElementById("register-email")?.value.trim() || "";
            const password = document.getElementById("register-password")?.value || "";

            if (!fullName || !email || !password) {
                showMessage("Please complete all required fields.", "error");
                return;
            }

            if (password.length < 8) {
                showMessage(
                    "Your password must contain at least 8 characters.",
                    "error"
                );
                return;
            }

            const submitButton = registerForm.querySelector('button[type="submit"]');
            const originalText = submitButton?.textContent || "Create account";

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = "Creating account...";
            }

            try {
                const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        full_name: fullName,
                        email,
                        password
                    })
                });

                const data = await readResponse(response);
                if (!response.ok) {
                    if (response.status === 503 && data.detail?.includes(
                        "account was created"
                    )) {
                        showVerification(email);
                    }
                    throw new Error(
                        data.detail ||
                        "Your account couldn't be created. Please review your details and try again."
                    );
                }

                registerForm.reset();
                showVerification(email);
                showMessage(data.message, "success");

            } catch (error) {
                console.error("Registration error:", error);

                showMessage(
                    error.message ||
                    "Your account couldn't be created. Please review your details and try again.",
                    "error"
                );
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText;
                }
            }
        });
    }

    if (verificationForm) {
        verificationForm.addEventListener("submit", async event => {
            event.preventDefault();
            clearMessage();

            const email = document.getElementById("verification-email").value.trim();
            const code = document.getElementById("verification-code").value.trim();
            const submitButton = verificationForm.querySelector('button[type="submit"]');

            if (!email || !/^\d{6}$/.test(code)) {
                showMessage("Enter the email address and six-digit code.", "error");
                return;
            }

            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = "Verifying...";
            }

            try {
                const response = await fetch(`${API_BASE_URL}/api/auth/verify-email`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, code })
                });
                const data = await readResponse(response);

                if (!response.ok) {
                    throw new Error(data.detail || "Email verification failed.");
                }

                const loginEmail = document.getElementById("login-email");
                if (loginEmail) loginEmail.value = email;
                switchTab(true);
                showMessage(data.message, "success");
            } catch (error) {
                showMessage(error.message || "Email verification failed.", "error");
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = "Verify email →";
                }
            }
        });
    }

    document.getElementById("resend-verification")?.addEventListener(
        "click",
        async () => {
            clearMessage();
            const email = document.getElementById("verification-email").value.trim();

            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/auth/resend-verification`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email })
                    }
                );
                const data = await readResponse(response);

                if (!response.ok) {
                    throw new Error(data.detail || "A new code could not be sent.");
                }

                showMessage(data.message, "success");
            } catch (error) {
                showMessage(error.message || "A new code could not be sent.", "error");
            }
        }
    );

    // Citizen login
    setupLoginForm(loginForm, "citizen");

    // Authority login: activated when the authority form is added to index.html.
    const authorityLoginForm = document.getElementById("authority-login-panel");
    setupLoginForm(authorityLoginForm, "authority");

    // Footer year
    const yearElement = document.querySelector(".footer > span");

    if (yearElement) {
        yearElement.textContent =
            `© ${new Date().getFullYear()} CivicCare AI · Built for better communities`;
    }

    console.info("CivicCare AI authentication initialized.");
});

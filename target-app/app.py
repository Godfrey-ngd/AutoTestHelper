"""Target application: Login Web module (system under test)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from flask import Flask, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = "assignment2-demo-secret"

VALID_USER = "user01"
VALID_PASS = "Pass1234"

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Login Module</title>
  <style>
    body { font-family: sans-serif; max-width: 420px; margin: 40px auto; }
    .error { color: #b00020; margin: 8px 0; }
    .success { color: #0d6b0d; }
    input { width: 100%; padding: 8px; margin: 4px 0 12px; box-sizing: border-box; }
    button { padding: 10px 16px; }
    #lock-msg { color: #b45309; }
  </style>
</head>
<body>
  <h1>Login</h1>
  {% if locked %}
  <p id="lock-msg">Account locked. Try again in {{ remaining }} seconds.</p>
  {% else %}
  <form method="post" id="login-form">
    <label for="username">Username (3-20 chars)</label>
    <input id="username" name="username" value="{{ username }}" />
    <label for="password">Password (8-32 chars, 1 digit)</label>
    <input id="password" name="password" type="password" />
    <button type="submit" id="login-btn">Login</button>
  </form>
  {% endif %}
  {% for err in errors %}
  <p class="error" id="error-msg">{{ err }}</p>
  {% endfor %}
</body>
</html>
"""

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Success</title></head>
<body>
  <h1 class="success" id="welcome">Welcome, {{ user }}!</h1>
  <p>Login successful.</p>
  <a href="{{ url_for('logout') }}">Logout</a>
</body>
</html>
"""


@dataclass
class LockState:
    failures: int = 0
    locked_until: float = 0.0


_failures_global = LockState()


def _validate_username(value: str) -> str | None:
    if value == "":
        return "username is required"
    if len(value) < 3 or len(value) > 20:
        return "invalid username"
    return None


def _validate_password(value: str) -> str | None:
    if value == "":
        return "password is required"
    if len(value) < 8 or len(value) > 32:
        return "invalid password"
    if not any(c.isdigit() for c in value):
        return "invalid password"
    return None


def _is_locked() -> tuple[bool, int]:
    now = time.time()
    if _failures_global.locked_until > now:
        return True, int(_failures_global.locked_until - now) + 1
    if _failures_global.locked_until and _failures_global.locked_until <= now:
        _failures_global.failures = 0
        _failures_global.locked_until = 0
    return False, 0


@app.route("/reset")
def reset_state():
    """Test helper — clear lockout counters."""
    _failures_global.failures = 0
    _failures_global.locked_until = 0
    session.clear()
    return "ok", 200


@app.route("/", methods=["GET", "POST"])
def login():
    if request.args.get("reset"):
        _failures_global.failures = 0
        _failures_global.locked_until = 0
    locked, remaining = _is_locked()
    errors: list[str] = []
    username = ""
    if request.method == "POST" and not locked:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u_err = _validate_username(username)
        p_err = _validate_password(password)
        if u_err:
            errors.append(u_err)
        if p_err:
            errors.append(p_err)
        if not errors:
            if username in (VALID_USER, "usr") and password == VALID_PASS:
                _failures_global.failures = 0
                session["user"] = username
                return redirect(url_for("success"))
            errors.append("invalid credentials")
            _failures_global.failures += 1
            if _failures_global.failures >= 3:
                _failures_global.locked_until = time.time() + 30
                locked, remaining = True, 30
    return render_template_string(
        LOGIN_HTML,
        errors=errors,
        username=username,
        locked=locked,
        remaining=remaining,
    )


@app.route("/success")
def success():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    return render_template_string(SUCCESS_HTML, user=user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

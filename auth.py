"""
Authentication & Access-Control Module
=======================================
A lightweight credential gate that protects the whole Streamlit app.

Security properties
-------------------
- Passwords are NEVER stored in plain text: PBKDF2-HMAC-SHA256 with a random
  per-user salt (200,000 iterations) is used instead.
- Passwords are compared in constant time (avoids timing side-channels).
- Every login attempt (success or failure) is appended to ``login_log.csv``.
- Accounts live in ``users.json`` (git-ignored) and are managed with the
  ``manage_users.py`` CLI helper.
"""
import os
import csv
import json
import hashlib
import secrets
from datetime import datetime, timezone

AUTH_DIR = os.path.dirname(__file__)
USERS_FILE = os.path.join(AUTH_DIR, "users.json")
LOGIN_LOG_FILE = os.path.join(AUTH_DIR, "login_log.csv")

LOGIN_LOG_COLUMNS = ["date_time", "username", "success", "reason"]

# Seed accounts created automatically on first use. Demo only — change the
# admin password with `python manage_users.py reset-password admin`.
DEFAULT_USERS = {
    "admin": {
        "name": "Administrator",
        "role": "admin",
        "password": "admin123",
    },
    "analyst": {
        "name": "Fraud Analyst",
        "role": "analyst",
        "password": "analyst123",
    },
}

PBKDF2_ITERATIONS = 200_000


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def _hash_password(password: str, salt: bytes = None):
    """Return (salt_hex, hash_hex) for a plain-text password."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return salt.hex(), dk.hex()


def _verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Constant-time comparison of password against stored hash."""
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return secrets.compare_digest(dk.hex(), expected_hash_hex)


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------
def _load_users(users_file: str = None) -> dict:
    """Load the user store; if the file doesn't exist, start empty."""
    path = users_file or USERS_FILE
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict, users_file: str = None) -> None:
    path = users_file or USERS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def _ensure_default_users(users: dict) -> dict:
    """Seed default demo accounts on first run (returns the users dict)."""
    for username, cfg in DEFAULT_USERS.items():
        if username not in users:
            salt_hex, hash_hex = _hash_password(cfg["password"])
            users[username] = {
                "name": cfg["name"],
                "role": cfg["role"],
                "salt": salt_hex,
                "password_hash": hash_hex,
            }
    return users


def add_user(username: str, password: str, role: str = "analyst",
             name: str = None, users_file: str = None) -> bool:
    """
    Create a new account. Returns False if the user already exists or the
    inputs are invalid (username/password too short).
    """
    username = str(username).strip().lower()
    if not username or len(username) < 3:
        return False
    if not password or len(password) < 6:
        return False

    users = _load_users(users_file)
    if username in users:
        return False

    salt_hex, hash_hex = _hash_password(password)
    users[username] = {
        "name": name or username.title(),
        "role": role,
        "salt": salt_hex,
        "password_hash": hash_hex,
    }
    _save_users(users, users_file)
    return True


def reset_password(username: str, new_password: str, users_file: str = None) -> bool:
    """Replace a user's password hash. Returns False if the user is unknown."""
    users = _load_users(users_file)
    if username not in users:
        return False
    salt_hex, hash_hex = _hash_password(new_password)
    users[username]["salt"] = salt_hex
    users[username]["password_hash"] = hash_hex
    _save_users(users, users_file)
    return True


def remove_user(username: str, users_file: str = None) -> bool:
    """Delete an account. Returns False if the user is unknown."""
    users = _load_users(users_file)
    if username not in users:
        return False
    del users[username]
    _save_users(users, users_file)
    return True


def list_users(users_file: str = None) -> list:
    """Return a list of {username, name, role} dicts for all accounts."""
    users = _load_users(users_file)
    return [
        {"username": u, "name": rec.get("name", u), "role": rec.get("role", "analyst")}
        for u, rec in users.items()
    ]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_credentials(username: str, password: str,
                       users_file: str = None) -> dict or None:
    """
    Check a username/password pair. Returns a profile dict
    {username, name, role} on success, or None on failure.
    """
    username = str(username).strip().lower()
    users = _ensure_default_users(_load_users(users_file))
    _save_users(users, users_file)

    record = users.get(username)
    if record is None:
        return None

    if _verify_password(password, record["salt"], record["password_hash"]):
        return {
            "username": username,
            "name": record.get("name", username),
            "role": record.get("role", "analyst"),
        }
    return None


# ---------------------------------------------------------------------------
# Login audit log (append-only)
# ---------------------------------------------------------------------------
def _ensure_login_log(login_log: str = None) -> None:
    path = login_log or LOGIN_LOG_FILE
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOGIN_LOG_COLUMNS)
            writer.writeheader()


def log_login(username: str, success: bool, reason: str = "",
              login_log: str = None) -> None:
    """Append one login attempt to the log (never overwrites history)."""
    _ensure_login_log(login_log)
    path = login_log or LOGIN_LOG_FILE
    row = {
        "date_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "username": str(username),
        "success": "yes" if success else "no",
        "reason": reason,
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOGIN_LOG_COLUMNS)
        writer.writerow(row)


def load_login_log(login_log: str = None):
    """Return login attempts as a list of dicts (empty if none yet)."""
    import pandas as pd
    path = login_log or LOGIN_LOG_FILE
    if not os.path.exists(path):
        return pd.DataFrame(columns=LOGIN_LOG_COLUMNS)
    return pd.read_csv(path)
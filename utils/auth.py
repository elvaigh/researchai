"""Authentication helpers."""
import bcrypt
import streamlit as st
from utils.db import create_user, get_user_by_email


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def register_user(email: str, username: str, password: str):
    """Register a new user. Returns (user_dict, error_string)."""
    if not email or not username or not password:
        return None, "All fields are required."
    if get_user_by_email(email):
        return None, "Email already registered."
    if len(password) < 6:
        return None, "Password must be at least 6 characters."
    try:
        hashed = hash_password(password)
        user = create_user(email, username, hashed)
        return user, None
    except Exception as e:
        return None, str(e)


def login_user(email: str, password: str):
    """Authenticate a user. Returns (user_dict, error_string)."""
    if not email or not password:
        return None, "Email and password are required."
    try:
        user = get_user_by_email(email)
    except Exception as e:
        return None, f"Database error: {e}"
    if not user:
        return None, "No account found with this email."
    if not verify_password(password, user["password"]):
        return None, "Incorrect password."
    return user, None


def require_auth():
    """Redirect to login if not authenticated. Returns user dict."""
    if not st.session_state.get("user"):
        st.warning("Please log in to access this page.")
        st.stop()
    return st.session_state.user
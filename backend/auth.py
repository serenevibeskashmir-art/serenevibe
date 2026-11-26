from functools import wraps

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="admin-auth")


# Roles: "admin" is the main admin (everything, including Accounts);
# "admin2" is the second admin (everything except Accounts: payments, ledger, PDF import).
ROLES = ("admin", "admin2")


def create_admin_token(role="admin"):
    return _serializer().dumps({"role": role})


def get_admin_role(token):
    """Return the role stored in a valid token, or None."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=60 * 60 * 12)
    except (BadSignature, SignatureExpired):
        return None
    role = data.get("role")
    return role if role in ROLES else None


def verify_admin_token(token):
    return get_admin_role(token) is not None


def _bearer_token():
    auth_header = request.headers.get("Authorization", "")
    return auth_header.removeprefix("Bearer ").strip() if auth_header else ""


def current_admin_name():
    """Display name of the admin making this request (for the sheet's Created By column)."""
    from backend.config import Config
    return Config.ADMIN2_NAME if get_admin_role(_bearer_token()) == "admin2" else Config.ADMIN_NAME


def admin_required(view):
    """Any admin (main or second)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_admin_role(_bearer_token()) is None:
            return jsonify({"error": "Admin authentication required."}), 401
        return view(*args, **kwargs)

    return wrapped


def main_admin_required(view):
    """Main admin only (used for Accounts: payments and ledger)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        role = get_admin_role(_bearer_token())
        if role is None:
            return jsonify({"error": "Admin authentication required."}), 401
        if role != "admin":
            return jsonify({"error": "Accounts are available to the main admin only."}), 403
        return view(*args, **kwargs)

    return wrapped

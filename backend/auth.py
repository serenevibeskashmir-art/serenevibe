from functools import wraps

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="admin-auth")


def create_admin_token():
    return _serializer().dumps({"role": "admin"})


def verify_admin_token(token):
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=60 * 60 * 12)
        return data.get("role") == "admin"
    except (BadSignature, SignatureExpired):
        return False


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header else ""
        if not verify_admin_token(token):
            return jsonify({"error": "Admin authentication required."}), 401
        return view(*args, **kwargs)

    return wrapped

from functools import wraps
from flask import session, redirect, url_for, flash, jsonify
def facial_auth_required(f):
    """Decorador para requerir autenticación facial"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated', False):
            return jsonify({
                "error": "Autenticación requerida",
                "message": "Debe verificar su identidad facial primero"
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "role" not in session:
                flash("Debes iniciar sesión.")
                return redirect(url_for("index"))
            if session["role"] not in required_roles:
                flash("No tienes permiso para acceder a esta página.")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator
from functools import wraps
from flask import session, jsonify

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
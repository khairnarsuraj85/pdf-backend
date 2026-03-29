from __future__ import annotations

from functools import wraps

from flask import jsonify

from backend.utils.errors import PdfProcessingError, RequestValidationError
from backend.utils.file_handler import error_response


def handle_route_errors(default_message: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            try:
                return view_func(*args, **kwargs)
            except RequestValidationError as exc:
                return error_response(str(exc), 400)
            except PdfProcessingError as exc:
                return error_response(str(exc), 422)
            except Exception as exc:  # pragma: no cover
                return jsonify({"error": default_message, "details": str(exc)}), 500

        return wrapper

    return decorator

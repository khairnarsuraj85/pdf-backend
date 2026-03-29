from backend.routes.ai import ai_bp
from backend.routes.compress import compress_bp
from backend.routes.convert import convert_bp
from backend.routes.merge import merge_bp
from backend.routes.split import split_bp

REGISTERED_BLUEPRINTS = (
    compress_bp,
    split_bp,
    merge_bp,
    convert_bp,
    ai_bp,
)

__all__ = ["REGISTERED_BLUEPRINTS"]

from flask import Flask, jsonify
from flask_cors import CORS

from backend.config import EXPOSED_RESPONSE_HEADERS, load_app_config
from backend.routes import REGISTERED_BLUEPRINTS


def create_app() -> Flask:
    config = load_app_config()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.max_content_length

    CORS(
        app,
        resources={r"/*": {"origins": config.cors_origins}},
        expose_headers=list(EXPOSED_RESPONSE_HEADERS),
    )

    for blueprint in REGISTERED_BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "QuickPDF API",
                "privacy": "Files are processed in memory and deleted immediately after response.",
            }
        )

    @app.errorhandler(413)
    def file_too_large(_error):
        return (
            jsonify(
                {
                    "error": "File too large. The maximum upload size is 50MB.",
                    "code": "FILE_TOO_LARGE",
                }
            ),
            413,
        )

    return app

import os
import platform

from backend import create_app

app = create_app()


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    is_windows = platform.system() == "Windows"
    is_render = bool(os.getenv("RENDER"))
    debug = env_flag("FLASK_DEBUG", default=not is_render)
    use_reloader = env_flag("FLASK_USE_RELOADER", default=debug and not is_windows)
    port = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=use_reloader,
    )

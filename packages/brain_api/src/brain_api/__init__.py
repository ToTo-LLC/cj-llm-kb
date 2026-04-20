"""brain_api — FastAPI REST + WebSocket backend wrapping brain_core."""

from brain_api.app import create_app

__version__ = "0.0.1"
__all__ = ["__version__", "create_app"]

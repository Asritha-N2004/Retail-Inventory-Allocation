"""Vercel entrypoint: serve the API and the compiled React application."""

from pathlib import Path
from backend.app.main import app

frontend = Path(__file__).parent / "frontend" / "dist"
app.frontend("/", directory=str(frontend), fallback="index.html")

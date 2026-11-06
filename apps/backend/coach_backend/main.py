"""Application entrypoint."""

from coach_backend.api import create_app
from coach_backend.settings import Settings

settings = Settings.from_env()
app = create_app(settings)

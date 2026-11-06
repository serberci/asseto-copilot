import uvicorn

from coach_backend.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "coach_backend.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
    )


if __name__ == "__main__":
    main()

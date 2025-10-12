from fastapi import FastAPI

from .api import oauth, rbac
from .config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.include_router(rbac.router)
app.include_router(oauth.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

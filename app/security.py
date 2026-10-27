import secrets

from fastapi import Header, HTTPException, status

from .config import settings


def verifier_cle(x_api_key: str | None = Header(default=None)) -> None:
    """Protection par clé d'API (désactivée si POINTAGE_API_KEY n'est pas défini)."""
    if settings.api_key is None:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé d'API invalide ou absente")

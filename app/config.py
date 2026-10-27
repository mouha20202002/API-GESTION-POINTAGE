from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POINTAGE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./pointage.db"
    api_key: str | None = None

    # Feuille ELEMENT du classeur : "marge de retard matinale et heure normale"
    heure_normale_matin: time = time(8, 0)
    heure_limite_matin: time = time(8, 30)   # la formule Excel (col. SITUATION) compare à cette valeur
    heure_normale_soir: time = time(17, 0)
    heure_limite_soir: time = time(17, 30)


settings = Settings()

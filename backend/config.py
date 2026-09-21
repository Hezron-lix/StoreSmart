"""Central configuration for the StoreSmart backend.

All modules must import SETTINGS from here — never read .env directly and
never hardcode credentials, paths, or secrets.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str
    db_name: str = "storagewise"

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Paths (relative to repo root)
    log_path: str = "logs/audit.csv"
    reference_dir: str = "reference"
    schemas_dir: str = "schemas"

    # Server
    api_port: int = 8000

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def log_path_abs(self) -> Path:
        return self.repo_root / self.log_path

    @property
    def reference_dir_abs(self) -> Path:
        return self.repo_root / self.reference_dir

    @property
    def schemas_dir_abs(self) -> Path:
        return self.repo_root / self.schemas_dir

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        case_sensitive = False


SETTINGS = Settings()

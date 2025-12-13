"""Utilities for loading Veryfi API credentials securely.

The helpers in this module favor environment variables so that sensitive
values never need to be written to disk in plain text. During development
you can also rely on a local ``.env`` file that remains on your machine.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional
import os


ENV_FILE = Path(".env")


@dataclass(frozen=True)
class VeryfiCredentials:
    """Container with the values required to authenticate against Veryfi."""

    api_url: str
    client_id: str
    client_secret: str
    username: str
    api_key: str


def _read_env_file(path: Path) -> Dict[str, str]:
    """Parse a dotenv-like file into a mapping without mutating ``os.environ``."""

    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, sep, value = line.partition("=")
        if not sep:
            continue  # Skip malformed entries quietly.

        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def load_credentials(env_file: Optional[Path] = ENV_FILE) -> VeryfiCredentials:
    """Return Veryfi credentials combining env vars and an optional env file.

    Environment variables always win over the values from the ``env_file``.
    ``env_file`` should stay outside of Git so secrets never leave your machine.
    """

    file_values: Mapping[str, str] = {}
    if env_file is not None:
        file_values = _read_env_file(Path(env_file))

    def _get(key: str, *, default: Optional[str] = None) -> str:
        value = os.environ.get(key, file_values.get(key, default))
        if value is None or not value.strip():
            raise RuntimeError(f"Missing required Veryfi credential: {key}")
        return value.strip()

    return VeryfiCredentials(
        api_url=_get("VERYFI_API_URL", default="https://api.veryfi.com/"),
        client_id=_get("VERYFI_CLIENT_ID"),
        client_secret=_get("VERYFI_CLIENT_SECRET"),
        username=_get("VERYFI_USERNAME"),
        api_key=_get("VERYFI_API_KEY"),
    )


__all__ = ["VeryfiCredentials", "load_credentials"]

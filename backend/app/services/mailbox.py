"""Resolves IMAP connection details from a stored, encrypted email credential."""
import json

from app.agents.fetch_agent import IMAP_HOSTS
from app.core.security import decrypt_data
from app.models.credential import Credential


class MailboxNotFetchable(Exception):
    """Raised when a credential's provider has no IMAP fetch capability."""


def imap_config_from_credential(credential: Credential) -> dict:
    secret = json.loads(decrypt_data(credential.encrypted_secret) or "{}")

    if credential.provider in IMAP_HOSTS:
        host, port = IMAP_HOSTS[credential.provider]
        return {
            "imap_host": host,
            "imap_port": port,
            "username": secret["email"],
            "password": secret["app_password"],
        }

    if credential.provider == "imap":
        return {
            "imap_host": secret["host"],
            "imap_port": int(secret.get("port") or 993),
            "username": secret["username"],
            "password": secret["password"],
        }

    raise MailboxNotFetchable(
        f"The '{credential.provider}' provider can't fetch mail. "
        "Use Gmail, Outlook, or a Custom IMAP credential as the inbox."
    )
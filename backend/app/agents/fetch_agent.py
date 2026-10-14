
import email
import imaplib
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class FetchState(TypedDict, total=False):
    imap_host: str
    imap_port: int
    username: str
    password: str
    new_emails: list[dict[str, Any]]
    error: str | None


# Providers with a fixed, well-known IMAP host. Custom IMAP credentials
# supply their own host/port instead (see app/services/mailbox.py).
IMAP_HOSTS = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
}


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    out = ""
    for text, enc in decode_header(value):
        out += text.decode(enc or "utf-8", errors="ignore") if isinstance(text, bytes) else text
    return out


def _extract_body(msg: "email.message.Message") -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                return payload.decode(errors="ignore") if payload else ""
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="ignore") if payload else ""


def fetch_unseen_node(state: FetchState) -> FetchState:
    """Reads every UNSEEN message in INBOX. Never raises -- failures are
    put in state["error"] so the API layer can return a clean 4xx/5xx
    instead of an unhandled exception."""
    new_emails: list[dict[str, Any]] = []
    conn = None
    try:
        conn = imaplib.IMAP4_SSL(state["imap_host"], state["imap_port"])
        conn.login(state["username"], state["password"])
        conn.select("INBOX")

        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            state["error"] = "IMAP search failed"
            return state

        for msg_id in data[0].split():
            status, msg_data = conn.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            parsed = email.message_from_bytes(msg_data[0][1])

            try:
                received_at = parsedate_to_datetime(parsed.get("Date"))
            except Exception:
                received_at = None

            new_emails.append(
                {
                    "message_id": parsed.get("Message-ID") or msg_id.decode(),
                    "sender": _decode_header_value(parsed.get("From")),
                    "subject": _decode_header_value(parsed.get("Subject")),
                    "snippet": _extract_body(parsed).strip()[:500],
                    "received_at": received_at,
                }
            )

        state["new_emails"] = new_emails
    except Exception as exc:
        state["error"] = f"Could not fetch mail: {exc}"
    finally:
        if conn is not None:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass
    return state


def build_fetch_graph():
    graph = StateGraph(FetchState)
    graph.add_node("fetch_unseen", fetch_unseen_node)
    graph.set_entry_point("fetch_unseen")
    graph.add_edge("fetch_unseen", END)
    return graph.compile()


fetch_graph = build_fetch_graph()
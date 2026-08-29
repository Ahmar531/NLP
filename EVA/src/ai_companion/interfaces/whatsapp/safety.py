import logging
import re
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("ai_companion.whatsapp.safety")

# Record server startup time to drop historical/stale webhook deliveries
SERVER_START_TIME: float = time.time()

# Allowed message event types from WhatsApp integrations
ALLOWED_MESSAGE_EVENTS = {
    "MESSAGES_UPSERT",
    "MESSAGE_UPSERT",
    "MESSAGES.UPSERT",
    "MESSAGE.UPSERT",
    "MESSAGES",
}

# Explicitly ignored non-message events
IGNORED_EVENTS = {
    "CONNECTION_UPDATE",
    "CONNECTION.UPDATE",
    "PRESENCE_UPDATE",
    "PRESENCE.UPDATE",
    "CHATS_SET",
    "CHATS.SET",
    "CHATS_UPSERT",
    "CHATS.UPSERT",
    "CHATS_UPDATE",
    "CHATS.UPDATE",
    "CHATS_DELETE",
    "CHATS.DELETE",
    "CONTACTS_SET",
    "CONTACTS.SET",
    "CONTACTS_UPSERT",
    "CONTACTS.UPSERT",
    "CONTACTS_UPDATE",
    "CONTACTS.UPDATE",
    "MESSAGES_SET",
    "MESSAGES.SET",
    "MESSAGES_UPDATE",
    "MESSAGES.UPDATE",
    "MESSAGES_DELETE",
    "MESSAGES.DELETE",
    "SEND_MESSAGE",
    "STATUS_BROADCAST",
    "CALL",
    "CALL.OFFER",
    "QRCODE_UPDATED",
    "LABELS_ASSOCIATION",
    "LABELS_EDIT",
}


class WhatsAppIdempotencyStore:
    """Thread-safe TTL store for WhatsApp message IDs to guarantee idempotency."""

    def __init__(self, ttl_seconds: int = 600, max_size: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._processed: Dict[str, float] = {}
        self._lock = threading.Lock()

    def is_processed(self, message_id: str) -> bool:
        """Check if message_id was already processed recently."""
        if not message_id or not message_id.strip():
            return False
        with self._lock:
            self._evict_stale()
            return message_id.strip() in self._processed

    def mark_processed(self, message_id: str) -> bool:
        """
        Atomically mark message_id as processed.
        Returns True if marked successfully, or False if it was already processed.
        """
        if not message_id or not message_id.strip():
            return False
        clean_id = message_id.strip()
        with self._lock:
            self._evict_stale()
            if clean_id in self._processed:
                return False
            # Bounded capacity guard
            if len(self._processed) >= self.max_size:
                oldest_key = min(self._processed, key=self._processed.get)
                del self._processed[oldest_key]
            self._processed[clean_id] = time.time()
            return True

    def _evict_stale(self) -> None:
        """Evict records older than ttl_seconds."""
        now = time.time()
        stale_keys = [
            mid for mid, ts in self._processed.items()
            if now - ts > self.ttl_seconds
        ]
        for mid in stale_keys:
            del self._processed[mid]

    def clear(self) -> None:
        """Clear store (primarily for unit testing)."""
        with self._lock:
            self._processed.clear()


# Global singleton instance of idempotency store
idempotency_store = WhatsAppIdempotencyStore()


def normalize_phone_number(jid_or_number: str, alt_jid: Optional[str] = None) -> str:
    """
    Extract a normalized, clean phone number or stable user ID from a WhatsApp JID or raw number.
    Ensures LID, standard WhatsApp JID, or phone numbers resolve to a stable thread identity.
    """
    candidate = ""
    if alt_jid and "@s.whatsapp.net" in alt_jid:
        candidate = alt_jid
    elif jid_or_number:
        candidate = jid_or_number

    if not candidate:
        return ""

    # Split domain part if present
    user_part = candidate.split("@")[0]
    # Split device identifier if present (e.g., 923001234567:1)
    user_part = user_part.split(":")[0]
    # Strip any leading '+' or extraneous symbols
    cleaned = re.sub(r"[^\w]", "", user_part).strip()
    return cleaned


def is_group_or_broadcast(jid: str) -> bool:
    """Check if the JID belongs to a group, status broadcast, or newsletter."""
    if not jid:
        return False
    jid_lower = jid.lower()
    return (
        "@g.us" in jid_lower
        or "status@broadcast" in jid_lower
        or "@newsletter" in jid_lower
        or "@broadcast" in jid_lower
    )


def validate_incoming_event(
    event_type: str,
    message_id: str,
    sender_number: str,
    message_timestamp: Optional[float] = None,
    from_me: bool = False,
    server_start_time: float = SERVER_START_TIME,
    max_age_seconds: float = 3600.0,
) -> Tuple[bool, str]:
    """
    Strict validation of incoming WhatsApp webhook event before processing.

    Enforces:
    1. Only allowed message event types.
    2. Drops non-message events (presence, connection, status, etc.).
    3. Drops self-messages (fromMe == True).
    4. Drops group chats and status broadcasts.
    5. Drops duplicate message IDs (idempotency).
    6. Requires non-empty message_id and sender_number.

    Returns:
        (is_valid: bool, reason: str)
    """
    norm_event = str(event_type or "").upper().replace(".", "_").replace("-", "_")

    # 1. Event type filtering
    if norm_event in IGNORED_EVENTS:
        return False, f"Ignored non-message event type: {event_type}"

    if norm_event and not any(
        kw in norm_event
        for kw in {"MESSAGE", "MESSAGES", "UPSERT", "SEND_MESSAGE"}
    ):
        return False, f"Unsupported event type: {event_type}"

    # 2. Self message check
    if from_me:
        return False, "Ignored self message (fromMe=True)"

    # 3. Message ID and sender validation
    if not message_id or not str(message_id).strip():
        return False, "Missing incoming message_id"

    if not sender_number or not str(sender_number).strip():
        return False, "Missing sender_number"

    # 4. Group / Broadcast check
    if is_group_or_broadcast(sender_number):
        return False, f"Ignored group/broadcast message: {sender_number}"

    # 5. Timestamp staleness check (prevent dropping due to server reload clock-skew)
    if message_timestamp is not None:
        try:
            ts = float(message_timestamp)
            if ts > 1e11:
                ts = ts / 1000.0

            now = time.time()
            if (now - ts) > max_age_seconds:
                return False, f"Stale message older than {max_age_seconds}s (age={now - ts:.1f}s)"
        except (ValueError, TypeError) as err:
            logger.warning("Could not parse message_timestamp: %s", err)

    # 6. Idempotency check
    if idempotency_store.is_processed(message_id):
        return False, f"Duplicate message_id already processed: {message_id}"

    return True, "Valid"


def validate_outgoing_send(
    incoming_message_id: str,
    sender_number: str,
    outgoing_recipient: str,
    event_type: str,
) -> Tuple[bool, str]:
    """
    Final Safety Gatekeeper:
    Enforces:
    `Valid NEW incoming message → identify exact sender → process → generate response → send ONLY to that sender`

    Validates:
    1. incoming_message_id is non-empty.
    2. sender_number is non-empty and not a group/broadcast.
    3. outgoing_recipient is non-empty and not a group/broadcast.
    4. outgoing_recipient matches sender_number (normalized comparison).
    5. Emits structured audit log for every message.

    Returns:
        (is_valid: bool, reason: str)
    """
    inc_id = str(incoming_message_id or "").strip()
    sender = str(sender_number or "").strip()
    recipient = str(outgoing_recipient or "").strip()
    evt = str(event_type or "MESSAGE_UPSERT").strip()

    if not inc_id:
        reason = "Missing incoming_message_id"
        _log_audit(inc_id, sender, evt, recipient, "BLOCKED", reason)
        return False, reason

    if not sender:
        reason = "Missing sender_number"
        _log_audit(inc_id, sender, evt, recipient, "BLOCKED", reason)
        return False, reason

    if not recipient:
        reason = "Missing outgoing_recipient"
        _log_audit(inc_id, sender, evt, recipient, "BLOCKED", reason)
        return False, reason

    if is_group_or_broadcast(recipient) or is_group_or_broadcast(sender):
        reason = "Recipient or sender is group/broadcast"
        _log_audit(inc_id, sender, evt, recipient, "BLOCKED", reason)
        return False, reason

    # Compare normalized numbers
    norm_sender = normalize_phone_number(sender)
    norm_recipient = normalize_phone_number(recipient)

    if norm_sender != norm_recipient:
        # Check if recipient is a raw JID matching sender
        if recipient.split("@")[0] != sender.split("@")[0]:
            reason = f"Recipient mismatch (sender={sender}, recipient={recipient})"
            _log_audit(inc_id, sender, evt, recipient, "BLOCKED", reason)
            return False, reason

    _log_audit(inc_id, sender, evt, recipient, "ALLOWED", "Valid")
    return True, "Valid"


def _log_audit(
    incoming_message_id: str,
    sender_number: str,
    event_type: str,
    outgoing_recipient: str,
    status: str,
    reason: str = "",
) -> None:
    """Emit structured audit log for every WhatsApp message sending attempt."""
    msg = (
        f"[OUTGOING_WHATSAPP_AUDIT] incoming_message_id='{incoming_message_id}' "
        f"sender_number='{sender_number}' event_type='{event_type}' "
        f"outgoing_recipient='{outgoing_recipient}' status='{status}'"
    )
    if reason and status != "ALLOWED":
        msg += f" reason='{reason}'"

    if status == "ALLOWED":
        logger.info(msg)
    else:
        logger.error(msg)

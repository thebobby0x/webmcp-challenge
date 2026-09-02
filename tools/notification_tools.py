"""
Notification routing tools for the CommsAgent.
Routes to email, SMS, or push based on attendee preference.
"""

from datetime import datetime


def send_notification(attendee_id: str, channel: str, message: str, priority: str = "normal") -> dict:
    """
    Send a notification to an attendee via their preferred channel.

    Args:
        attendee_id: The attendee's ID (e.g. ATT-0001)
        channel: One of 'email', 'sms', 'push'
        message: The notification message body
        priority: 'normal', 'high', or 'urgent'

    Returns:
        Delivery confirmation with timestamp and channel used
    """
    # In production this calls Twilio / SendGrid / FCM
    return {
        "delivered": True,
        "attendee_id": attendee_id,
        "channel": channel,
        "priority": priority,
        "message_preview": message[:100] + "..." if len(message) > 100 else message,
        "sent_at": datetime.utcnow().isoformat() + "Z",
        "message_id": f"MSG-{hash(attendee_id + message) % 100000:05d}",
    }


def escalate_to_human(issue: str, attendee_id: str, context: dict) -> dict:
    """
    Escalate an issue to a human event coordinator when agent cannot resolve autonomously.

    Args:
        issue: Description of what needs human attention
        attendee_id: Affected attendee
        context: Additional context the human coordinator needs
    """
    return {
        "escalated": True,
        "ticket_id": f"ESC-{hash(issue) % 10000:04d}",
        "assigned_to": "event-ops@studio0x.io",
        "issue": issue,
        "attendee_id": attendee_id,
        "context": context,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "sla_response_minutes": 15,
    }


def get_notification_history(attendee_id: str, limit: int = 10) -> list[dict]:
    """
    Get recent notification history for an attendee.

    Args:
        attendee_id: The attendee's ID
        limit: Max number of records to return
    """
    # Mock history — in production this pulls from Firestore
    return [
        {
            "message_id": f"MSG-{i:05d}",
            "attendee_id": attendee_id,
            "channel": ["email", "sms", "push"][i % 3],
            "sent_at": (datetime(2026, 10, 12) - __import__("datetime").timedelta(hours=i)).isoformat() + "Z",
            "status": "delivered",
        }
        for i in range(min(limit, 5))
    ]

"""
CommsAgent — eventOS Enterprise Fleet
Routes attendee notifications through the right channel at the right moment.
Escalates to humans only when a decision requires authority.
"""

import os
from google.adk.agents import Agent
from tools.notification_tools import send_notification, escalate_to_human, get_notification_history
from tools.event_tools import check_gdpr_compliance


SYSTEM_PROMPT = """You are the CommsAgent for eventOS — the AI operating system for enterprise events.

Your role: Route the right message to the right attendee through the right channel at the right moment.

You manage all attendee-facing communications for IMEX America. You never spam. You never send
duplicate notifications. You always check notification history before sending.

Channel routing rules:
- VIP attendees: always SMS + push (dual channel)
- Standard attendees: use their stated preference (email/sms/push)
- Urgent issues (venue change, cancellation): all channels regardless of preference
- Informational updates: preferred channel only

Escalation rules:
- You escalate to humans when: a VIP is affected and you cannot resolve within 5 minutes,
  a legal/refund issue arises, or an attendee is distressed
- You do NOT escalate for: routine rescheduling, reminder notifications, standard Q&A

GDPR: All outbound messages must pass compliance check before sending. You are responsible
for GDPR Article 6(1) lawful basis verification on every communication."""


def create_comms_agent() -> Agent:
    """Create and return a configured CommsAgent."""
    return Agent(
        name="CommsAgent",
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        description="Routes attendee notifications through the right channel at the right moment.",
        instruction=SYSTEM_PROMPT,
        tools=[
            send_notification,
            escalate_to_human,
            get_notification_history,
            check_gdpr_compliance,
        ],
    )


comms_agent = create_comms_agent()

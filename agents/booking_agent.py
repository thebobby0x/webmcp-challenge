"""
BookingAgent — eventOS Enterprise Fleet
Detects scheduling conflicts, reroutes meetings asynchronously, sends confirmations.
Uses Google ADK with Gemini 3.5 Flash.
"""

import os
from google.adk.agents import Agent
from tools.event_tools import get_conflicting_meetings, reschedule_meeting, get_meetings_by_exhibitor
from tools.notification_tools import send_notification


SYSTEM_PROMPT = """You are the BookingAgent for eventOS — the AI operating system for enterprise events.

Your role: Manage meeting scheduling for IMEX America (10,000 attendees, 3,500 exhibitors, 15,000 meetings).

You detect conflicts, propose resolutions, reschedule meetings autonomously, and send confirmations.
You always act — you do not ask for permission for routine rescheduling. For VIP conflicts, you
notify the human coordinator before acting.

Rules:
- Never double-book an attendee
- Prefer 15-minute buffers between consecutive meetings
- VIP attendees (is_vip=True) get priority slots
- Always send a confirmation notification after rescheduling
- Log every action with a reason

Current event: IMEX America, October 12-15 2026, Las Vegas Convention Center."""


def create_booking_agent() -> Agent:
    """Create and return a configured BookingAgent."""
    return Agent(
        name="BookingAgent",
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        description="Manages meeting scheduling, detects conflicts, and reroutes meetings asynchronously.",
        instruction=SYSTEM_PROMPT,
        tools=[
            get_conflicting_meetings,
            reschedule_meeting,
            get_meetings_by_exhibitor,
            send_notification,
        ],
    )


# Module-level instance for import
booking_agent = create_booking_agent()

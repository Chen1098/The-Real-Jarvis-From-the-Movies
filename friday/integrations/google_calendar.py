"""
Google Calendar Integration for Jarvis
"""
import os
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
from friday.utils.logger import get_logger

logger = get_logger("google_calendar")


class CalendarEvent:
    """Represents a calendar event"""
    def __init__(self, summary: str, start: datetime, end: datetime, location: str = "", description: str = ""):
        self.summary = summary
        self.start = start
        self.end = end
        self.location = location
        self.description = description

    def __str__(self):
        time_str = self.start.strftime("%I:%M %p")
        return f"{self.summary} at {time_str}"

    def to_dict(self):
        return {
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "location": self.location,
            "description": self.description
        }


class GoogleCalendarService:
    """Google Calendar integration service"""

    def __init__(self):
        self.service = None
        self.enabled = False
        self.events_cache = []
        self.cache_time = None

    def start(self):
        """Initialize Google Calendar service"""
        try:
            # Try to import Google libraries
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import InstalledAppFlow
                from googleapiclient.discovery import build
            except ImportError:
                logger.warning("Google Calendar libraries not installed. Run: pip install google-auth-oauthlib google-api-python-client")
                return False

            SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
            creds = None

            # Token file stores user's access and refresh tokens
            token_path = Path("config/google_calendar_token.pickle")
            credentials_path = Path("config/google_calendar_credentials.json")

            # Check if credentials file exists
            if not credentials_path.exists():
                logger.warning(f"Google Calendar credentials not found at {credentials_path}")
                logger.info("To enable calendar: Download credentials from Google Cloud Console")
                return False

            # Load saved credentials
            if token_path.exists():
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)

            # If no valid credentials, login
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path), SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save credentials
                token_path.parent.mkdir(exist_ok=True)
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)

            # Build service
            self.service = build('calendar', 'v3', credentials=creds)
            self.enabled = True

            logger.info("Google Calendar service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}", exc_info=True)
            return False

    def stop(self):
        """Cleanup"""
        self.service = None
        self.enabled = False
        logger.info("Google Calendar service stopped")

    def get_todays_events(self) -> List[CalendarEvent]:
        """Get all events for today"""
        if not self.enabled:
            return []

        try:
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now + timedelta(days=1)

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=end_of_day.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            calendar_events = []

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Parse datetime
                if 'T' in start:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                else:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)

                calendar_events.append(CalendarEvent(
                    summary=event.get('summary', 'No title'),
                    start=start_dt,
                    end=end_dt,
                    location=event.get('location', ''),
                    description=event.get('description', '')
                ))

            self.events_cache = calendar_events
            self.cache_time = datetime.now()

            logger.info(f"Retrieved {len(calendar_events)} events for today")
            return calendar_events

        except Exception as e:
            logger.error(f"Error fetching today's events: {e}")
            return []

    def get_next_event(self) -> Optional[CalendarEvent]:
        """Get the next upcoming event"""
        if not self.enabled:
            return None

        try:
            now = datetime.now()
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                maxResults=1,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            if not events:
                return None

            event = events[0]
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            # Parse datetime
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                start_dt = datetime.fromisoformat(start)
                end_dt = datetime.fromisoformat(end)

            return CalendarEvent(
                summary=event.get('summary', 'No title'),
                start=start_dt,
                end=end_dt,
                location=event.get('location', ''),
                description=event.get('description', '')
            )

        except Exception as e:
            logger.error(f"Error fetching next event: {e}")
            return None

    def get_upcoming_events(self, hours: int = 24) -> List[CalendarEvent]:
        """Get events in the next N hours"""
        if not self.enabled:
            return []

        try:
            now = datetime.now()
            time_max = now + timedelta(hours=hours)

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            calendar_events = []

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                if 'T' in start:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                else:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)

                calendar_events.append(CalendarEvent(
                    summary=event.get('summary', 'No title'),
                    start=start_dt,
                    end=end_dt,
                    location=event.get('location', ''),
                    description=event.get('description', '')
                ))

            return calendar_events

        except Exception as e:
            logger.error(f"Error fetching upcoming events: {e}")
            return []

    def get_events_summary(self) -> str:
        """Get human-readable summary of today's events"""
        events = self.get_todays_events()

        if not events:
            return "No events scheduled for today"

        if len(events) == 1:
            return f"You have 1 event today: {events[0]}"

        summary = f"You have {len(events)} events today:\n"
        for i, event in enumerate(events, 1):
            time_str = event.start.strftime("%I:%M %p")
            summary += f"{i}. {event.summary} at {time_str}\n"

        return summary.strip()

    def is_free_at(self, check_time: datetime) -> bool:
        """Check if a specific time is free"""
        if not self.enabled:
            return True  # Assume free if calendar not available

        events = self.get_todays_events()

        for event in events:
            if event.start <= check_time < event.end:
                return False

        return True

    def get_context_string(self) -> str:
        """Get calendar context for AI prompt"""
        if not self.enabled:
            return "Calendar: Not connected"

        next_event = self.get_next_event()
        todays_events = self.get_todays_events()

        if not next_event and not todays_events:
            return "Calendar: No events today"

        context_parts = []

        if todays_events:
            context_parts.append(f"Today's schedule: {len(todays_events)} events")

        if next_event:
            now = datetime.now()
            time_until = next_event.start - now

            if time_until.total_seconds() < 3600:  # Less than 1 hour
                minutes = int(time_until.total_seconds() / 60)
                context_parts.append(f"Next: '{next_event.summary}' in {minutes} minutes")
            else:
                time_str = next_event.start.strftime("%I:%M %p")
                context_parts.append(f"Next: '{next_event.summary}' at {time_str}")

        return "Calendar: " + ", ".join(context_parts)

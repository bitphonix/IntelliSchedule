import os
import json
import pickle
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class CalendarService:
    """Google Calendar API service with OAuth2 authentication"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.pickle'):
        self.credentials = None
        self.service = None
        self.flow = None
        self.redirect_uri = "http://localhost:8000/auth/callback"
        self.credentials_path = credentials_path
        self.token_path = token_path
        
        self._load_credentials()
    
    def _load_credentials(self):
        """Load existing credentials from file"""
        try:
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    self.credentials = pickle.load(token)
                    
            if self.credentials and self.credentials.valid:
                self.service = build('calendar', 'v3', credentials=self.credentials)
                logger.info("Loaded existing credentials")
                
        except Exception as e:
            logger.error(f"Error loading credentials from {self.token_path}: {str(e)}")
    
    def _save_credentials(self):
        """Save credentials to file"""
        try:
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.credentials, token)
            logger.info(f"Credentials saved successfully to {self.token_path}")
        except Exception as e:
            logger.error(f"Error saving credentials to {self.token_path}: {str(e)}")
    
    def get_auth_url(self) -> str:
        """Get Google OAuth authorization URL"""
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"credentials.json not found at {self.credentials_path}.")
            
            self.flow = Flow.from_client_secrets_file(
                self.credentials_path,
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            auth_url, _ = self.flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error creating auth URL: {str(e)}")
            raise
    
    def authenticate_with_code(self, code: str):
        """Complete OAuth flow with authorization code"""
        try:
            if not self.flow:
                raise ValueError("OAuth flow not initialized. Call get_auth_url() first.")
            
            self.flow.fetch_token(code=code)
            self.credentials = self.flow.credentials
            self._save_credentials()
            self.service = build('calendar', 'v3', credentials=self.credentials)
            logger.info("Authentication successful")
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            if "scope" in str(e).lower():
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)
                    logger.info(f"Cleared existing credentials due to scope mismatch at {self.token_path}")
                raise ValueError("Authentication scope mismatch. Please try connecting again.")
            raise
    
    def is_authenticated(self) -> bool:
        """Check if service is authenticated"""
        return self.service is not None and self.credentials and self.credentials.valid
    
    def refresh_credentials(self):
        """Refresh expired credentials"""
        try:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
                self._save_credentials()
                self.service = build('calendar', 'v3', credentials=self.credentials)
                logger.info("Credentials refreshed")
                
        except Exception as e:
            logger.error(f"Error refreshing credentials: {str(e)}")
            raise
    
    def get_primary_calendar(self) -> str:
        """Get primary calendar ID"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            calendar_list = self.service.calendarList().list().execute()
            
            for calendar in calendar_list.get('items', []):
                if calendar.get('primary', False):
                    return calendar['id']
            
            return 'primary'
            
        except Exception as e:
            logger.error(f"Error getting primary calendar: {str(e)}")
            raise
    
    def get_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get calendar events for a date range"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            start_utc = start_date.astimezone(pytz.utc)
            end_utc = end_date.astimezone(pytz.utc)

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_utc.isoformat(),
                timeMax=end_utc.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            processed_events = []
            for event in events:
                start_str = event['start'].get('dateTime', event['start'].get('date'))
                end_str = event['end'].get('dateTime', event['end'].get('date'))
                
                processed_events.append({
                    'id': event['id'],
                    'title': event.get('summary', 'No Title'),
                    'start': datetime.fromisoformat(start_str.replace('Z', '+00:00')),
                    'end': datetime.fromisoformat(end_str.replace('Z', '+00:00')),
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'status': event.get('status', 'confirmed')
                })
            
            return processed_events
            
        except HttpError as e:
            logger.error(f"HTTP error getting events: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting events: {str(e)}")
            raise
    
    def get_availability(self, start_date: datetime, end_date: datetime, duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Get available time slots using the efficient freebusy query."""
        if not self.is_authenticated():
            raise ValueError("Not authenticated")
    
        start_utc = start_date.astimezone(pytz.utc)
        end_utc = end_date.astimezone(pytz.utc)

        body = {
            "timeMin": start_utc.isoformat(),
            "timeMax": end_utc.isoformat(),
            "items": [{"id": "primary"}],
            "timeZone": "UTC"
        }

        try:
            freebusy_result = self.service.freebusy().query(body=body).execute()
            busy_periods = freebusy_result.get('calendars', {}).get('primary', {}).get('busy', [])
        except HttpError as e:
            logger.error(f"HTTP error on freebusy query: {e}")
            return []

        available_slots = []
        
        current_slot_start = start_utc

        all_busy_periods = [{'start': start_utc.isoformat(), 'end': start_utc.isoformat()}]
        all_busy_periods.extend(busy_periods)
        all_busy_periods.append({'start': end_utc.isoformat(), 'end': end_utc.isoformat()})

        all_busy_periods.sort(key=lambda x: x['start'])

        for i in range(len(all_busy_periods) - 1):
            free_period_start = datetime.fromisoformat(all_busy_periods[i]['end'].replace('Z', '+00:00'))
            free_period_end = datetime.fromisoformat(all_busy_periods[i+1]['start'].replace('Z', '+00:00'))

            current_slot = free_period_start
            while current_slot + timedelta(minutes=duration_minutes) <= free_period_end:
                slot_start_utc = current_slot
                slot_end_utc = current_slot + timedelta(minutes=duration_minutes)
                
                available_slots.append({
                    'start': slot_start_utc.astimezone(start_date.tzinfo),
                    'end': slot_end_utc.astimezone(start_date.tzinfo),
                })
                current_slot += timedelta(minutes=duration_minutes)
        
        return available_slots
    
    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a specific time slot is available"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            start_utc = start_time.astimezone(pytz.utc)
            end_utc = end_time.astimezone(pytz.utc)

            body = {
                'timeMin': start_utc.isoformat(),
                'timeMax': end_utc.isoformat(),
                'items': [{'id': 'primary'}]
            }
            
            response = self.service.freebusy().query(body=body).execute()
            
            busy_times = response.get('calendars', {}).get('primary', {}).get('busy', [])
            
            for busy_period in busy_times:
                busy_start = datetime.fromisoformat(busy_period['start'].replace('Z', '+00:00'))
                busy_end = datetime.fromisoformat(busy_period['end'].replace('Z', '+00:00'))
                
                if start_utc < busy_end and end_utc > busy_start:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return False
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime,
                    description: str = "", location: str = "") -> Dict[str, Any]:
        """Create a calendar event"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            if not self.check_availability(start_time, end_time):
                raise ValueError("Time slot is not available")
            
            start_utc = start_time.astimezone(pytz.utc)
            end_utc = end_time.astimezone(pytz.utc)

            event = {
                'summary': title,
                'description': description,
                'location': location,
                'start': {
                    'dateTime': start_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_utc.isoformat(),
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': True,
                },
            }
            
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            logger.info(f"Event created: {created_event.get('id')}")
            
            return {
                'id': created_event.get('id'),
                'title': title,
                'start': start_utc.isoformat(),
                'end': end_utc.isoformat(),
                'html_link': created_event.get('htmlLink'),
                'status': 'created'
            }
            
        except HttpError as e:
            logger.error(f"HTTP error creating event: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            raise
    
    def update_event(self, event_id: str, title: Optional[str] = None,
                    start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                    description: Optional[str] = None, location: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing calendar event"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            existing_event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            if title is not None:
                existing_event['summary'] = title
            if description is not None:
                existing_event['description'] = description
            if location is not None:
                existing_event['location'] = location
            if start_time is not None:
                existing_event['start'] = {
                    'dateTime': start_time.astimezone(pytz.utc).isoformat(),
                    'timeZone': 'UTC',
                }
            if end_time is not None:
                existing_event['end'] = {
                    'dateTime': end_time.astimezone(pytz.utc).isoformat(),
                    'timeZone': 'UTC',
                }
            
            if start_time and end_time:
                if not self.check_availability(start_time, end_time):
                    raise ValueError("New time slot is not available")
            
            updated_event = self.service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=existing_event
            ).execute()
            
            logger.info(f"Event updated: {event_id}")
            
            return {
                'id': updated_event.get('id'),
                'title': updated_event.get('summary'),
                'start': updated_event['start'].get('dateTime'),
                'end': updated_event['end'].get('dateTime'),
                'html_link': updated_event.get('htmlLink'),
                'status': 'updated'
            }
            
        except HttpError as e:
            logger.error(f"HTTP error updating event: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating event: {str(e)}")
            raise
    
    def delete_event(self, event_id: str) -> Dict[str, Any]:
        """Delete a calendar event"""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            logger.info(f"Event deleted: {event_id}")
            
            return {
                'id': event_id,
                'status': 'deleted'
            }
            
        except HttpError as e:
            logger.error(f"HTTP error deleting event: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error deleting event: {str(e)}")
            raise
    
    def find_free_slots(self, date_range: Tuple[datetime, datetime], duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """Find free time slots within a date range using freebusy query."""
        try:
            if not self.is_authenticated():
                raise ValueError("Not authenticated")
            
            start_dt, end_dt = date_range

            if start_dt.tzinfo is None:
                start_dt = pytz.utc.localize(start_dt)
            if end_dt.tzinfo is None:
                end_dt = pytz.utc.localize(end_dt)

            body = {
                "timeMin": start_dt.astimezone(pytz.utc).isoformat(),
                "timeMax": end_dt.astimezone(pytz.utc).isoformat(),
                "items": [{"id": "primary"}],
                "timeZone": "UTC"
            }

            freebusy_result = self.service.freebusy().query(body=body).execute()
            busy_periods = freebusy_result.get('calendars', {}).get('primary', {}).get('busy', [])

            available_slots = []
            
            all_busy_periods = [{'start': start_dt.astimezone(pytz.utc).isoformat(), 'end': start_dt.astimezone(pytz.utc).isoformat()}]
            all_busy_periods.extend(busy_periods)
            all_busy_periods.append({'start': end_dt.astimezone(pytz.utc).isoformat(), 'end': end_dt.astimezone(pytz.utc).isoformat()})

            all_busy_periods.sort(key=lambda x: x['start'])

            for i in range(len(all_busy_periods) - 1):
                free_period_start = datetime.fromisoformat(all_busy_periods[i]['end'].replace('Z', '+00:00'))
                free_period_end = datetime.fromisoformat(all_busy_periods[i+1]['start'].replace('Z', '+00:00'))

                current_slot = free_period_start
                while current_slot + timedelta(minutes=duration_minutes) <= free_period_end:
                    slot_start_utc = current_slot
                    slot_end_utc = current_slot + timedelta(minutes=duration_minutes)
                    
                    available_slots.append({
                        'start': slot_start_utc.astimezone(start_dt.tzinfo),
                        'end': slot_end_utc.astimezone(start_dt.tzinfo),
                    })
                    current_slot += timedelta(minutes=duration_minutes)
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Error finding free slots: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            if not self.is_authenticated():
                return {"status": "not_authenticated", "message": "Service not authenticated"}
            
            calendar_list = self.service.calendarList().list(maxResults=1).execute()
            
            return {
                "status": "healthy",
                "authenticated": True,
                "primary_calendar_found": len(calendar_list.get('items', [])) > 0
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "authenticated": self.credentials is not None
            }

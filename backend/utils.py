import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import pytz

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('calendar_assistant.log'),
            logging.StreamHandler()
        ]
    )

class DateTimeParser:
    """Advanced date and time parsing with natural language support"""
    
    def __init__(self):
        self.relative_patterns = {
            'today': 0,
            'tomorrow': 1,
            'day after tomorrow': 2,
            'next week': 7,
            'this week': 0,
            'next month': 30,
            'this month': 0,
        }
        
        self.weekday_patterns = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6,
        }
        
        # Updated time periods with comprehensive mappings
        self.time_patterns = {
            'morning': (5, 12),      # 5:00 AM - 11:59 AM
            'afternoon': (12, 18),   # 12:00 PM - 5:59 PM
            'evening': (18, 21),     # 6:00 PM - 8:59 PM
            'night': (21, 24),       # 9:00 PM - 11:59 PM
            'midnight': (0, 0),      # 12:00 AM (exact)
            'midday': (12, 12),      # 12:00 PM (exact)
            'noon': (12, 12),        # 12:00 PM (exact)
            'dawn': (5, 6),          # 5:00 AM - 5:59 AM
            'dusk': (18, 19),        # 6:00 PM - 6:59 PM
            'twilight': (19, 20),    # 7:00 PM - 7:59 PM
        }
    
    def parse(self, text: str, user_timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        """Parse date and time from natural language text"""
        try:
            text = text.lower().strip()
            duration_minutes = extract_duration(text) or 30
            
            # Try to extract time range first
            range_result = self._parse_time_range(text, user_timezone)
            if range_result:
                return range_result
            
            # Try to parse single datetime
            single_result = self._parse_single_datetime(text, user_timezone, duration_minutes)
            if single_result:
                return single_result
            
            return None
            
        except Exception as e:
            logging.error(f"Error parsing datetime: {str(e)}")
            return None
    
    def _parse_time_range(self, text: str, user_timezone: str) -> Optional[Dict[str, Any]]:
        """Parse time ranges like '3-5 PM', 'between 2 and 4 PM', including multi-day ranges."""
        range_patterns = [
            r'between\s+(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*and\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?',
            r'from\s+(\d{1,2}(?::\d{2})?)\s*(am|pm)?\s*to\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)?',
            r'(\d{1,2}(?::\d{2})?)\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)',
        ]

        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Standardize handling of matched groups
                if len(groups) == 4:
                    start_time_str, start_period, end_time_str, end_period = groups
                elif len(groups) == 3:
                    start_time_str, end_time_str, end_period = groups
                    start_period = None # Will be inferred later
                else:
                    continue

                # Infer start period if missing
                if not start_period and end_period:
                    start_period = end_period
                
                start_time = self._parse_time_string(start_time_str, start_period)
                end_time = self._parse_time_string(end_time_str, end_period)

                if start_time and end_time:
                    user_tz = pytz.timezone(user_timezone)
                    now = datetime.now(user_tz)

                    # Determine the date range (e.g., 'this week', 'next month')
                    start_date_part, end_date_part = self._get_date_range_from_text(text, now)

                    start_datetime = start_date_part.replace(
                        hour=start_time[0], minute=start_time[1], second=0, microsecond=0
                    )
                    end_datetime = end_date_part.replace(
                        hour=end_time[0], minute=end_time[1], second=0, microsecond=0
                    )

                    # Ensure timezone localization
                    if start_datetime.tzinfo is None:
                        start_datetime = user_tz.localize(start_datetime)
                    if end_datetime.tzinfo is None:
                        end_datetime = user_tz.localize(end_datetime)

                    return {
                        "start": start_datetime,
                        "end": end_datetime,
                        "is_range": True,
                        "text": text
                    }
        return None

    def _get_date_range_from_text(self, text: str, now: datetime) -> Tuple[datetime, datetime]:
        """Identifies a date range like 'this week' or 'next month' from text."""
        text = text.lower()
        
        if 'this week' in text:
            start_of_week = now - timedelta(days=now.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week, end_of_week
        
        if 'next week' in text:
            start_of_next_week = now + timedelta(days=(7 - now.weekday()))
            end_of_next_week = start_of_next_week + timedelta(days=6)
            return start_of_next_week, end_of_next_week

        # Default to the date parsed from the text, or today if no date is found
        date_part = self._parse_date_part(text, now.tzinfo.zone)
        return date_part, date_part

    
    def _parse_single_datetime(self, text: str, user_timezone: str, duration_minutes: int) -> Optional[Dict[str, Any]]:
        """Parse single datetime expressions"""
        
        time_regex = r'\d{1,2}:\d{2}|\d{1,2}\s*(am|pm)'
        has_specific_time = re.search(time_regex, text, re.IGNORECASE)
        has_time_period = any(period in text for period in self.time_patterns.keys())
        
        date_part = self._parse_date_part(text, user_timezone)
        if not date_part:
            return None
            
        if not has_specific_time and not has_time_period:
            if any(word in text for word in ['availability', 'available', 'free', 'openings', 'slots']):
                start_of_day = date_part.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = date_part.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                return {
                    "start": start_of_day,
                    "end": end_of_day,
                    "is_range": True,
                    "is_full_day": True,
                    "text": text
                }
        
        if has_time_period:
            for phrase, (start_hour, end_hour) in self.time_patterns.items():
                if phrase in text:
                    if phrase in ['midnight', 'midday', 'noon']:
                        exact_datetime = date_part.replace(
                            hour=start_hour, minute=0, second=0, microsecond=0
                        )
                        return {
                            "start": exact_datetime,
                            "end": exact_datetime + timedelta(minutes=duration_minutes),
                            "is_range": False,
                            "duration_minutes": duration_minutes,
                            "text": text
                        }
                    else:
                        start_of_period = date_part.replace(
                            hour=start_hour, minute=0, second=0, microsecond=0
                        )
                        end_of_period = date_part.replace(
                            hour=end_hour, minute=0, second=0, microsecond=0
                        )
                        
                        return {
                            "start": start_of_period,
                            "end": end_of_period,
                            "is_range": True,
                            "text": text
                        }
        
        if has_specific_time:
            try:
                parsed_dt = date_parser.parse(text, fuzzy=True, default=date_part)
                if parsed_dt:
                    user_tz = pytz.timezone(user_timezone)
                    if parsed_dt.tzinfo is None:
                        parsed_dt = user_tz.localize(parsed_dt)
                    
                    return {
                        "start": parsed_dt,
                        "end": parsed_dt + timedelta(minutes=duration_minutes),
                        "is_range": False,
                        "duration_minutes": duration_minutes,
                        "text": text
                    }
            except Exception:
                pass
        
        try:
            parsed_dt = date_parser.parse(text, fuzzy=True, default=date_part)
            if parsed_dt:
                user_tz = pytz.timezone(user_timezone)
                if parsed_dt.tzinfo is None:
                    parsed_dt = user_tz.localize(parsed_dt)
                
                return {
                    "start": parsed_dt,
                    "end": parsed_dt + timedelta(minutes=duration_minutes),
                    "is_range": False,
                    "duration_minutes": duration_minutes,
                    "text": text
                }
        except:
            pass
        
        return None
    
    def _parse_date_part(self, text: str, user_timezone: str) -> Optional[datetime]:
        """Parse date part from text with proper timezone handling"""
        
        user_tz = pytz.timezone(user_timezone)
        now = datetime.now(user_tz)
        
        logging.debug(f"_parse_date_part: Processing text='{text}', now='{now}' in {user_timezone}")

        for phrase, days in self.relative_patterns.items():
            if phrase in text:
                target_date = now + timedelta(days=days)
                logging.debug(f"_parse_date_part: Found relative date '{phrase}', target_date='{target_date}'")
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for weekday, day_num in self.weekday_patterns.items():
            if weekday in text:
                current_weekday = now.weekday()
                days_ahead = day_num - current_weekday
                
                if days_ahead <= 0:
                    days_ahead += 7
                
                if 'next' in text:
                    days_ahead += 7
                
                target_date = now + timedelta(days=days_ahead)
                logging.debug(f"_parse_date_part: Found weekday '{weekday}', target_date='{target_date}'")
                return target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            parsed_date = date_parser.parse(text, fuzzy=True, default=now)
            
            if parsed_date:
                if parsed_date.tzinfo is None:
                    parsed_date = user_tz.localize(parsed_date)
                return parsed_date
        except (ValueError, TypeError):
            pass
        
        return now

    def _parse_time_part(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse time part from text"""
        
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',
            r'(\d{1,2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})',
            r'(\d{4})'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 4:
                    hour_min = match.group(1)
                    hour = int(hour_min[:2])
                    minute = int(hour_min[2:])
                    return (hour, minute)
                elif len(match.groups()) == 3:
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    period = match.group(3).lower()
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    return (hour, minute)
                elif len(match.groups()) == 2:
                    hour = int(match.group(1))
                    period = match.group(2).lower()
                    
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    return (hour, 0)
        
        return None
    
    def _parse_time_string(self, time_str: str, period: str) -> Optional[Tuple[int, int]]:
        """Parse time string with period"""
        try:
            if ':' in time_str:
                hour, minute = map(int, time_str.split(':'))
            else:
                hour = int(time_str)
                minute = 0
            
            if period and period.lower() == 'pm' and hour != 12:
                hour += 12
            elif period and period.lower() == 'am' and hour == 12:
                hour = 0
            
            return (hour, minute)
        except:
            return None

def extract_duration(text: str) -> Optional[int]:
    """Extract duration in minutes from text"""
    
    if re.search(r'\b(a|an|one)\s+hour\b', text, re.IGNORECASE):
        return 60

    hour_patterns = [
        r'(\d+)\s*-?\s*h\b',
        r'(\d+)\s*-?\s*hr',
        r'(\d+)\s*-?\s*hours?'
    ]

    minute_patterns = [
        r'(\d+)\s*-?\s*m\b',
        r'(\d+)\s*-?\s*min(ute)?s?'
    ]

    for pattern in hour_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1)) * 60

    for pattern in minute_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
            
    return None

def normalize_time_format(dt: datetime) -> str:
    """Normalize datetime to user-friendly format"""
    return dt.strftime('%A, %B %d at %I:%M %p')

def get_relative_date(text: str, base_date: Optional[datetime] = None) -> Optional[datetime]:
    """Get relative date from text"""
    if not base_date:
        base_date = datetime.now(timezone.utc)
    
    text = text.lower()
    
    if 'today' in text:
        return base_date
    elif 'tomorrow' in text:
        return base_date + timedelta(days=1)
    elif 'yesterday' in text:
        return base_date - timedelta(days=1)
    elif 'next week' in text:
        return base_date + timedelta(weeks=1)
    elif 'this week' in text:
        return base_date
    elif 'next month' in text:
        return base_date + relativedelta(months=1)
    elif 'this month' in text:
        return base_date
    
    return None

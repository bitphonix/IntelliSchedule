from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
import uvicorn
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import pytz

from calendar_service import CalendarService
from agent import CalendarAgent
from utils import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Calendar Assistant API",
    description="Conversational AI Calendar Assistant with Google Calendar Integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Global services
import os

# Define paths relative to the main.py file
backend_dir = os.path.dirname(os.path.abspath(__file__))
credentials_file_path = os.path.join(backend_dir, 'credentials.json')
token_file_path = os.path.join(backend_dir, 'token.pickle')

calendar_service = CalendarService(
    credentials_path=credentials_file_path,
    token_path=token_file_path
)
agent = CalendarAgent(calendar_service)

# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    user_timezone: Optional[str] = "UTC"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    needs_confirmation: bool = False
    confirmation_data: Optional[Dict[str, Any]] = None
    available_slots: Optional[List[Dict[str, Any]]] = None

class BookingConfirmation(BaseModel):
    session_id: str
    confirmed: bool
    confirmation_data: Dict[str, Any]

class CalendarEvent(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = ""
    location: Optional[str] = ""

# Session storage (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}

def get_session(session_id: str) -> Dict[str, Any]:
    """Get or create session data"""
    if session_id not in sessions:
        # If the global service is already authenticated, carry that state into the new session
        is_authenticated = calendar_service.is_authenticated()
        
        sessions[session_id] = {
            "conversation_history": [],
            "context": {},
            "authenticated": is_authenticated,
            "calendar_service": calendar_service if is_authenticated else None
        }
        
        if is_authenticated:
            logger.info(f"New session {session_id} created with existing authentication.")
            
    return sessions[session_id]

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Calendar Assistant API",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/auth/url")
async def get_auth_url(session_id: str = "default"):
    """Get Google OAuth authorization URL"""
    try:
        session = get_session(session_id)
        auth_url = calendar_service.get_auth_url()
        return {"auth_url": auth_url, "session_id": session_id}
    except Exception as e:
        logger.error(f"Error getting auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback")
async def auth_callback(code: str, session_id: str = "default"):
    try:
        session = get_session(session_id)
        calendar_service.authenticate_with_code(code)
        session["authenticated"] = True
        session["calendar_service"] = calendar_service
        
        # Update agent with authenticated service
        agent.calendar_service = calendar_service
        
        # Redirect back to frontend with session info
        frontend_url = os.getenv("FRONTEND_URL", "https://intellischedule-bzuqu73t8jaz8ywvk5rzh2.streamlit.app/")
        return RedirectResponse(
            url=f"{frontend_url}?session_id={session_id}&auth=success",
            status_code=302
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/status")
async def auth_status(session_id: str = "default"):
    """Check authentication status"""
    session = get_session(session_id)
    return {
        "authenticated": session.get("authenticated", False),
        "session_id": session_id
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    """Main chat endpoint for conversational AI"""
    try:
        session = get_session(message.session_id)
        
        if not session.get("authenticated", False):
            return ChatResponse(
                response="Please connect to your Google Calendar first to use the assistant.",
                session_id=message.session_id,
                needs_confirmation=False,
                confirmation_data=None,
                available_slots=None
            )
        
        # --- MODIFICATION START ---
        # Get history and add the new message
        history = session.get("conversation_history", [])
        history.append({
            "role": "user",
            "content": message.message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Process message with agent, passing the full history
        response_data = await agent.process_message(
            session_id=message.session_id,
            user_timezone=message.user_timezone,
            conversation_history=history
        )
        
        # The agent now returns the full updated history
        session["conversation_history"] = response_data.get("conversation_history", [])
        session["context"] = response_data.get("context", {})

        # The last message from the history is the agent's latest response
        assistant_response = ""
        if session["conversation_history"]:
            last_message = session["conversation_history"][-1]
            if last_message["role"] == "assistant":
                assistant_response = last_message["content"]
        # --- MODIFICATION END ---
        
        return ChatResponse(
            response=assistant_response, # Use the response from the history
            session_id=message.session_id,
            needs_confirmation=response_data.get("needs_confirmation", False),
            confirmation_data=response_data.get("confirmation_data"),
            available_slots=response_data.get("available_slots")
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return ChatResponse(
            response=f"I apologize, but I encountered an error: {str(e)}. Please try again.",
            session_id=message.session_id,
            needs_confirmation=False,
            confirmation_data=None,
            available_slots=None
        )

@app.post("/confirm-booking")
async def confirm_booking(confirmation: BookingConfirmation):
    """Confirm and execute booking"""
    try:
        session = get_session(confirmation.session_id)
        
        if not session.get("authenticated", False):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        if not confirmation.confirmed:
            return {
                "status": "cancelled",
                "message": "Booking cancelled. How else can I help you?"
            }
        
        # Execute booking
        result = await agent.execute_booking(
            confirmation.confirmation_data,
            session_id=confirmation.session_id
        )
        
        # Update conversation history
        session["conversation_history"].append({
            "role": "assistant",
            "content": result["message"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Booking confirmation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calendar/events")
async def get_calendar_events(
    session_id: str = "default",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get calendar events for a date range"""
    try:
        session = get_session(session_id)
        
        if not session.get("authenticated", False):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get user's timezone from session or default to UTC
        user_timezone_str = session.get("user_timezone", "UTC")
        user_tz = pytz.timezone(user_timezone_str)

        now = datetime.now(user_tz)

        # Set default start and end dates if not provided
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            if start_dt.tzinfo is None:
                start_dt = user_tz.localize(start_dt)
        else:
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) # Beginning of today

        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            if end_dt.tzinfo is None:
                end_dt = user_tz.localize(end_dt)
        else:
            end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999) # End of today
        
        events = calendar_service.get_events(start_dt, end_dt)
        return {"events": events, "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calendar/availability")
async def get_availability(
    session_id: str = "default",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    duration_minutes: int = 30
):
    """Get available time slots"""
    try:
        session = get_session(session_id)
        
        if not session.get("authenticated", False):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get user's timezone from session or default to UTC
        user_timezone_str = session.get("user_timezone", "UTC")
        user_tz = pytz.timezone(user_timezone_str)

        now = datetime.now(user_tz)

        # Set default start and end dates if not provided
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            if start_dt.tzinfo is None:
                start_dt = user_tz.localize(start_dt)
        else:
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) # Beginning of today

        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            if end_dt.tzinfo is None:
                end_dt = user_tz.localize(end_dt)
        else:
            end_dt = now + timedelta(days=7) # 7 days from now
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999) # End of the 7th day
        
        availability = calendar_service.get_availability(
            start_dt, end_dt, duration_minutes
        )
        return {"availability": availability, "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Error fetching availability: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/book")
async def book_event(event: CalendarEvent, session_id: str = "default"):
    """Book a calendar event"""
    try:
        session = get_session(session_id)
        
        if not session.get("authenticated", False):
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        result = calendar_service.create_event(
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            description=event.description,
            location=event.location
        )
        
        return {
            "status": "success",
            "event_id": result["id"],
            "message": f"Event '{event.title}' booked successfully!",
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Booking error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation-history")
async def get_conversation_history(session_id: str = "default"):
    """Get conversation history for a session"""
    session = get_session(session_id)
    return {
        "history": session.get("conversation_history", []),
        "session_id": session_id
    }

@app.delete("/session")
async def clear_session(session_id: str = "default"):
    """Clear session data"""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "cleared", "session_id": session_id}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "calendar_api": calendar_service.health_check(),
            "agent": agent.health_check(),
        },
        "active_sessions": len(sessions),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
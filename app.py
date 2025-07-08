import streamlit as st
import requests
import json
from datetime import datetime, timezone
import time
import pytz
from typing import Dict, List, Any, Optional

# Page config
st.set_page_config(
    page_title="Calendar Assistant",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
BACKEND_URL = "http://localhost:8000"
DEFAULT_TIMEZONE = "UTC"

# Custom CSS
st.markdown("""
    <style>
    .chat-message {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        max-width: 80%;
        border: 1px solid #ddd;
    }
    
    .user-message {
        background-color: #e3f2fd;
        margin-left: auto;
        text-align: right;
        color: #1565c0;
        font-weight: 500;
    }
    
    .assistant-message {
        background-color: #f8f9fa;
        margin-right: auto;
        color: #212529;
        border-left: 4px solid #007bff;
    }
    
    .error-message {
        background-color: #ffebee;
        color: #c62828;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border: 1px solid #ef5350;
    }
    
    .success-message {
        background-color: #e8f5e8;
        color: #2e7d32;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border: 1px solid #4caf50;
    }
    
    .info-message {
        background-color: #e1f5fe;
        color: #0277bd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border: 1px solid #03a9f4;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'session_id' not in st.session_state:
        st.session_state.session_id = "default" 
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'user_timezone' not in st.session_state:
        st.session_state.user_timezone = DEFAULT_TIMEZONE
    
    if 'pending_confirmation' not in st.session_state:
        st.session_state.pending_confirmation = None
    
    if 'auth_url' not in st.session_state:
        st.session_state.auth_url = None

# API functions
def make_api_request(endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
    """Make API request to backend"""
    try:
        url = f"{BACKEND_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, params=data)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url, params=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.RequestException as e:
        st.error(f"API request failed: {str(e)}")
        return {"error": str(e)}
    
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return {"error": str(e)}

def check_auth_status() -> bool:
    """Check authentication status"""
    result = make_api_request(f"/auth/status?session_id={st.session_state.session_id}")
    return result.get("authenticated", False)

def get_auth_url() -> str:
    """Get Google OAuth URL"""
    result = make_api_request(f"/auth/url?session_id={st.session_state.session_id}")
    return result.get("auth_url", "")

def send_message(message: str) -> Dict:
    """Send message to chat endpoint"""
    data = {
        "message": message,
        "session_id": st.session_state.session_id,
        "user_timezone": st.session_state.user_timezone
    }
    
    return make_api_request("/chat", method="POST", data=data)

def confirm_booking(confirmed: bool, confirmation_data: Dict) -> Dict:
    """Confirm or cancel booking"""
    data = {
        "session_id": st.session_state.session_id,
        "confirmed": confirmed,
        "confirmation_data": confirmation_data
    }
    
    return make_api_request("/confirm-booking", method="POST", data=data)

def get_calendar_events(start_date: str = None, end_date: str = None) -> Dict:
    """Get calendar events"""
    params = {"session_id": st.session_state.session_id}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    
    return make_api_request("/calendar/events", data=params)

def get_availability(start_date: str = None, end_date: str = None, duration: int = 30) -> Dict:
    """Get availability"""
    params = {
        "session_id": st.session_state.session_id,
        "duration_minutes": duration
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    
    return make_api_request("/calendar/availability", data=params)

# UI Components
def render_sidebar():
    """Render sidebar with controls"""
    with st.sidebar:
        st.header("Calendar Assistant")
        
        # Authentication status
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("🔐 Authentication")
            
            if st.session_state.authenticated:
                st.success("✅ Connected to Google Calendar")
                
                if st.button("🔄 Refresh Status"):
                    st.session_state.authenticated = check_auth_status()
                    st.rerun()
                
                if st.button("🚪 Disconnect"):
                    st.session_state.authenticated = False
                    st.rerun()
            else:
                st.warning("❌ Not connected to Google Calendar")
                
                if st.button("🔗 Connect Google Calendar"):
                    auth_url = get_auth_url()
                    if auth_url:
                        st.session_state.auth_url = auth_url
                        st.markdown(f'<a href="{auth_url}" target="_blank">Click here to authenticate →</a>', unsafe_allow_html=True)
                        st.info("After authentication, refresh this page.")
                    else:
                        st.error("Failed to get authentication URL")
                
                # Check auth status periodically
                if st.button("🔄 Check Status"):
                    st.session_state.authenticated = check_auth_status()
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Timezone selection
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("🌍 Timezone")
            
            common_timezones = [
                "UTC", 
                "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
                "Europe/London", "Europe/Paris", "Europe/Berlin", 
                "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney",
                "Asia/Kolkata"
            ]
            
            selected_tz = st.selectbox(
                "Select your timezone:",
                options=common_timezones,
                index=common_timezones.index(st.session_state.user_timezone)
            )
            
            if selected_tz != st.session_state.user_timezone:
                st.session_state.user_timezone = selected_tz
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Quick actions
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("⚡ Quick Actions")
            
            if st.button("📅 Check Today's Schedule"):
                if st.session_state.authenticated:
                    with st.spinner("Checking schedule..."):
                        events = get_calendar_events()
                        if events.get("events"):
                            st.success(f"Found {len(events['events'])} events today")
                        else:
                            st.info("No events found for today")
                else:
                    st.warning("Please authenticate first")
            
            if st.button("🔍 Show Availability"):
                if st.session_state.authenticated:
                    with st.spinner("Checking availability..."):
                        availability = get_availability()
                        if availability.get("availability"):
                            st.success(f"Found {len(availability['availability'])} available slots")
                        else:
                            st.info("No available slots found")
                else:
                    st.warning("Please authenticate first")
            
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.session_state.pending_confirmation = None
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Session info
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.subheader("ℹ️ Session Info")
            
            st.text(f"Session ID: {st.session_state.session_id[-8:]}")
            st.text(f"Messages: {len(st.session_state.messages)}")
            st.text(f"Timezone: {st.session_state.user_timezone}")
            st.text(f"Authenticated: {'Yes' if st.session_state.authenticated else 'No'}")
            
            st.markdown('</div>', unsafe_allow_html=True)

def render_chat_message(message: Dict, is_user: bool = False):
    """Render a chat message"""
    css_class = "user-message" if is_user else "assistant-message"
    icon = "🧑" if is_user else "🤖"
    
    st.markdown(f"""
    <div class="chat-message {css_class}">
        {icon} {'You' if is_user else 'Assistant'}:
        {message.get('content', '')}
    </div>
    """, unsafe_allow_html=True)

def render_confirmation_dialog(confirmation_data: Dict):
    """Render booking confirmation dialog"""
    st.markdown('<div class="info-message">', unsafe_allow_html=True)
    st.markdown("### 📅 Booking Confirmation")
    
    # Parse datetime
    start_time = datetime.fromisoformat(confirmation_data["start_time"].replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(confirmation_data["end_time"].replace('Z', '+00:00'))
    
    # Convert to user timezone
    user_tz = pytz.timezone(st.session_state.user_timezone)
    start_local = start_time.astimezone(user_tz)
    end_local = end_time.astimezone(user_tz)
    
    st.markdown(f"""
    **Title:** {confirmation_data.get('title', 'Meeting')}  
    **Date:** {start_local.strftime('%A, %B %d, %Y')}  
    **Time:** {start_local.strftime('%I:%M %p')} - {end_local.strftime('%I:%M %p')} ({st.session_state.user_timezone})  
    **Duration:** {confirmation_data.get('duration_minutes', 30)} minutes
    """)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Confirm Booking", key="confirm_yes"):
            with st.spinner("Booking appointment..."):
                result = confirm_booking(True, confirmation_data)
                
                if result.get("status") == "success":
                    st.session_state.messages.append({
                        "content": result.get("message", "Booking confirmed!"),
                        "is_user": False,
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.pending_confirmation = None
                    st.success("Booking confirmed!")
                else:
                    st.error(f"Booking failed: {result.get('message', 'Unknown error')}")
                
                st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key="confirm_no"):
            result = confirm_booking(False, confirmation_data)
            st.session_state.messages.append({
                "content": "Booking cancelled. How else can I help you?",
                "is_user": False,
                "timestamp": datetime.now().isoformat()
            })
            st.session_state.pending_confirmation = None
            st.rerun()

def render_chat_interface():
    """Render main chat interface"""
    st.header("💬 Chat with Your Calendar Assistant")
    
    # Check authentication
    if not st.session_state.authenticated:
        st.markdown('<div class="info-message">', unsafe_allow_html=True)
        st.markdown("⚠️ **Please authenticate with Google Calendar first using the sidebar.**")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Chat container
    chat_container = st.container()
    
    with chat_container:
        # Display messages
        for message in st.session_state.messages:
            render_chat_message(message, message.get("is_user", False))
        
        # Display confirmation dialog if needed
        if st.session_state.pending_confirmation:
            render_confirmation_dialog(st.session_state.pending_confirmation)
    
    # Chat input
    with st.form(key="chat_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_input = st.text_input(
                "Type your message...",
                placeholder="e.g., 'Book a meeting tomorrow at 2 PM' or 'What's my availability this week?'",
                key="chat_input"
            )
        
        with col2:
            submit_button = st.form_submit_button("Send 📤")
    
    # Process message
    if submit_button and user_input:
        # Add user message
        st.session_state.messages.append({
            "content": user_input,
            "is_user": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send to backend
        with st.spinner("Thinking..."):
            response = send_message(user_input)
            
            if response.get("error"):
                st.error(f"Error: {response['error']}")
            else:
                # Add assistant response
                st.session_state.messages.append({
                    "content": response.get("response", "Sorry, I couldn't process that."),
                    "is_user": False,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Handle confirmation
                if response.get("needs_confirmation") and response.get("confirmation_data"):
                    st.session_state.pending_confirmation = response["confirmation_data"]
        
        st.rerun()
    
    # Sample prompts
    st.markdown("### 💡 Try these examples:")
    
    example_prompts = [
        "What's my availability tomorrow?",
        "Book a meeting next Friday at 2 PM",
        "Schedule a call between 3-5 PM this week",
        "Any openings on Monday?",
        "Book a 1-hour meeting tomorrow morning"
    ]
    
    cols = st.columns(len(example_prompts))
    for i, prompt in enumerate(example_prompts):
        with cols[i]:
            if st.button(prompt, key=f"example_{i}"):
                # Simulate clicking the example
                st.session_state.messages.append({
                    "content": prompt,
                    "is_user": True,
                    "timestamp": datetime.now().isoformat()
                })
                
                with st.spinner("Processing..."):
                    response = send_message(prompt)
                    
                    if response.get("error"):
                        st.error(f"Error: {response['error']}")
                    else:
                        st.session_state.messages.append({
                            "content": response.get("response", "Sorry, I couldn't process that."),
                            "is_user": False,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        if response.get("needs_confirmation") and response.get("confirmation_data"):
                            st.session_state.pending_confirmation = response["confirmation_data"]
                
                st.rerun()

# Main app
def main():
    """Main application"""
    init_session_state()
    
    # Check authentication status on startup
    if not st.session_state.authenticated:
        st.session_state.authenticated = check_auth_status()
    
    # Render UI
    render_sidebar()
    render_chat_interface()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div class="info-message">
        Built with ❤️ using Streamlit, FastAPI, and Google Calendar API
        <br>
        Calendar Assistant v1.0 - Conversational AI for Smart Scheduling
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
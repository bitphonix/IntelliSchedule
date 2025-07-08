Calendar Assistant - Conversational AI for Smart Scheduling
A sophisticated conversational AI agent that helps users book appointments on their Google Calendar through natural language conversations. Built with FastAPI, LangGraph, and Streamlit.
🚀 Features

Natural Language Understanding: Understands various date/time formats and flexible time references
Real-time Calendar Integration: Connects with Google Calendar API for live availability checking
Smart Conversation Flow: Multi-turn conversations with context preservation
Conflict Resolution: Prevents double bookings and suggests alternatives
Timezone Support: Handles multiple timezones for global users
Confirmation Workflow: Always confirms details before booking
Edge Case Handling: Comprehensive handling of various booking scenarios

🛠️ Tech Stack

Backend: FastAPI with Python
AI Framework: LangGraph for conversational AI
Frontend: Streamlit for interactive chat interface
Calendar API: Google Calendar API with OAuth2
Natural Language: Custom datetime parsing with dateutil
Authentication: Google OAuth2 flow

📋 Prerequisites

Python 3.8+
Google Cloud Project with Calendar API enabled
OpenAI API key for LangGraph
Google OAuth2 credentials

🔧 Installation & Setup
1. Clone the Repository
git clone https://github.com/yourusername/calendar-assistant.git
cd calendar-assistant

2. Create Virtual Environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install Dependencies
pip install -r requirements.txt

4. Google Calendar API Setup

Go to Google Cloud Console
Create a new project or select existing one
Enable Google Calendar API
Create OAuth2 credentials (Desktop application)
Download the credentials file as credentials.json
Place it in the project root directory

5. Environment Configuration

Copy .env.example to .env
Fill in your credentials:

cp .env.example .env

Edit .env:
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
OPENAI_API_KEY=your_openai_api_key

🚀 Running the Application
Method 1: Start Both Services
# Terminal 1: Start Backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend
streamlit run app.py --server.port 8501

Method 2: Development Mode
# Backend with auto-reload
cd backend
python -m uvicorn main:app --reload

# Frontend with auto-reload
streamlit run app.py

🔑 First-Time Authentication

Open the Streamlit app (usually at http://localhost:8501)
Click "Connect Google Calendar" in the sidebar
Follow the OAuth flow to authenticate
Return to the app - you're now connected!

💬 Usage Examples
Basic Booking
User: "Book a meeting tomorrow at 2 PM"
Assistant: "Perfect! I can book a 30-minute meeting for tomorrow, December 15 at 2:00 PM. Shall I go ahead and book this for you?"

Availability Check
User: "What's my availability this Friday?"
Assistant: "You're completely free on Friday, December 15. Available slots: 9:00 AM – 6:00 PM. Would you like to book one?"

Time Range Booking
User: "Schedule a call between 3-5 PM next week"
Assistant: "Here are available 30-min slots between 3–5 PM next week:
• Monday, Dec 18: 3:30 PM
• Wednesday, Dec 20: You're completely free!
• Friday, Dec 22: 4:00 PM
Would you like to book one of these?"

Flexible Scheduling
User: "Any openings tomorrow afternoon?"
Assistant: "Yes! Tomorrow afternoon you have these available slots:
• 1:00 PM, 2:00 PM, 3:30 PM, 4:00 PM, 5:00 PM
Which time works best for you?"

🧠 Supported Natural Language Formats
Date Formats

tomorrow, today, next Friday
December 15, Dec 15, 2024
next week, this weekend
5 July 2025, 05 July

Time Formats

2 PM, 14:00, 2:30 PM
afternoon, morning, evening
between 3-5 PM, from 2 to 4 PM

Duration Formats

30 minutes, 1 hour, 2 hrs
90 mins, 1h 30m

🔍 Edge Cases Handled
✅ Relative Dates: "tomorrow", "next week", "3–5 PM"✅ Full Day Availability: "You're free all day on Friday"✅ Partial Availability: Shows only actual free time slots✅ Busy Slot Conflicts: Suggests closest alternatives✅ Time Range Booking: Supports multi-hour blocks✅ Various Time Formats: "5 PM", "17:00", "5:00PM"✅ Double Booking Prevention: Real-time conflict checking✅ Timezone Handling: Accurate timezone conversion✅ Conversation Memory: Maintains context across turns  
🏗️ Architecture
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Streamlit UI  │────│   FastAPI API    │────│ Google Calendar │
│   (Frontend)    │    │   (Backend)      │    │      API        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                      ┌──────────────────┐
                      │   LangGraph AI   │
                      │   (Agent Logic)  │
                      └──────────────────┘

Backend Components

main.py: FastAPI server with all endpoints
calendar_service.py: Google Calendar API integration
agent.py: LangGraph conversational AI logic
utils.py: Date parsing and helper functions

Frontend Components

app.py: Streamlit chat interface with session management

🐛 Troubleshooting
Common Issues

Authentication Failed

Check Google credentials are correct
Ensure Calendar API is enabled
Verify redirect URI matches OAuth settings


Backend Connection Error

Ensure backend is running on port 8000
Check CORS settings
Verify API endpoints are accessible


Date Parsing Issues

Check timezone settings
Verify dateutil is installed
Review custom parsing logic



Debug Mode
Enable debug logging:
export LOG_LEVEL=DEBUG
uvicorn backend.main:app --reload --log-level debug

📊 API Endpoints

GET / - Health check
GET /auth/url - Get OAuth URL
POST /auth/callback - Handle OAuth callback
POST /chat - Main chat endpoint
POST /confirm-booking - Confirm booking
GET /calendar/events - Get calendar events
GET /calendar/availability - Get availability
POST /calendar/book - Book event directly

🧪 Testing
Run tests:
python -m pytest backend/tests/

🔧 Configuration
Backend Settings

Host: 0.0.0.0
Port: 8000
Auto-reload: Enabled for development

Frontend Settings

Host: localhost
Port: 8501
Page config: Wide layout

📝 Contributing

Fork the repository
Create a feature branch
Make your changes
Add tests if needed
Submit a pull request

📄 License
This project is licensed under the MIT License.
🙏 Acknowledgments

Google Calendar API for calendar integration
LangGraph for conversational AI framework
Streamlit for the amazing UI framework
FastAPI for the robust backend framework


Calendar Assistant v1.0 - Built with ❤️ for smart scheduling
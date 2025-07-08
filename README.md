# IntelliSchedule 🗕️

A smart conversational AI agent for your Google Calendar that understands natural language to intelligently check availability and schedule appointments, simplifying your scheduling workflows.

## ✨ Features

* 🤖 **Natural Language Processing**: Interact with your calendar using everyday language
* 🗕️ **Google Calendar Integration**: Seamless connection to your Google Calendar
* 🔍 **Smart Availability Checking**: Find available time slots quickly
* ⏰ **Intelligent Scheduling**: Book appointments with natural language commands
* 🌍 **Timezone Support**: Handle multiple timezones automatically
* 💬 **Conversational Interface**: Chat-based interaction for intuitive scheduling
* 🔐 **Secure Authentication**: OAuth 2.0 integration with Google
* 📱 **Responsive UI**: Built with Streamlit for a modern web experience

## 🛠️ Tech Stack

### Backend

* **FastAPI**: High-performance web framework
* **LangChain**: AI/ML framework for conversational AI
* **Google Gemini**: Large language model for natural language understanding
* **LangGraph**: Graph-based conversation management
* **Google Calendar API**: Calendar integration
* **Python 3.8+**: Core programming language

### Frontend

* **Streamlit**: Interactive web application framework
* **Custom CSS**: Enhanced UI/UX design

### Key Libraries

* `google-api-python-client`: Google Calendar API integration
* `google-auth-oauthlib`: OAuth 2.0 authentication
* `dateparser`: Natural language date parsing
* `pytz`: Timezone handling
* `uvicorn`: ASGI server

## 🚀 Getting Started

### Prerequisites

* Python 3.8 or higher
* Google Cloud Console account
* Google Calendar API credentials

### Installation

Clone the repository:

```bash
git clone https://github.com/bitphonix/IntelliSchedule.git
cd IntelliSchedule
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set up Google Calendar API:

* Go to Google Cloud Console
* Create a new project or select an existing one
* Enable the Google Calendar API
* Create OAuth 2.0 credentials
* Download the credentials JSON file and save it as `backend/credentials.json`

Configure environment variables:

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration:

```
# Google Calendar API Credentials
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Google Gemini API Key
GOOGLE_API_KEY=your_gemini_api_key_here

# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=True

# Security
SECRET_KEY=your_secret_key_here
```

### Running the Application

Start the backend server:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend (in a new terminal):

```bash
streamlit run app.py
```

Access the application:

* Open your browser and go to `http://localhost:8501`
* Authenticate with Google Calendar
* Start chatting with your calendar assistant!

## 💡 Usage Examples

**Check Availability**

* "What's my availability tomorrow?"
* "Any openings on Monday?"
* "Show me free slots this week"

**Schedule Meetings**

* "Book a meeting tomorrow at 2 PM"
* "Schedule a call between 3-5 PM this week"
* "Book a 1-hour meeting tomorrow morning"

**Natural Language Queries**

* "Do I have any meetings next Friday?"
* "What does my schedule look like today?"
* "Find me a 30-minute slot next week"

## 🏗️ Architecture

```
IntelliSchedule/
├── app.py                 # Streamlit frontend application
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── test_availability.py   # Testing script
└── backend/
    ├── main.py            # FastAPI backend server
    ├── agent.py           # Conversational AI agent
    ├── calendar_service.py # Google Calendar integration
    └── utils.py           # Utility functions
```

## 🔧 API Endpoints

* `GET /` - Health check
* `GET /auth/url` - Get Google OAuth URL
* `GET /auth/callback` - Handle OAuth callback
* `GET /auth/status` - Check authentication status
* `POST /chat` - Main conversational endpoint
* `POST /confirm-booking` - Confirm meeting bookings
* `GET /calendar/events` - Retrieve calendar events
* `GET /calendar/availability` - Check availability
* `POST /calendar/book` - Book new events
* `GET /conversation-history` - Get chat history
* `DELETE /session` - Clear session data
* `GET /health` - Detailed system health

## 🧪 Testing

Test the agent functionality:

```bash
python test_availability.py
```

This script allows you to test the conversational agent's ability to:

* Parse natural language input
* Extract datetime information
* Check calendar availability
* Generate appropriate responses

## 🔒 Security

* **OAuth 2.0**: Secure Google authentication
* **Session Management**: Secure session handling
* **CORS Protection**: Configurable CORS origins
* **Environment Variables**: Sensitive data protection

## 🌟 Key Features in Detail

### Conversational AI Agent

* Uses Google Gemini for natural language understanding
* Maintains conversation context and history
* Handles complex scheduling requests
* Provides intelligent suggestions

### Calendar Integration

* Real-time Google Calendar synchronization
* Conflict detection and resolution
* Multi-timezone support
* Event creation and management

### Smart Scheduling

* Availability analysis
* Optimal time slot suggestions
* Duration-based booking
* Confirmation workflows

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

* Google Calendar API for calendar integration
* LangChain for conversational AI framework
* Streamlit for the web interface
* FastAPI for the backend framework

## 📧 Contact

For questions or support, please open an issue on GitHub or contact [Tanishk Soni](https://github.com/bitphonix).

---

Made with ❤️ using Streamlit, FastAPI, and Google Calendar API

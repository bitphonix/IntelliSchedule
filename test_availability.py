# test_availability.py
import os
import sys
from datetime import datetime, timedelta, timezone
import pytz
import asyncio

# --- Path Correction ---
# Get the absolute path to the directory where this script is located (the project root)
project_root = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(project_root, 'backend')

# Add the backend directory to sys.path
# This allows direct imports of modules within the backend directory
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Define explicit paths for credentials and token
credentials_file_path = os.path.join(backend_dir, 'credentials.json')
token_file_path = os.path.join(backend_dir, 'token.pickle')

# Import necessary components directly from their files
from calendar_service import CalendarService
from agent import CalendarAgent, ConversationState
from utils import setup_logging
from langchain_core.messages import HumanMessage, AIMessage

# --- Setup ---
setup_logging()
print("--- Starting Agent Flow Test ---")

async def run_agent_flow_test():
    """
    Simulates the CalendarAgent's message processing flow to demonstrate
    intent parsing, datetime extraction, and availability checking.
    """
    # 1. Initialize the CalendarService and CalendarAgent with explicit paths
    print("1. Initializing CalendarService and CalendarAgent...")
    try:
        calendar_service = CalendarService(
            credentials_path=credentials_file_path,
            token_path=token_file_path
        )
        agent = CalendarAgent(calendar_service)
    except Exception as e:
        print(f"[ERROR] Failed to initialize services: {e}")
        return

    # 2. Verify authentication
    if not calendar_service.is_authenticated():
        print("\n[ERROR] Authentication failed.")
        print("Please ensure you have run the main Streamlit app and authenticated with Google Calendar at least once.")
        print(f"A valid 'token.pickle' file must exist in the '{backend_dir}' directory.")
        return
    
    print("   Authentication successful.")

    # 3. Get user input for the message and timezone
    user_message = input("\nEnter your message (e.g., 'Any openings on Monday?', 'Book a 1-hour meeting tomorrow morning'): ")
    user_timezone = input("Enter your timezone (e.g., 'Asia/Kolkata', 'America/New_York', 'UTC'): ")
    
    # Validate timezone (basic check)
    try:
        pytz.timezone(user_timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"[WARNING] Unknown timezone '{user_timezone}'. Defaulting to UTC.")
        user_timezone = "UTC"

    print(f"\n2. Processing message: '{user_message}' in timezone '{user_timezone}'...")

    # 4. Simulate the agent's process_message flow
    conversation_history = []
    
    try:
        response_data = await agent.process_message(
            session_id="test_session",
            user_timezone=user_timezone,
            conversation_history=conversation_history + [{
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
        )

        # 5. Display the agent's internal state and response
        print("\n--- Agent Processing Results ---")
        print(f"Agent's Intent: {response_data.get('context', {}).get('intent', 'N/A')}")
        
        extracted_dt = response_data.get('context', {}).get('extracted_datetime')
        if extracted_dt:
            print(f"Extracted Datetime (Start): {extracted_dt.get('start')}")
            print(f"Extracted Datetime (End): {extracted_dt.get('end')}")
            print(f"Is Range: {extracted_dt.get('is_range')}")
            print(f"Duration Minutes: {extracted_dt.get('duration_minutes')}")
        else:
            print("Extracted Datetime: None")

        available_slots = response_data.get('available_slots')
        if available_slots:
            print(f"\nAvailable Slots Found ({len(available_slots)}):")
            for i, slot in enumerate(available_slots[:5]):
                start_utc = datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
                start_local = start_utc.astimezone(pytz.timezone(user_timezone))
                print(f"  - Slot {i+1}: {start_local.strftime('%A, %B %d at %I:%M %p')}")
            if len(available_slots) > 5:
                print(f"  ... and {len(available_slots) - 5} more slots.")
        else:
            print("Available Slots: None")

        assistant_response = "N/A"
        if response_data.get("conversation_history"):
            last_message = response_data["conversation_history"][-1]
            if last_message["role"] == "assistant":
                assistant_response = last_message["content"]

        print(f"\nAgent's Final Response: {assistant_response}")
        print(f"Needs Confirmation: {response_data.get('needs_confirmation')}")

    except Exception as e:
        print(f"\n[ERROR] The agent flow test encountered an error: {e}")

# --- Run the script ---
if __name__ == "__main__":
    asyncio.run(run_agent_flow_test())

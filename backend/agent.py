import os
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import dataclass, field
import pytz

from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessageGraph
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from utils import DateTimeParser, normalize_time_format, extract_duration, get_relative_date

logger = logging.getLogger(__name__)

@dataclass
class ConversationState:
    """State for conversation flow"""
    messages: List[Any] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None
    extracted_datetime: Optional[Dict[str, Any]] = None
    duration_minutes: int = 30
    needs_confirmation: bool = False
    confirmation_data: Optional[Dict[str, Any]] = None
    available_slots: Optional[List[Dict[str, Any]]] = None
    user_timezone: str = "UTC"
    session_id: str = "default"

class CalendarAgent:
    """Advanced conversational AI agent for calendar management"""
    
    def __init__(self, calendar_service):
        self.calendar_service = calendar_service
        self.datetime_parser = DateTimeParser()
        
        # Initialize Google Gemini
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",  # You can also use "gemini-1.5-flash" for faster responses
            temperature=0.1,
            google_api_key=google_api_key,
            convert_system_message_to_human=True  # Important for Gemini compatibility
        )
        
        # Conversation memory
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        
        # Build the conversation graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph with conditional branching."""
        workflow = StateGraph(ConversationState)
        
        # Add nodes
        workflow.add_node("parse_intent", self._parse_intent)
        workflow.add_node("parse_datetime", self._parse_datetime)
        workflow.add_node("check_availability", self._check_availability)
        workflow.add_node("generate_response", self._generate_response)
        
        # Set entry point
        workflow.set_entry_point("parse_intent")
        
        # Add edges
        workflow.add_edge("parse_intent", "parse_datetime")
        workflow.add_edge("check_availability", "generate_response")

        # Add the crucial conditional edge
        workflow.add_conditional_edges(
            "parse_datetime",
            self._decide_next_step,
            {
                "check_availability": "check_availability",
                "generate_response": "generate_response",
            }
        )
        
        # End after generating a response
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def _decide_next_step(self, state: ConversationState) -> str:
        """Decides the next node to call based on the agent's state."""
        if state.context.get("error"):
            return "generate_response" # Go to generate a response about the error

        if state.intent == "book_appointment":
            if state.extracted_datetime and state.available_slots:
                # We have a time and it's available, so propose booking
                return "generate_response"
            elif state.extracted_datetime and not state.available_slots:
                # The time is busy, check for alternatives
                return "check_availability"
            else:
                # Intent is to book, but no time was given
                return "generate_response" # Go to generate a clarifying question
        
        elif state.intent == "check_availability":
            return "check_availability"
        
        # For modify or general queries, just generate a response
        return "generate_response"
    
    async def process_message(self, session_id: str, user_timezone: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Process user message through conversation flow using history."""
        try:
            # Build LangChain messages from the provided history
            messages = []
            for item in conversation_history:
                if item.get("role") == "user":
                    messages.append(HumanMessage(content=item["content"]))
                else:
                    messages.append(AIMessage(content=item["content"]))

            # Initialize state with the full message history
            initial_state = ConversationState(
                messages=messages,
                user_timezone=user_timezone,
                session_id=session_id
            )
            
            # Preserve context from previous conversations in this session
            if hasattr(self, 'session_contexts') and session_id in self.session_contexts:
                initial_state.context = self.session_contexts[session_id].copy()

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Store context for future use in this session
            if not hasattr(self, 'session_contexts'):
                self.session_contexts = {}
            # FIX: Access final_state as dictionary, not object
            self.session_contexts[session_id] = final_state["context"].copy()
            
            # Convert final LangChain messages back to serializable dicts
            updated_history_for_session = []
            for msg in final_state['messages']:
                role = "user" if isinstance(msg, HumanMessage) else "assistant"
                updated_history_for_session.append({"role": role, "content": msg.content})

            # Return the complete state to the main app
            return {
                "conversation_history": updated_history_for_session,
                "session_id": session_id,
                "needs_confirmation": final_state.get("needs_confirmation", False),
                "confirmation_data": final_state.get("confirmation_data"),
                "available_slots": final_state.get("available_slots"),
                "context": final_state.get("context", {})
            }

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            error_history = conversation_history + [{"role": "assistant", "content": "I apologize, but I encountered an error. Please try again."}]
            return {
                "conversation_history": error_history,
                "response": "I apologize, but I encountered an error. Please try again.",
                "context": {"error": str(e)}
            }


    
    def _parse_intent(self, state: ConversationState) -> ConversationState:
        """Parse user intent from message using Gemini"""
        try:
            message = state.messages[-1].content.lower()
            
            intent_prompt = f"""
            Analyze this user message and classify the intent. Respond with only one of these intents:
            - "book_appointment": User wants to book/schedule something
            - "check_availability": User wants to see available times
            - "modify_appointment": User wants to cancel/change/reschedule
            - "general_query": Other types of queries
            
            User message: "{message}"
            
            Consider these patterns:
            - Booking: "book", "schedule", "set up", "arrange", "plan", "create", "add"
            - Availability: "available", "free", "open", "what time", "when free", "any slot"
            - Modification: "cancel", "delete", "remove", "reschedule", "move", "change"
            
            Intent:"""
            
            try:
                response = self.llm.invoke(intent_prompt)
                intent = response.content.strip().lower()
                
                # Map response to our intents
                if "book_appointment" in intent:
                    state.intent = "book_appointment"
                elif "check_availability" in intent:
                    state.intent = "check_availability"
                elif "modify_appointment" in intent:
                    state.intent = "modify_appointment"
                else:
                    state.intent = "general_query"
                    
            except Exception as llm_error:
                logger.warning(f"LLM intent parsing failed, using rule-based fallback: {llm_error}")
                # Fallback to rule-based intent parsing
                booking_patterns = [
                    r"book|schedule|set up|arrange|plan|create|add",
                    r"meeting|appointment|call|event",
                    r"available|free|open",
                    r"tomorrow|today|next week|this week|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
                ]
                
                availability_patterns = [
                    r"available|free|open",
                    r"what.*time|when.*free|any.*slot",
                    r"check.*calendar|see.*schedule"
                ]
                
                modification_patterns = [
                    r"cancel|delete|remove|reschedule|move|change|update"
                ]
                
                # Determine intent
                if any(re.search(pattern, message) for pattern in booking_patterns):
                    if "available" in message or "free" in message:
                        state.intent = "check_availability"
                    else:
                        state.intent = "book_appointment"
                elif any(re.search(pattern, message) for pattern in availability_patterns):
                    state.intent = "check_availability"
                elif any(re.search(pattern, message) for pattern in modification_patterns):
                    state.intent = "modify_appointment"
                else:
                    state.intent = "general_query"
            
            logger.info(f"Parsed intent: {state.intent}")
            return state
            
        except Exception as e:
            logger.error(f"Error parsing intent: {str(e)}")
            state.intent = "general_query"
            return state
    
    def _parse_datetime(self, state: ConversationState) -> ConversationState:
        """Parse date and time from message"""
        try:
            message = state.messages[-1].content
            
            # Use datetime parser
            parsed_datetime = self.datetime_parser.parse(message, state.user_timezone)
            
            if parsed_datetime:
                state.extracted_datetime = parsed_datetime
                # Store the last discussed date/time in context for future reference
                state.context["last_discussed_datetime"] = parsed_datetime
                
                # Extract duration if specified, and update the state
                duration = extract_duration(message)
                if duration:
                    state.duration_minutes = duration
                    if state.extracted_datetime:
                        state.extracted_datetime["duration_minutes"] = duration
                        state.extracted_datetime["end"] = state.extracted_datetime["start"] + timedelta(minutes=duration)
                
                logger.info(f"Parsed datetime: {parsed_datetime}")
            else:
                logger.info("No datetime found in message")
            
            return state
            
        except Exception as e:
            logger.error(f"Error parsing datetime: {str(e)}")
            return state

    
    def _check_availability(self, state: ConversationState) -> ConversationState:
        """Check calendar availability with improved context memory and multi-day handling."""
        try:
            if not self.calendar_service.is_authenticated():
                state.context["error"] = "Not authenticated with Google Calendar"
                return state

            user_tz = pytz.timezone(state.user_timezone)
            now = datetime.now(user_tz)

            if not state.extracted_datetime:
                last_discussed = state.context.get("last_discussed_datetime")
                if last_discussed:
                    logger.info(f"Using last discussed datetime from context: {last_discussed}")
                    state.extracted_datetime = last_discussed
                else:
                    # Default to checking the next 7 days if no time is specified
                    start_date = now
                    end_date = now + timedelta(days=7)
                    available_slots = self.calendar_service.get_availability(
                        start_date, end_date, state.duration_minutes
                    )
                    state.available_slots = [
                        slot for slot in available_slots if slot["start"] > now
                    ]
                    return state

            start_time = state.extracted_datetime["start"]
            end_time = state.extracted_datetime["end"]

            # Scenario 1: A time range over multiple days (e.g., "3-5 PM this week")
            is_multi_day_time_range = (
                state.extracted_datetime.get("is_range") and
                not state.extracted_datetime.get("is_full_day") and
                (end_time.date() > start_time.date())
            )

            if is_multi_day_time_range:
                all_slots = []
                current_day = start_time
                while current_day.date() <= end_time.date():
                    # Define the time window for the current day
                    day_start_time = current_day.replace(
                        hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0
                    )
                    day_end_time = current_day.replace(
                        hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
                    )

                    if day_start_time > now:
                        daily_slots = self.calendar_service.find_free_slots(
                            (day_start_time, day_end_time),
                            state.duration_minutes
                        )
                        all_slots.extend(daily_slots)
                    
                    current_day += timedelta(days=1)

                state.available_slots = [
                    slot for slot in all_slots if slot["start"] > now
                ]

            # Scenario 2: A general date range or a full day (e.g., "this week", "tomorrow")
            elif state.extracted_datetime.get("is_range") or state.extracted_datetime.get("is_full_day"):
                available_slots = self.calendar_service.find_free_slots(
                    (start_time, end_time),
                    state.duration_minutes
                )
                state.available_slots = [
                    slot for slot in available_slots if slot["start"] > now
                ]

            # Scenario 3: A specific, single time (e.g., "tomorrow at 2 PM")
            else:
                end_time = start_time + timedelta(minutes=state.duration_minutes)
                
                if start_time <= now:
                    state.context["requested_slot_past"] = True
                    state.available_slots = []
                    return state
                
                is_available = self.calendar_service.check_availability(start_time, end_time)
                
                if is_available:
                    state.available_slots = [{"start": start_time, "end": end_time}]
                else:
                    state.context["requested_slot_busy"] = True
                    date_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    date_end = date_start + timedelta(days=1)
                    
                    alternative_slots = self.calendar_service.find_free_slots(
                        (date_start, date_end),
                        state.duration_minutes
                    )
                    
                    state.available_slots = [
                        slot for slot in alternative_slots if slot["start"] > now
                    ][:5]
            
            return state
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            state.context["error"] = str(e)
            return state



    
    def _generate_response(self, state: ConversationState) -> ConversationState:
        """Generate natural language response using Gemini"""
        try:
            # Generate response based on intent
            if state.intent == "check_availability":
                response = self._generate_availability_response(state)
            elif state.intent == "book_appointment":
                response = self._generate_booking_response(state)
            elif state.intent == "modify_appointment":
                response = self._generate_modification_response(state)
            else:
                response = self._generate_general_response(state)
            
            # IMPORTANT: Add the response to the conversation history
            state.messages.append(AIMessage(content=response))
            logger.info(f"Generated response: {response[:100]}...")
            
            return state
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            state.context["response"] = "I apologize, but I encountered an error generating a response. Please try again."
            return state
    
    def _generate_availability_response(self, state: ConversationState) -> str:
        """Generate availability check response using Gemini for natural language"""
        try:
            logger.info(f"Generating response for intent: {state.intent}")
            
            if state.context.get("error"):
                return f"I encountered an issue: {state.context['error']}"
            
            if not state.available_slots:
                if state.extracted_datetime:
                    return "I couldn't find any available slots for that time. Would you like me to suggest some alternative times?"
                else:
                    return "It looks like your calendar is quite busy. Let me know if you'd like to check a specific time or date range."
            
            logger.info(f"Available slots: {len(state.available_slots)}")
            
            slots_by_day = {}
            for slot in state.available_slots:
                day_key = slot["start"].strftime('%A, %B %d')
                if day_key not in slots_by_day:
                    slots_by_day[day_key] = []
                slots_by_day[day_key].append(slot["start"].strftime('%I:%M %p'))
            
            slots_info = []
            for day, times in slots_by_day.items():
                if len(times) > 5:
                    slots_info.append(f"{day}: {', '.join(times[:3])}, and {len(times) - 3} more slots")
                else:
                    slots_info.append(f"{day}: {', '.join(times)}")
            
            try:
                slots_text = '\n'.join(slots_info)
                user_message = state.messages[-1].content if state.messages else "availability check"
                
                natural_response_prompt = f"""
                You are a helpful calendar assistant. Generate a natural, conversational response for showing available calendar slots.
                
                User asked: "{user_message}"
                
                Available slots:
                {slots_text}
                
                Requirements:
                - Be conversational and friendly
                - Present the information clearly
                - Ask if they'd like to book one of these slots
                - Keep it concise but helpful
                - Don't be robotic
                
                Response:"""
                
                gemini_response = self.llm.invoke(natural_response_prompt)
                return gemini_response.content.strip()
                
            except Exception as llm_error:
                logger.warning(f"Gemini response generation failed, using template: {llm_error}")
                response_parts = ["Here are your available slots:"]
                for slot_info in slots_info:
                    response_parts.append(f"\n• {slot_info}")
                response_parts.append("\n\nWould you like to book any of these slots?")
                return "".join(response_parts)
                
        except Exception as e:
            logger.error(f"Error generating availability response: {str(e)}")
            return "I had trouble checking your availability. Please try again."
    
    def _generate_booking_response(self, state: ConversationState) -> str:
        """Generate booking response with consistent time formatting."""
        try:
            if state.context.get("error"):
                return f"I encountered an issue: {state.context['error']}"
            
            if not state.extracted_datetime:
                return "I'd be happy to help you book an appointment! Could you please specify when you'd like to schedule it? For example, 'tomorrow at 2 PM' or 'next Friday afternoon'."

            if state.context.get("requested_slot_past"):
                return "I notice that time has already passed. Would you like me to suggest some available times for today or upcoming days?"

            if not state.available_slots:
                if state.context.get("requested_slot_busy"):
                    # This path is for when a specific slot was requested but was busy
                    response_parts = ["That time slot is not available. Here are some alternative times for that day:"]
                    for slot in state.available_slots:
                        response_parts.append(f"• {slot['start'].strftime('%I:%M %p')}")
                    response_parts.append("\nWould you like to book one of these times?")
                    return "\n".join(response_parts)
                else:
                    # This path is for when a range was requested but no slots were found
                    return "I couldn't find any available slots for that time range. Would you like to try a different day or time?"

            # If we have multiple slots, it means the user asked for a range. List them.
            if len(state.available_slots) > 1:
                slots_by_day = {}
                for slot in state.available_slots:
                    day_key = slot["start"].strftime('%A, %B %d')
                    if day_key not in slots_by_day:
                        slots_by_day[day_key] = []
                    slots_by_day[day_key].append(slot["start"].strftime('%I:%M %p'))

                response_parts = [f"Great! I found {len(state.available_slots)} available {state.duration_minutes}-minute slots:"]
                for day, times in slots_by_day.items():
                    response_parts.append(f"**{day}:** {', '.join(times)}")
                response_parts.append(f"\nWhich time works best for you?")
                return "\n".join(response_parts)

            # If we have exactly one slot, it's time to confirm the booking.
            if len(state.available_slots) == 1:
                slot = state.available_slots[0]
                start_time_local = slot["start"]
                end_time_local = slot["end"]
                
                # The time displayed to the user should be in their local timezone.
                formatted_time = start_time_local.strftime('%A, %B %d at %I:%M %p')
                
                # For the API call, we need to convert the time to UTC.
                start_time_utc = start_time_local.astimezone(pytz.utc)
                end_time_utc = end_time_local.astimezone(pytz.utc)

                state.needs_confirmation = True
                state.confirmation_data = {
                    "start_time": start_time_utc.isoformat(),
                    "end_time": end_time_utc.isoformat(),
                    "title": "Meeting",
                    "description": "",
                    "location": "",
                    "user_timezone": state.user_timezone
                }
                
                return f"Perfect! I can book a {state.duration_minutes}-minute meeting for {formatted_time}. Would you like me to confirm this booking?"
            
            return "I'm sorry, I had trouble finding a suitable time. Please try again."
                
        except Exception as e:
            logger.error(f"Error generating booking response: {str(e)}")
            return "I had trouble processing your booking request. Please try again."

    def _generate_modification_response(self, state: ConversationState) -> str:
        """Generate modification response"""
        return "I can help you modify your appointments. Could you please specify which appointment you'd like to change and what modifications you need?"
    
    def _generate_general_response(self, state: ConversationState) -> str:
        """Generate general response using Gemini"""
        try:
            user_message = state.messages[-1].content if state.messages else ""
            
            general_prompt = f"""
            You are a helpful calendar assistant. The user said: "{user_message}"
            
            This doesn't seem to be a specific calendar request. Generate a helpful response that:
            - Acknowledges their message
            - Explains what you can help with (checking availability, booking appointments, modifying events)
            - Asks how you can assist them
            - Be friendly and conversational
            - Keep it brief
            
            Response:"""
            
            try:
                gemini_response = self.llm.invoke(general_prompt)
                return gemini_response.content.strip()
            except Exception as llm_error:
                logger.warning(f"Gemini general response failed, using template: {llm_error}")
                return "I'm here to help you manage your calendar! You can ask me to check your availability, book appointments, or modify existing ones. What would you like to do?"
                
        except Exception as e:
            logger.error(f"Error generating general response: {str(e)}")
            return "I'm here to help you manage your calendar! You can ask me to check your availability, book appointments, or modify existing ones. What would you like to do?"
    
    async def execute_booking(self, confirmation_data: Dict[str, Any], session_id: str = "default") -> Dict[str, Any]:
        """Execute the actual booking with consistent time formatting."""
        try:
            if not self.calendar_service.is_authenticated():
                raise ValueError("Not authenticated with Google Calendar")
            
            # The times are now correctly formatted ISO strings with UTC timezone info
            start_time_utc = datetime.fromisoformat(confirmation_data["start_time"])
            end_time_utc = datetime.fromisoformat(confirmation_data["end_time"])

            # Create event in UTC
            result = self.calendar_service.create_event(
                title=confirmation_data.get("title", "Meeting"),
                start_time=start_time_utc,
                end_time=end_time_utc,
                description=confirmation_data.get("description", ""),
                location=confirmation_data.get("location", "")
            )

            # Convert to user's timezone for the final message
            user_tz_str = confirmation_data.get("user_timezone", "UTC")
            user_tz = pytz.timezone(user_tz_str)
            start_time_local = start_time_utc.astimezone(user_tz)
            formatted_time_local = start_time_local.strftime('%A, %B %d at %I:%M %p')

            success_message = (
                f"✅ Done! Your meeting has been booked for *{formatted_time_local}* ({user_tz_str}). "
                f"You should receive a calendar notification shortly."
            )

            return {
                "status": "success",
                "message": success_message,
                "event_details": result
            }

        except Exception as e:
            logger.error(f"Error executing booking: {str(e)}")
            return {
                "status": "error",
                "message": f"I'm sorry, but I couldn't book your appointment: {str(e)}. Please try again."
            }
    
    def _confirm_booking(self, state: ConversationState) -> ConversationState:
        """Handle booking confirmation"""
        # This would be called when user confirms booking
        state.needs_confirmation = False
        return state
    
    def _execute_booking(self, state: ConversationState) -> ConversationState:
        """Execute booking after confirmation"""
        # This would be called after confirmation
        return state
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        return self.conversations.get(session_id, [])
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self.conversations:
            del self.conversations[session_id]
    
    def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        try:
            return {
                "status": "healthy",
                "llm_available": self.llm is not None,
                "calendar_service_available": self.calendar_service is not None,
                "active_conversations": len(self.conversations),
                "llm_model": "gemini-1.5-pro"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

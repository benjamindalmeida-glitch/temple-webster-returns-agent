import os          # Access environment variables (API keys, project IDs)
import json        # Parse and format JSON strings — used to decode LLM responses
import time        # Adds delay between retries via time.sleep()

from google import genai            # The Google GenAI SDK — sends messages to Gemini
from google.genai import types      # Configuration objects for the SDK (system instructions, tools, temperature)
from pydantic import BaseModel, Field, ValidationError  # Schema definition and validation — ensures LLM output has the right structure
from typing import Optional         # Allows order_id to be either a string or null
from dotenv import load_dotenv      # Reads the .env file and loads its values as environment variables


# Using python-dotenv for secrets; in production GCP, swap for Secret Manager.
load_dotenv()

# Strip any local GCP credentials to guarantee routing to the standard Developer API.
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

api_key = os.environ.get("GEMINI_API_KEY")

# Forcing base_url bypasses any local Vertex AI routing.
client = genai.Client(
    api_key=api_key,
    http_options={'base_url': 'https://generativelanguage.googleapis.com'}
)

# --- MOCK DATABASE ---
ORDERS = {
    "101": {"item": "Milan Boucle Sofa", "price": 899, "status": "Delivered 5 days ago"},
    "102": {"item": "Ceramic Vase", "price": 45, "status": "Delivered 45 days ago"},
    "103": {"item": "Outdoor Dining Set", "price": 1200, "status": "In Transit"},
    "104": {"item": "Handwoven Jute Rug", "price": 120, "status": "Delivered 10 days ago"}
}

# Mock for what would be a REST/GraphQL call to central in production.
# The type hints and docstring are parsed by the GenAI SDK to build the tool's JSON schema.
def get_order(order_id: str) -> dict:
    """Fetches order details from the database based on the order ID."""
    return ORDERS.get(order_id, {"error": "Order not found. Ask the customer to verify the ID."})

# Defines the strict contract for the agent's JSON output.
# The Gemini API currently doesn't support response_schema alongside tool calling,
# so we enforce the schema via prompt instructions and validate on the output side.
class AgentDecision(BaseModel):
    order_id: Optional[str] = Field(description="The order ID if found, otherwise null.")
    decision: str = Field(description="Must be one of: REFUND, REJECT, ESCALATE, or ASK_FOR_INFO.")
    customer_reply: str = Field(description="The polite reply to send back to the customer.")
    category: str = Field(description="Classification of the issue (e.g., Damage in Transit, Change of mind).")

SYSTEM_INSTRUCTION = """
You are the Autonomous Returns & Resolution Agent for Temple & Webster.
Your job is to read customer complaints, use the `get_order` tool to fetch order details, and make a programmatic decision.

Business Policies:
1. Customers can return items for a refund within 30 days of delivery.
2. Items over $500 cannot be automatically refunded; they must be marked as "ESCALATE" for human review.
3. If an item is still "In Transit", tell the customer to wait until delivery and mark as "REJECT".

Instructions:
- If you do not have an order ID, output ASK_FOR_INFO and ask the customer for it.
- Classify the issue into a specific category based on the user's text.

CRITICAL: Your final output MUST be a strict, raw JSON payload. Do not wrap it in markdown backticks.
It must contain exactly 4 keys:
- "order_id": (string or null)
- "decision": (must be "REFUND", "REJECT", "ESCALATE", or "ASK_FOR_INFO")
- "customer_reply": (string, polite reply to the customer)
- "category": (string)
"""

MAX_RETRIES = 3
MAX_TURNS = 3

def parse_response(raw_text: str) -> dict:
    """Sanitises LLM output and validates it against the AgentDecision schema."""
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
        validated = AgentDecision(**data)
        return validated.model_dump()
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"LLM returned unparsable or invalid output: {cleaned}") from e

def send_with_retry(chat, message: str) -> dict:
    """Sends a message with retries to handle transient LLM or parsing failures."""
    for attempt in range(MAX_RETRIES):
        try:
            response = chat.send_message(message)
            return parse_response(response.text)
        except (ValueError, Exception) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"Retry {attempt + 1}/{MAX_RETRIES}: {e}")
            time.sleep(1)

def process_ticket(initial_message: str) -> dict:
    """Processes a customer message, handles tool calling, and manages the ASK_FOR_INFO loop."""
    print(f"\n--- New Ticket ---")
    print(f"Customer: {initial_message}")

    # Using chats.create so the SDK automatically manages user/model/tool history,
    # reducing boilerplate for multi-turn context management.
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[get_order],
            temperature=0.1
        )
    )

    result = send_with_retry(chat, initial_message)
    print(f"Agent Output:\n{json.dumps(result, indent=2)}")

    # Handles the "Human in the Loop" state. The agent pauses, collects missing info,
    # and resumes with full conversation context intact. Capped to prevent infinite loops.
    turns = 0
    while result.get("decision") == "ASK_FOR_INFO" and turns < MAX_TURNS:
        turns += 1
        user_reply = input(f"\nAgent asks: {result.get('customer_reply')}\nCustomer reply: ")
        result = send_with_retry(chat, user_reply)
        print(f"Agent Output:\n{json.dumps(result, indent=2)}")

    # Safety valve: if the agent still can't resolve after max turns, escalate to a human.
    if result.get("decision") == "ASK_FOR_INFO":
        result["decision"] = "ESCALATE"
        result["customer_reply"] = "We're having trouble resolving this automatically. A team member will follow up shortly."
        print(f"Agent Output (safety escalation):\n{json.dumps(result, indent=2)}")

    return result

if __name__ == "__main__":
    test_message = "I want to return the rug I bought, it's the wrong color."
    process_ticket(test_message)

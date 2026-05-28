import json
from unittest.mock import patch
from agent import process_ticket

def test_case_1_escalate():
    """Order 101 ($899, delivered 5 days ago) — price > $500 triggers ESCALATE (Rule 2)."""
    message = "Hi, my order 101 arrived but it doesn't fit in my living room. I want to return it."
    result = process_ticket(message)
    assert result.get("decision") == "ESCALATE", f"Expected ESCALATE, got {result.get('decision')}"


def test_case_2_reject_outside_window():
    """Order 102 ($45, delivered 45 days ago) — outside 30-day window triggers REJECT (Rule 1)."""
    message = "I bought a vase (Order 102) a while ago and just opened it, it's broken. Can I get my money back?"
    result = process_ticket(message)
    assert result.get("decision") == "REJECT", f"Expected REJECT, got {result.get('decision')}"


def test_case_3_reject_in_transit():
    """Order 103 ($1200, In Transit) — in-transit status takes precedence, triggers REJECT (Rule 3)."""
    message = "Where is my outdoor dining set?! Order 103."
    result = process_ticket(message)
    assert result.get("decision") == "REJECT", f"Expected REJECT, got {result.get('decision')}"


@patch('builtins.input', return_value="104")
def test_case_4_ask_for_info(mock_input):
    """No order ID provided — agent must ASK_FOR_INFO, then resolve to REFUND after receiving Order 104."""
    message = "I want to return the rug I bought, it's the wrong color."
    result = process_ticket(message)
    mock_input.assert_called_once()
    print(f"\n✅ Test 4 Result:\n{json.dumps(result, indent=2)}")
    assert result.get("decision") == "REFUND", f"Expected REFUND, got {result.get('decision')}"


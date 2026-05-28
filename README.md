# Autonomous Returns & Resolution Agent

An AI-powered customer service agent that reads complaints, looks up order data via tool calling, applies business rules, and outputs strict programmatic decisions. Built with Python, Google Gemini, and the GenAI SDK.

## Architecture Overview

The agent follows a ReAct-style loop:
1. Receives a raw customer message
2. Uses Gemini to parse intent and extract order IDs
3. Calls the `get_order` tool to fetch order details
4. Applies business rules (return window, price threshold, transit status)
5. Outputs a validated JSON decision: `REFUND`, `REJECT`, `ESCALATE`, or `ASK_FOR_INFO`

If information is missing, the agent enters a multi-turn loop — pausing to collect input from the customer and resuming with full conversation context intact.

## Business Rules

| Rule | Condition | Decision |
|------|-----------|----------|
| 1 | Delivered within 30 days, item ≤ $500 | REFUND |
| 2 | Item > $500 | ESCALATE for human review |
| 3 | Item still In Transit | REJECT — ask customer to wait |

## Mock Data

| Order ID | Item | Price | Status |
|----------|------|-------|--------|
| 101 | Milan Boucle Sofa | $899 | Delivered 5 days ago |
| 102 | Ceramic Vase | $45 | Delivered 45 days ago |
| 103 | Outdoor Dining Set | $1,200 | In Transit |
| 104 | Handwoven Jute Rug | $120 | Delivered 10 days ago |

### Setup Instructions

### 1. Clone and navigate into the repository
```bash
git clone https://github.com/benjamindalmeida-glitch/temple-webster-returns-agent.git
cd temple-webster-returns-agent
```

### 2. Create and activate a virtual environment
```bash
python -m venv .venv
```

Windows:
```bash
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Duplicate `.env.example` and rename the copy to `.env`. Open it and add your Gemini API key:
```
GEMINI_API_KEY=your-api-key-here
```

### 5. Run the agent
```bash
python agent.py
```
This demonstrates the ASK_FOR_INFO loop. The agent will recognise that no order ID was provided, pause, and ask for one. Type `104` when prompted — the agent will resume with full context, fetch the order, and return a final REFUND decision.

### 6. Run the test suite
```bash
pytest test_agent.py -v -s
```
Four automated tests validate each business rule and decision path:

| Test | Expected Decision | What it proves |
|------|-------------------|----------------|
| 1 | ESCALATE | LLM correctly applies the $500 threshold rule |
| 2 | REJECT | LLM reasons about delivery dates against the 30-day policy |
| 3 | REJECT | LLM prioritises in-transit status over conflicting rules |
| 4 | ASK_FOR_INFO → REFUND | Multi-turn loop works — agent pauses, collects input, resumes with context |

Together they cover tool calling, policy adherence, conflict resolution, and stateful conversation management.

## Test Cases

| Test | Input | Expected Decision | Rule |
|------|-------|-------------------|------|
| 1 | Order 101 — sofa doesn't fit | ESCALATE | Price > $500 |
| 2 | Order 102 — vase broken | REJECT | Outside 30-day window |
| 3 | Order 103 — where is my order? | REJECT | Still in transit |
| 4 | No order ID — rug wrong color | ASK_FOR_INFO → REFUND | Multi-turn loop, then price ≤ $500 |

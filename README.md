# Microsoft Foundry — AI Agents POC

A collection of proof-of-concept scripts demonstrating **Azure AI Foundry Agents** with the `azure-ai-projects` SDK.

## Prerequisites

- Python 3.8+
- An Azure AI Foundry project with a deployed model
- Azure credentials configured (e.g. `az login` or a service principal)

## Setup

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install azure-ai-projects azure-identity python-dotenv
```

Create a `.env` file in the project root:

```env
FOUNDRY_PROJECT_ENDPOINT=https://<your-resource>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL_NAME=<deployed-model-name>
```

## Scripts

| Script | Description |
|---|---|
| `FoundryAgent.py` | Basic agent with a custom weather tool. Sends a single query and prints the response. |
| `customtool.py` | Defines a reusable `FunctionTool` (`weather_tool`) that returns mock weather data. Imported by other scripts. |
| `multithread.py` | Runs the same agent across **three concurrent threads**, each with a different question, and polls all runs to completion. |
| `HumanInLoop.py` | Demonstrates **human-in-the-loop** approval — the agent requests a tool call (refund / cancel subscription) and waits for manual confirmation before executing. |
| `doctor_appointment_agent.py` | Full **interactive clinic appointment system** with receptionist approval, emergency handling, multi-patient sessions, and an end-of-day report. |

## Doctor Appointment System

The most complete example. Run it with:

```bash
python doctor_appointment_agent.py
```

### Features

- **AI Receptionist ("Utkarsha")** — guides patients step-by-step to collect name, phone, symptoms, preferred slot, visit type, and emergency status.
- **Three tool functions:**
  - `check_slots()` — returns available 20-minute appointment slots.
  - `get_clinic_info(topic)` — returns clinic timings, fees, location, contact, emergency number, or parking info.
  - `book_appointment(...)` — validates the slot and creates a booking.
- **Human approval gate** — before any booking is finalised, a receptionist prompt appears with options to confirm, reject, or change the slot.
- **Emergency fast-track** — emergency cases are auto-approved and assigned the first available slot.
- **Multi-patient sessions** — run multiple patient sessions sequentially from a menu (`new` / `report` / `quit`).
- **End-of-day report** — summary of confirmed, rejected, and exited sessions.

### Menu Commands

| Command | Action |
|---|---|
| `new` | Start a new patient chat session |
| `report` | View all bookings made so far |
| `quit` | Exit and print the end-of-day report |

## Project Structure

```
Microsoft Foundry/
├── .env                    # Environment variables (not committed)
├── FoundryAgent.py          # Basic agent + custom tool demo
├── customtool.py           # Shared weather FunctionTool
├── multithread.py          # Multi-thread concurrent agent runs
├── HumanInLoop.py          # Human approval before tool execution
├── doctor_appointment_agent.py   # Full clinic appointment system
└── README.md
```

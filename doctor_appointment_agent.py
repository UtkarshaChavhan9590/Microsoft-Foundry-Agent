import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import FunctionTool

load_dotenv()

# ═══════════════════════════════════════════════════════════
# CLINIC DATA
# ═══════════════════════════════════════════════════════════

AVAILABLE_SLOTS = [
    "Monday    10:00 AM",
    "Monday    11:00 AM",
    "Tuesday   09:00 AM",
    "Tuesday   03:00 PM",
    "Wednesday 10:00 AM",
    "Wednesday 04:00 PM",
    "Thursday  11:00 AM",
    "Friday    09:00 AM",
    "Friday    02:00 PM",
]

BOOKED = []

# ═══════════════════════════════════════════════════════════
# TOOL FUNCTIONS
# ═══════════════════════════════════════════════════════════

def check_slots() -> str:
    """Returns available appointment slots."""
    return json.dumps({
        "available_slots": AVAILABLE_SLOTS,
        "doctor":          "Dr. Mehta (MBBS, MD - General Physician)",
        "clinic":          "Mehta Clinic, Pune",
        "note":            "Each slot is 20 minutes."
    })


def get_clinic_info(topic: str) -> str:
    """Returns clinic information based on topic."""
    data = {
        "timings":  "Monday to Saturday: 9 AM – 7 PM. Sunday: Closed.",
        "fees":     "First visit: ₹500. Follow-up within 7 days: ₹200.",
        "location": "123 MG Road, Near City Mall, Pune – 411001.",
        "contact":  "Phone: 020-12345678 | WhatsApp: 98765-43210",
        "emergency":"For emergencies please call 020-99999999 (available 24x7).",
        "parking":  "Free parking in basement. Entry from lane behind clinic."
    }
    answer = data.get(
        topic.lower().strip(),
        "Please call 020-12345678 for more details."
    )
    return json.dumps({"topic": topic, "answer": answer})


def book_appointment(patient_name: str,
                     phone_number: str,
                     problem: str,
                     preferred_slot: str,
                     visit_type: str = "first_visit",
                     is_emergency: str = "no") -> str:
    """
    Books an appointment after all details are collected.
    is_emergency: 'yes' or 'no'
    visit_type: 'first_visit' or 'follow_up'
    """
    # Validate slot
    matched_slot = None
    for s in AVAILABLE_SLOTS:
        if preferred_slot.lower().replace(" ", "") in s.lower().replace(" ", ""):
            matched_slot = s
            break

    if not matched_slot:
        return json.dumps({
            "status":           "slot_unavailable",
            "requested_slot":   preferred_slot,
            "available_slots":  AVAILABLE_SLOTS,
            "message":          f"Slot '{preferred_slot}' not found. Please choose from available slots."
        })

    fee = "₹200" if visit_type == "follow_up" else "₹500"
    booking_id = f"APT-{datetime.now().strftime('%H%M%S')}"

    booking = {
        "booking_id":    booking_id,
        "patient_name":  patient_name,
        "phone":         phone_number,
        "problem":       problem,
        "slot":          matched_slot,
        "visit_type":    visit_type,
        "is_emergency":  is_emergency,
        "fee":           fee,
        "status":        "confirmed",
        "booked_at":     datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    BOOKED.append(booking)
    AVAILABLE_SLOTS.remove(matched_slot)

    return json.dumps(booking)


TOOL_FUNCTIONS = {
    "check_slots":      check_slots,
    "get_clinic_info":  get_clinic_info,
    "book_appointment": book_appointment,
}

# ═══════════════════════════════════════════════════════════
# RECEPTIONIST APPROVAL
# ═══════════════════════════════════════════════════════════

def receptionist_review(patient_name: str, fn_args: dict) -> tuple:
    """
    Shows receptionist the booking details.
    Returns (approved: bool, final_args: dict)
    """
    is_emergency = fn_args.get("is_emergency", "no").lower() == "yes"

    print("\n" + "═" * 55)
    if is_emergency:
        print("  🚨  EMERGENCY — AUTO APPROVING FIRST SLOT")
        fn_args["preferred_slot"] = AVAILABLE_SLOTS[0] if AVAILABLE_SLOTS else "Emergency slot"
        print(f"  Slot assigned  : {fn_args['preferred_slot']}")
        print("═" * 55)
        return True, fn_args

    print("  📋  RECEPTIONIST — APPOINTMENT REQUEST")
    print("═" * 55)
    print(f"  Patient Name   : {fn_args.get('patient_name', 'N/A')}")
    print(f"  Phone          : {fn_args.get('phone_number', 'N/A')}")
    print(f"  Problem        : {fn_args.get('problem', 'N/A')}")
    print(f"  Requested Slot : {fn_args.get('preferred_slot', 'N/A')}")
    print(f"  Visit Type     : {fn_args.get('visit_type', 'first_visit')}")
    print(f"  Emergency      : {fn_args.get('is_emergency', 'no').upper()}")
    print("═" * 55)
    print("  y = Confirm    n = Reject    m = Change slot")
    decision = input("  Receptionist: ").strip().lower()

    if decision == "m":
        print(f"\n  Available slots:")
        for i, s in enumerate(AVAILABLE_SLOTS, 1):
            print(f"    {i}. {s}")
        choice = input("  Enter slot number: ").strip()
        try:
            idx = int(choice) - 1
            fn_args["preferred_slot"] = AVAILABLE_SLOTS[idx]
            print(f"  ✏️  Slot changed to: {fn_args['preferred_slot']}")
        except (ValueError, IndexError):
            print("  ⚠️  Invalid choice. Keeping original slot.")
        decision = "y"

    approved = decision == "y"
    print(f"\n  {'✅ CONFIRMED' if approved else '❌ REJECTED'}")
    print("═" * 55)
    return approved, fn_args


# ═══════════════════════════════════════════════════════════
# SINGLE PATIENT CHAT SESSION
# ═══════════════════════════════════════════════════════════

def run_patient_session(client, agent, patient_label: str) -> dict:
    """
    Runs a full interactive chat session for one patient.
    The agent asks questions, patient types answers.
    Returns session result dict.
    """
    print(f"\n{'═'*55}")
    print(f"  🏥  NEW PATIENT SESSION — {patient_label}")
    print(f"{'═'*55}")

    # Create thread for this patient
    thread = client.agents.threads.create(
        metadata={"session": patient_label}
    )

    outcome = "pending"
    booking_result = None

    # ── Interactive chat loop ──────────────────────────────
    while True:
        # Get patient input
        print()
        user_input = input("  You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "bye"]:
            print("  Agent: Thank you for contacting Mehta Clinic. Goodbye! 🙏")
            outcome = "exited"
            break

        # Send patient message to thread
        client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_input
        )

        # Run agent on this thread
        run = client.agents.runs.create(
            thread_id=thread.id,
            agent_id=agent.id
        )

        # ── Poll run status ────────────────────────────────
        while True:
            time.sleep(1)
            run = client.agents.runs.get(
                thread_id=thread.id,
                run_id=run.id
            )

            # Still thinking
            if run.status in ["queued", "in_progress"]:
                continue

            # ── Tool call triggered ────────────────────────
            elif run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                rejected = False

                for call in tool_calls:
                    fn_name = call.function.name
                    fn_args = json.loads(call.function.arguments)

                    # Auto-handle info tools
                    if fn_name in ["check_slots", "get_clinic_info"]:
                        result = TOOL_FUNCTIONS[fn_name](**fn_args)
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": result
                        })
                        continue

                    # book_appointment → receptionist review
                    if fn_name == "book_appointment":
                        approved, final_args = receptionist_review(
                            patient_label, fn_args
                        )

                        if approved:
                            result = TOOL_FUNCTIONS[fn_name](**final_args)
                            result_data = json.loads(result)
                            booking_result = result_data
                            tool_outputs.append({
                                "tool_call_id": call.id,
                                "output": result
                            })
                            outcome = "confirmed"
                        else:
                            # Rejected — tell agent
                            rejected = True
                            outcome = "rejected"
                            client.agents.runs.cancel(
                                thread_id=thread.id,
                                run_id=run.id
                            )
                            # Inject rejection notice for agent
                            client.agents.messages.create(
                                thread_id=thread.id,
                                role="user",
                                content="[SYSTEM] The receptionist declined this booking. "
                                        "Please inform the patient politely and suggest "
                                        "they call 020-12345678 to arrange an alternative."
                            )
                            # Re-run agent so it can reply
                            run = client.agents.runs.create(
                                thread_id=thread.id,
                                agent_id=agent.id
                            )
                            break

                if not rejected and tool_outputs:
                    client.agents.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                    continue   # keep polling

            # ── Completed — print agent reply ──────────────
            elif run.status == "completed":
                messages = client.agents.messages.list(
                    thread_id=thread.id
                )
                for msg in messages:
                    if msg.role == "assistant":
                        print(f"\n  Dr. AI: {msg.content[0].text.value}")
                        break

                # If booking confirmed, end session
                if outcome == "confirmed":
                    print(f"\n  ✅ Appointment booked! Booking ID: "
                          f"{booking_result.get('booking_id', 'N/A')}")
                    break

                # If rejected, let patient decide to continue or exit
                if outcome == "rejected":
                    print("\n  (Type another message or 'bye' to exit)")

                break   # go back to patient input prompt

            elif run.status in ["failed", "cancelled", "expired"]:
                if outcome != "rejected":
                    print(f"\n  ⚠️  Something went wrong: {run.last_error}")
                break

    # Cleanup thread
    #client.agents.threads.delete(thread.id)

    return {
        "patient":  patient_label,
        "outcome":  outcome,
        "booking":  booking_result
    }


# ═══════════════════════════════════════════════════════════
# MAIN — MULTI PATIENT MENU
# ═══════════════════════════════════════════════════════════

def main():
    print("\n" + "═" * 55)
    print("  🏥  MEHTA CLINIC — APPOINTMENT SYSTEM")
    print("     Dr. Mehta (MBBS, MD — General Physician)")
    print("═" * 55)

    # Connect
    client = AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential()
    )

    # Register tools
    tools = FunctionTool(functions=list(TOOL_FUNCTIONS.values()))

    # Create agent
    agent = client.agents.create_agent(
        model=os.environ["FOUNDRY_MODEL_NAME"],
        name="mehta-clinic-agent",
        instructions="""You are Utkarsha, a friendly receptionist at Mehta Clinic in Pune.

Your job is to help patients book appointments with Dr. Mehta.

STEP BY STEP — always follow this order:
1. Greet the patient warmly
2. Ask for their FULL NAME (if not given)
3. Ask for their PHONE NUMBER (10 digits)
4. Ask what PROBLEM or SYMPTOMS they have
5. Call check_slots() to show available slots
6. Ask which SLOT they prefer
7. Ask if this is a FIRST VISIT or FOLLOW-UP
8. Ask if it is an EMERGENCY (yes/no)
9. Once you have ALL details → call book_appointment()

For general questions (timings, fees, location, parking):
- Use get_clinic_info(topic) — topic can be: timings, fees, location, contact, emergency, parking

Rules:
- Ask ONE question at a time — do not ask multiple questions together
- Be warm, friendly and speak in simple English
- If patient says emergency, set is_emergency='yes' and book immediately
- Always confirm the slot and details before booking
- Never make up information — use tools for real data""",
        tools=tools.definitions
    )
    print(f"\n  Agent ready. Type 'new' to start a patient session.")
    print(f"  Type 'report' to see today's bookings.")
    print(f"  Type 'quit' to exit the system.\n")

    all_results = []

    # ── Receptionist / Admin menu ──────────────────────────
    while True:
        print("─" * 55)
        cmd = input("  MENU → new / report / quit: ").strip().lower()

        if cmd == "quit":
            break

        elif cmd == "report":
            # Show today's bookings
            print(f"\n  📋 TODAY'S BOOKINGS ({len(BOOKED)} total)")
            print(f"  {'─'*50}")
            if not BOOKED:
                print("  No appointments booked yet.")
            for b in BOOKED:
                print(f"  {b['booking_id']} | {b['patient_name']:<15} | "
                      f"{b['slot']:<20} | {b['problem']}")
            print()

        elif cmd == "new":
            # Ask who is the patient (label for logging)
            patient_label = input(
                "  Enter patient label (e.g. Counter-1): "
            ).strip() or f"Patient-{len(all_results)+1}"

            # Run interactive session
            result = run_patient_session(client, agent, patient_label)
            all_results.append(result)

            # Show quick result
            print(f"\n  Session ended → Outcome: {result['outcome'].upper()}")
            if result["booking"]:
                b = result["booking"]
                print(f"  Booking ID : {b['booking_id']}")
                print(f"  Patient    : {b['patient_name']}")
                print(f"  Slot       : {b['slot']}")
                print(f"  Fee        : {b['fee']}")

        else:
            print("  Unknown command. Type: new / report / quit")

    # ── Final report ───────────────────────────────────────
    print("\n" + "═" * 55)
    print("  🏥  END OF DAY REPORT — MEHTA CLINIC")
    print("═" * 55)
    confirmed = [r for r in all_results if r["outcome"] == "confirmed"]
    rejected  = [r for r in all_results if r["outcome"] == "rejected"]
    exited    = [r for r in all_results if r["outcome"] == "exited"]

    print(f"  Total sessions   : {len(all_results)}")
    print(f"  Confirmed        : {len(confirmed)}")
    print(f"  Rejected         : {len(rejected)}")
    print(f"  Exited without booking: {len(exited)}")

    if BOOKED:
        print(f"\n  ── Confirmed Appointments ──")
        for b in BOOKED:
            print(f"  📅 {b['booking_id']} | {b['patient_name']:<15} | "
                  f"{b['slot']:<20} | {b['fee']}")

    # Cleanup agent
    #client.agents.delete_agent(agent.id)
    print("\n  ✅ System closed. Goodbye!\n")


if __name__ == "__main__":
    main()
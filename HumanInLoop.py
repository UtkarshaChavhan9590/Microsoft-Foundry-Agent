import os, time, json
from datetime import datetime
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import FunctionTool

load_dotenv()

client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential()
)

# Verify connection
print("Connected! Creating agent...")

# ── Define tools the agent can request ───────────────────────────
def process_refund(order_id: str, amount: str) -> str:
    """Actually processes the refund in your system."""
    # Replace with your real refund logic / API call
    print(f"\n  [SYSTEM] Processing refund: order={order_id}, amount=£{amount}")
    return json.dumps({
        "status": "refunded",
        "order_id": order_id,
        "amount": amount,
        "reference": "REF-98765"
    })

def cancel_subscription(user_id: str, reason: str) -> str:
    """Actually cancels subscription in your system."""
    print(f"\n  [SYSTEM] Cancelling subscription: user={user_id}, reason={reason}")
    return json.dumps({
        "status": "cancelled",
        "user_id": user_id,
        "effective_date": "2025-05-01"
    })

# Register both functions as tools
tool_functions = {
    "process_refund": process_refund,
    "cancel_subscription": cancel_subscription,
}

tools = FunctionTool(functions=[process_refund, cancel_subscription])


agent = client.agents.create_agent(
    model=os.environ["FOUNDRY_MODEL_NAME"],
    name=f"Customagent-humaninloop{datetime.now().strftime('%Y%m%d%H%M%S')}",
    instructions="""You are a customer support agent.
    When a customer asks for a refund, call process_refund.
    When a customer wants to cancel, call cancel_subscription.
    Always collect all required details before calling a tool.""",
    tools=tools.definitions
)
print(f"Agent with custom tool: {agent.id}")

thread = client.agents.threads.create(
    metadata={"user": "Customer123", "type": "Support"}
)
print(f"Thread created: {thread.id}")

# Add Message to Thread
client.agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="I want a refund for order #ORD-555. The amount was £49.99."
)

#Run Agent
run = client.agents.runs.create(
    thread_id=thread.id,
    agent_id=agent.id
)

#poll for run completion
while True:
    time.sleep(1)
    run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
    print(f"Run status: {run.status}")


    if run.status in ["queued", "in_progress"]:
        continue
    elif run.status == "requires_action":
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            
            print(f"Calling function: {func_name} with args: {fn_args}")
             # ── Show human what agent wants to do ─────────────────
            print("\n" + "="*55)
            print("⚠️  HUMAN APPROVAL REQUIRED")
            print("="*55)
            print(f"  Tool requested : {func_name}")
            print(f"  Arguments      : {json.dumps(fn_args, indent=4)}")
            print("="*55)

             # ── Ask for human decision ────────────────────────────
            decision = input("  Approve? (y = yes / n = no / m = modify): ").strip().lower()

            if decision == "y":
                # ✅ Approved — execute the real function
                print("  ✅ Approved — executing...")
                result = tool_functions[func_name](**fn_args)
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": result
                })
            elif decision == "m":
                # ✏️ Modify — ask human for new arguments
                print("  ✏️ Modify — please provide new arguments as JSON:")
                new_amount = input("  Enter corrected amount: ").strip()
                fn_args["amount"] = new_amount
                result = tool_functions[func_name](**fn_args)
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": result
                })
            else:
                # ❌ Rejected — cancel the entire run
                print("  ❌ Rejected — cancelling run.")
                client.agents.runs.cancel(
                    thread_id=thread.id,
                    run_id=run.id
                )
                # Add a message explaining why
                client.agents.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content="The action was rejected by the human supervisor. Please inform the customer."
                )
                break

        # Submit all approved tool outputs back so run can continue
        if tool_outputs:
            client.agents.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
            print("\n  ▶ Tool output submitted — run resuming...")

# ── DONE ──────────────────────────────────────────────────────
    elif run.status == "completed":
        print("\n" + "="*55)
        print("✅ RUN COMPLETED")
        print("="*55)
        messages = client.agents.messages.list(thread_id=thread.id)
        for msg in messages:
            if msg.role == "assistant":
                print(f"Agent reply: {msg.content[0].text.value}")
                break
        break

    # ── SOMETHING WENT WRONG ──────────────────────────────────────
    elif run.status in ["failed", "cancelled", "expired"]:
        print(f"\n❌ Run ended with status: {run.status}")
        if run.last_error:
            print(f"   Error: {run.last_error}")
        break    
# Cleanup
# client.agents.delete_agent(agent_id=agent.id)
# client.agents.threads.delete(thread_id=thread.id)
print("Cleanup completed.")

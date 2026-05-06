import os
import time
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import CodeInterpreterTool
from customtool import weather_tool

load_dotenv()

client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential()
)

# Verify connection
print("Connected! Creating agent...")

#code_tool = CodeInterpreterTool()

agent = client.agents.create_agent(
    model=os.environ["FOUNDRY_MODEL_NAME"],
    name="my-first-agent-customtool",
    instructions="You are a helpful assistant.",
    tools=weather_tool.definitions
)
print(f"Agent with custom tool: {agent.id}")

thread = client.agents.threads.create()
print(f"Thread created: {thread.id}")

# Add Message to Thread
client.agents.messages.create(
    thread_id=thread.id,
    role="user",
    content="What's the weather like in Pune?"
)

#Run Agent
run = client.agents.runs.create(
    thread_id=thread.id,
    agent_id=agent.id
)

#poll for run completion
while run.status in ["queued", "in_progress", "requires_action"]:
    if run.status == "requires_action":
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            import json
            args = json.loads(tool_call.function.arguments)
            print(f"Calling function: {func_name} with args: {args}")
            result = weather_tool.execute(tool_call)
            tool_outputs.append({"tool_call_id": tool_call.id, "output": result})
        run = client.agents.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )
    else:
        time.sleep(1)
        run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
    print(f"Run status: {run.status}")

# Read response
if run.status == "completed":
    messages = client.agents.messages.list(thread_id=thread.id)
    for message in messages:
        if message.role == "assistant":
            print(f" Agent: {message.content[0].text.value}")
            break
else:
    print(f"Run failed or was cancelled.{run.last_error}")

# Cleanup
# client.agents.delete_agent(agent_id=agent.id)
# client.agents.threads.delete(thread_id=thread.id)
print("Cleanup completed.")

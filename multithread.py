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
    instructions="You are a helpful assistant."
    #tools=weather_tool.definitions
)
print(f"Agent with id: {agent.id}")

#Single Thread Example
#thread = client.agents.threads.create()
#print(f"Thread created: {thread.id}")


# Multiple Threads Example
A_thread  = client.agents.threads.create(
    metadata={"user": "Thread A" , "session": "Session 1"}
)
print(f"Thread A created: {A_thread.id}")
B_thread  = client.agents.threads.create(
    metadata={"user": "Thread B" , "session": "Session 1"}
)
print(f"Thread B created: {B_thread.id}")
C_thread  = client.agents.threads.create(
    metadata={"user": "Thread C" , "session": "Session 1"}
)
print(f"Thread C created: {C_thread.id}")

# Add Message to Thread
client.agents.messages.create(
    thread_id=A_thread.id,
    role="user",
    content="What's the LangGraph in single sentences?"
)

client.agents.messages.create(
    thread_id=B_thread.id,
    role="user",
    content="What's the Langsmith in single sentences?"
)

client.agents.messages.create(
    thread_id=C_thread.id,
    role="user",
    content="What's the difference between LangSmith and LangGraph in single sentences?"
)

#Run Agent
# run = client.agents.runs.create(
#     thread_id=A_thread.id,
#     agent_id=agent.id
# )

A_run = client.agents.runs.create(
    thread_id=A_thread.id,
    agent_id=agent.id
)
B_run = client.agents.runs.create(
    thread_id=B_thread.id,
    agent_id=agent.id
)
C_run = client.agents.runs.create(
    thread_id=C_thread.id,
    agent_id=agent.id
)


runs = {
    "Thread A": (A_thread.id , A_run.id),
    "Thread B": (B_thread.id , B_run.id),
    "Thread C": (C_thread.id , C_run.id)
}

#poll for run completion
while True:
    all_done = True

    for user,(thread_id , run_id) in runs.items():
        run = client.agents.runs.get(thread_id=thread_id, run_id=run_id)

        if run.status in ["queued", "in_progress"]:
            all_done = False
            print(f"{user} Run status: {run.status}")

        elif run.status == "completed":
            messages = client.agents.messages.list(thread_id=thread_id)
            for message in messages:
                if message.role == "assistant":
                    print(f"{user} Agent: {message.content[0].text.value}")
                    break
                #remove from polling list
                runs.pop(user)
                break
                
        elif run.status in ["faliled", "cancelled" , "expired"]:
            print(f"{user} Run failed or was cancelled.{run.last_error}")
            #remove from polling list
            runs.pop(user)
            break
    
    if not runs or all_done:
        break

    time.sleep(1)


# Multi turn  send a follow up in the same thread
# thread remembers the previous message automatically as part of the conversation history
client.agents.messages.create(
    thread_id=A_thread.id,
    role="user",
    content="Can you explain it in more details?"
)

follow_up_run = client.agents.runs.create(
    thread_id=A_thread.id,
    agent_id=agent.id
)

messages = client.agents.messages.list(thread_id=A_thread.id)
for message in messages:
    if message.role == "assistant":
        print(f"Follow up Agent: {message.content[0].text.value}")
        break


# Cleanup
# client.agents.delete_agent(agent_id=agent.id)
# client.agents.threads.delete(thread_id=thread.id)
#print("Cleanup completed.")

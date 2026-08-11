from langchain.agents import create_agent
from langchain_groq import ChatGroq

from langgraph.checkpoint.memory import InMemorySaver

from agent.tools import tools
from agent.prompts import SYSTEM_PROMPT
from utils.config import GROQ_API_KEY


# ==========================================
# GROQ MODEL
# ==========================================

model = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=250,
)


# ==========================================
# SHORT-TERM MEMORY
# ==========================================

checkpointer = InMemorySaver()


# ==========================================
# CREATE AGENT
# ==========================================

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)


# ==========================================
# RUN AGENT
# ==========================================

def run_agent(
    user_message: str,
    thread_id: str = "default",
    user_id: str = "user_1",
) -> str:

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Tell the agent which user is talking
    message = f"""
Current user ID: {user_id}

User message:
{user_message}
"""

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        },
        config=config,
    )

    final_message = result["messages"][-1]
    print (f"Agent response: {final_message.content}")
    return final_message.content
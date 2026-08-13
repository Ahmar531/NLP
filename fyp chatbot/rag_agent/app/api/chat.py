from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.agent import agent
from app.memory.long_term import get_all_memories


router = APIRouter()
SHORT_TERM_MEMORY_LIMIT = 8
short_term_memories = {}


# ============================================================
# SHORT TERM MEMORY
# ============================================================

def add_short_term_memory(
    user_id: str,
    role: str,
    content: str,
):

    user_memory = short_term_memories.setdefault(
        user_id,
        []
    )

    user_memory.append(
        {
            "role": role,
            "content": content,
        }
    )

    if len(user_memory) > SHORT_TERM_MEMORY_LIMIT:

        del user_memory[
            :-SHORT_TERM_MEMORY_LIMIT
        ]


def format_short_term_memory(user_id: str):

    user_memory = short_term_memories.get(
        user_id,
        []
    )

    if not user_memory:

        return ""

    return "\n".join(
        f"{message['role']}: {message['content']}"
        for message in user_memory
    )


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    message: str

    user_id: str = "default_user"


# ============================================================
# CHAT ENDPOINT
# ============================================================

@router.post("/")
async def chat(request: ChatRequest):

    # --------------------------------------------------------
    # Get long-term memories
    # --------------------------------------------------------

    memories = get_all_memories(
        user_id=request.user_id
    )

    memory_text = ""

    if memories:

        memory_text = "\n".join(
            f"{m['key']}: {m['value']}"
            for m in memories
        )

    short_term_memory_text = format_short_term_memory(
        user_id=request.user_id
    )


    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
Known long-term user memories:

{memory_text}

Recent short-term conversation memory:

{short_term_memory_text}

User question:

{request.message}

Instructions:

- Use long-term memories when relevant.
- Use short-term memory for current conversation context.
- Do not store normal conversation in long-term memory.
- Long-term memory is only for stable important user facts.
- Do not invent personal information.
- Answer normal questions normally.
- If the question is related to company PDF documents,
  use the PDF search tool.
- If information is not available in the PDF documents,
  clearly say that it was not found.
"""


    # --------------------------------------------------------
    # Call agent
    # --------------------------------------------------------

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        }
    )


    # --------------------------------------------------------
    # Get response
    # --------------------------------------------------------

    messages = result.get(
        "messages",
        []
    )

    if not messages:

        return {
            "answer": "I could not generate a response."
        }


    answer = messages[-1].content

    add_short_term_memory(
        user_id=request.user_id,
        role="User",
        content=request.message,
    )

    add_short_term_memory(
        user_id=request.user_id,
        role="AI",
        content=answer,
    )


    return {
        "answer": answer
    }

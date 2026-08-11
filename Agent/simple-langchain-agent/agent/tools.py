from langchain.tools import tool

from agent.memory import LongTermMemory


memory = LongTermMemory()


# ==========================================
# SAVE MEMORY
# ==========================================

@tool
def save_memory(
    user_id: str,
    memory_text: str,
) -> str:
    """
    Save important information about the user
    into long-term memory.

    Use this only for information that should
    be remembered across future conversations.
    """

    return memory.save_memory(
        user_id=user_id,
        memory=memory_text,
    )


# ==========================================
# SEARCH MEMORY
# ==========================================

@tool
def search_memory(
    user_id: str,
    query: str,
) -> str:
    """
    Search the user's long-term memory when
    previous user information is relevant.
    """

    memories = memory.search_memory(
        user_id=user_id,
        query=query,
        limit=5,
    )

    if not memories:

        return "No relevant memories found."

    return "\n".join(
        f"- {item}"
        for item in memories
    )


# ==========================================
# ALL TOOLS
# ==========================================

tools = [
    save_memory,
    search_memory,
]
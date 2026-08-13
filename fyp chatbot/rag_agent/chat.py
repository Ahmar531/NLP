import re

from app.memory.long_term import (
    save_memory,
    get_memory,
    get_all_memories,
)

from app.agent.agent import agent


USER_ID = "default_user"
SHORT_TERM_MEMORY_LIMIT = 8
INVALID_NAME_WORDS = {
    "a",
    "an",
    "the",
    "learning",
    "working",
    "studying",
    "trying",
    "going",
    "using",
    "asking",
    "happy",
    "sad",
    "fine",
    "good",
    "bad",
}


# ============================================================
# EXTRACT NAME
# ============================================================

def extract_name(message: str):

    patterns = [
        r"\bmy name is\s+([A-Za-z]+)",
        r"\bi am called\s+([A-Za-z]+)",
        r"\bi'm called\s+([A-Za-z]+)",
        r"\bcall me\s+([A-Za-z]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            message,
            re.IGNORECASE
        )

        if match:

            name = match.group(1).strip()

            if name.lower() not in INVALID_NAME_WORDS:

                return name

    return None


# ============================================================
# EXTRACT IMPORTANT MEMORY
# ============================================================

def extract_important_memory(message: str):

    name = extract_name(message)

    if name:

        return "name", name

    remember_match = re.search(
        r"\bremember\s+(?:that\s+)?(.+)",
        message,
        re.IGNORECASE,
    )

    if not remember_match:

        return None

    memory_text = remember_match.group(1).strip()
    memory_text = re.sub(
        r"[.!?]+$",
        "",
        memory_text,
    )

    if not memory_text:

        return None

    patterns = [
        (
            "name",
            r"\bmy name is\s+([A-Za-z]+)",
        ),
        (
            "location",
            r"\bi live in\s+(.+)",
        ),
        (
            "location",
            r"\bi am from\s+(.+)",
        ),
        (
            "learning",
            r"\bi am learning\s+(.+)",
        ),
        (
            "role",
            r"\bi work as\s+(.+)",
        ),
        (
            "preference",
            r"\bi prefer\s+(.+)",
        ),
        (
            "goal",
            r"\bmy goal is\s+(.+)",
        ),
    ]

    for key, pattern in patterns:

        match = re.search(
            pattern,
            memory_text,
            re.IGNORECASE,
        )

        if match:

            return key, match.group(1).strip()

    return "important_note", memory_text


# ============================================================
# SHORT TERM MEMORY
# ============================================================

def add_short_term_memory(
    short_term_memory,
    role: str,
    content: str,
):

    short_term_memory.append(
        {
            "role": role,
            "content": content,
        }
    )

    if len(short_term_memory) > SHORT_TERM_MEMORY_LIMIT:

        del short_term_memory[
            :-SHORT_TERM_MEMORY_LIMIT
        ]


def format_short_term_memory(short_term_memory):

    if not short_term_memory:

        return ""

    return "\n".join(
        f"{message['role']}: {message['content']}"
        for message in short_term_memory
    )


# ============================================================
# CHAT
# ============================================================

def chat():

    print("Type 'exit' or 'quit' to stop.")
    print()

    short_term_memory = []

    while True:

        user_message = input("You: ").strip()

        if user_message.lower() in [
            "exit",
            "quit"
        ]:

            print("AI: Goodbye!")
            break


        # ====================================================
        # IMPORTANT MEMORY SETTING
        # ====================================================

        important_memory = extract_important_memory(user_message)

        if important_memory:

            key, value = important_memory

            save_memory(
                user_id=USER_ID,
                key=key,
                value=value,
            )

            add_short_term_memory(
                short_term_memory,
                "User",
                user_message,
            )

            if key == "name":

                answer = (
                    f"Got it. I will remember your name as {value}."
                )

            else:

                answer = (
                    f"Got it. I will remember {key} as {value}."
                )

            add_short_term_memory(
                short_term_memory,
                "AI",
                answer,
            )

            print(
                f"AI: {answer}"
            )

            continue


        # ====================================================
        # NAME QUESTION
        # ====================================================

        name_questions = [
            "what is my name",
            "what's my name",
            "tell me my name",
            "do you know my name",
        ]

        if user_message.lower() in name_questions:

            name = get_memory(
                user_id=USER_ID,
                key="name",
            )

            if name:

                answer = (
                    f"Your name is {name}."
                )

            else:

                answer = (
                    "I don't know your name yet."
                )

            add_short_term_memory(
                short_term_memory,
                "User",
                user_message,
            )

            add_short_term_memory(
                short_term_memory,
                "AI",
                answer,
            )

            print(
                f"AI: {answer}"
            )

            continue


        # ====================================================
        # GET ALL MEMORIES
        # ====================================================

        memories = get_all_memories(
            user_id=USER_ID
        )

        memory_text = ""

        if memories:

            memory_text = "\n".join(
                f"{m['key']}: {m['value']}"
                for m in memories
            )

        short_term_memory_text = format_short_term_memory(
            short_term_memory
        )


        # ====================================================
        # CREATE PROMPT
        # ====================================================

        prompt = f"""
Known long-term user memories:

{memory_text}

Recent short-term conversation memory:

{short_term_memory_text}

Current user question:

{user_message}

Instructions:

- Use the memories when they are relevant.
- Use short-term memory for current conversation context.
- Do not store normal conversation in long-term memory.
- Long-term memory is only for stable important user facts.
- Do not invent personal information.
- If the user asks about their name, use the stored name.
- Answer normal questions normally.
- If the question is about company policies, use the PDF RAG tool.
"""


        # ====================================================
        # CALL AGENT
        # ====================================================

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


        # ====================================================
        # GET FINAL RESPONSE
        # ====================================================

        messages = result.get(
            "messages",
            []
        )

        if messages:

            answer = messages[-1].content

            add_short_term_memory(
                short_term_memory,
                "User",
                user_message,
            )

            add_short_term_memory(
                short_term_memory,
                "AI",
                answer,
            )

            print()
            print(f"AI: {answer}")
            print()

        else:

            print(
                "AI: I could not generate a response."
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    chat()

from agent.agent import run_agent


def main():

    print("=" * 50)
    print("       LangChain AI Agent")
    print("=" * 50)

    print("Type 'exit' to stop.")
    print()

    # User identity
    user_id = "user_1"

    # Conversation identity
    thread_id = "conversation_1"

    while True:

        user_message = input("You: ")

        if user_message.lower() == "exit":

            print("Goodbye!")

            break

        if not user_message.strip():
            continue

        try:

            response = run_agent(
                user_message=user_message,
                thread_id=thread_id,
                user_id=user_id,
            )

            print()
            print("Agent:", response)
            print()

        except Exception as error:

            print()
            print("Error:", error)
            print()


if __name__ == "__main__":
    main()
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ai_companion.core.prompts import CHARACTER_CARD_PROMPT, ROUTER_PROMPT
from ai_companion.graph.utils.helpers import AsteriskRemovalParser, get_chat_model


class RouterResponse(BaseModel):
    response_type: str = Field(
        description="The response type to give to the user. It must be one of: 'conversation', 'image' or 'audio'"
    )


def get_router_chain():
    # Simplified router without structured output for model compatibility
    from langchain_core.output_parsers import StrOutputParser
    
    model = get_chat_model(temperature=0.3)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ROUTER_PROMPT + "\n\nRespond with ONLY ONE WORD: 'conversation', 'image', or 'audio'"),
            MessagesPlaceholder(variable_name="messages")
        ]
    )

    class SimpleRouterResponse:
        def __init__(self, response_text):
            response_text = response_text.strip().lower()
            if 'image' in response_text:
                self.response_type = 'image'
            elif 'audio' in response_text:
                self.response_type = 'audio'
            else:
                self.response_type = 'conversation'
    
    chain = prompt | model | StrOutputParser()
    
    async def parse_router_response(messages):
        result = await chain.ainvoke(messages)
        return SimpleRouterResponse(result)
    
    class RouterChain:
        async def ainvoke(self, input_data):
            return await parse_router_response(input_data)
    
    return RouterChain()


def get_character_response_chain(summary: str = ""):
    model = get_chat_model()
    system_message = CHARACTER_CARD_PROMPT

    if summary:
        system_message += f"\n\nSummary of conversation earlier between Ava and the user: {summary}"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    return prompt | model | AsteriskRemovalParser()

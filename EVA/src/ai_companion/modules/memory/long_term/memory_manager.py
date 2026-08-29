import json
import logging
import re
import uuid
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from ai_companion.core.prompts import MEMORY_ANALYSIS_PROMPT
from ai_companion.modules.memory.long_term.vector_store import (
    get_vector_store,
)
from ai_companion.settings import settings

logger = logging.getLogger(__name__)


class MemoryAnalysis(BaseModel):
    """Result of analyzing a message for memory-worthy content."""

    is_important: bool = Field(
        ...,
        description=(
            "Whether the message contains information "
            "important enough to remember long-term."
        ),
    )

    formatted_memory: Optional[str] = Field(
        default=None,
        description=(
            "A concise statement of the information "
            "that should be remembered."
        ),
    )


class MemoryManager:
    """Manager responsible for long-term user memories."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.logger = logger

        self.llm = ChatGroq(
            model=settings.SMALL_TEXT_MODEL_NAME,
            api_key=settings.GROQ_API_KEY,
            temperature=0.1,
            max_retries=2,
        )

    async def _analyze_memory(
        self,
        message: str,
    ) -> MemoryAnalysis:
        """
        Analyze a message and determine whether it contains
        useful long-term information.
        """

        if not message or not message.strip():
            return MemoryAnalysis(
                is_important=False,
                formatted_memory=None,
            )

        prompt = MEMORY_ANALYSIS_PROMPT.format(
            message=message
        )

        try:
            response = await self.llm.ainvoke(prompt)

            content = (
                response.content
                if hasattr(response, "content")
                else str(response)
            )

            content = str(content).strip()

            # Remove markdown JSON fences.
            cleaned_content = re.sub(
                r"```(?:json)?",
                "",
                content,
                flags=re.IGNORECASE,
            ).strip()

            cleaned_content = cleaned_content.replace(
                "```",
                ""
            ).strip()

            # Find JSON object.
            json_match = re.search(
                r"\{.*\}",
                cleaned_content,
                re.DOTALL,
            )

            if not json_match:
                self.logger.warning(
                    "Memory analysis returned no valid JSON."
                )

                return MemoryAnalysis(
                    is_important=False,
                    formatted_memory=None,
                )

            data = json.loads(
                json_match.group()
            )

            return MemoryAnalysis(
                is_important=bool(
                    data.get("is_important", False)
                ),
                formatted_memory=data.get(
                    "formatted_memory"
                ),
            )

        except Exception as e:
            self.logger.warning(
                "Failed to analyze memory: %s",
                e,
                exc_info=True,
            )

            return MemoryAnalysis(
                is_important=False,
                formatted_memory=None,
            )

    async def extract_and_store_memories(
        self,
        message: BaseMessage,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Extract important information from a human message
        and store it permanently for the specified user.
        """

        # Only remember human/user messages.
        msg_type = getattr(message, "type", None)

        if (
            msg_type != "human"
            and not isinstance(message, HumanMessage)
        ):
            return

        content = (
            message.content
            if isinstance(message.content, str)
            else str(message.content)
        )

        if not content.strip():
            return

        effective_user_id = (
            str(user_id)
            if user_id
            else "default_user"
        )

        self.logger.info(
            "Analyzing message for user '%s'",
            effective_user_id,
        )

        analysis = await self._analyze_memory(
            content
        )

        if not analysis.is_important:
            self.logger.debug(
                "Message is not important enough to store."
            )
            return

        if not analysis.formatted_memory:
            self.logger.debug(
                "No formatted memory returned."
            )
            return

        memory_text = analysis.formatted_memory.strip()

        if not memory_text:
            return

        # Prevent duplicate/similar memories.
        try:
            similar = (
                self.vector_store.find_similar_memory(
                    memory_text,
                    user_id=effective_user_id,
                )
            )

            if similar:
                self.logger.info(
                    "Similar memory already exists for "
                    "user '%s': %s",
                    effective_user_id,
                    memory_text,
                )
                return

        except Exception as e:
            self.logger.warning(
                "Could not check for similar memory: %s",
                e,
                exc_info=True,
            )

        # Store memory.
        try:
            memory_id = str(uuid.uuid4())

            metadata = {
                "id": memory_id,
                "user_id": effective_user_id,
                "timestamp": datetime.now().isoformat(),
            }

            self.vector_store.store_memory(
                text=memory_text,
                metadata=metadata,
                user_id=effective_user_id,
            )

            self.logger.info(
                "Stored long-term memory for user '%s': %s",
                effective_user_id,
                memory_text,
            )

        except Exception as e:
            self.logger.error(
                "Failed to store memory for user '%s': %s",
                effective_user_id,
                e,
                exc_info=True,
            )

    def get_relevant_memories(
        self,
        context: str,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """
        Retrieve relevant and general memories belonging
        only to the specified user.
        """

        effective_user_id = (
            str(user_id)
            if user_id
            else "default_user"
        )

        result = []
        seen = set()

        try:
            # Semantic/relevant memories.
            relevant_memories = []

            if context and context.strip():
                relevant_memories = (
                    self.vector_store.search_memories(
                        context,
                        user_id=effective_user_id,
                        k=settings.MEMORY_TOP_K,
                    )
                )

            # General memories for this user.
            all_memories = (
                self.vector_store.get_all_memories(
                    user_id=effective_user_id,
                    limit=10,
                )
            )

            # Relevant memories first.
            combined = (
                relevant_memories + all_memories
            )

            for memory in combined:
                memory_text = getattr(
                    memory,
                    "text",
                    None,
                )

                if not memory_text:
                    continue

                memory_text = str(
                    memory_text
                ).strip()

                if not memory_text:
                    continue

                if memory_text in seen:
                    continue

                seen.add(memory_text)
                result.append(memory_text)

                self.logger.debug(
                    "Retrieved memory for user '%s': %s",
                    effective_user_id,
                    memory_text,
                )

            self.logger.info(
                "Retrieved %d memories for user '%s'",
                len(result),
                effective_user_id,
            )

            return result

        except Exception as e:
            self.logger.error(
                "Failed to retrieve memories for user '%s': %s",
                effective_user_id,
                e,
                exc_info=True,
            )

            return []

    def format_memories_for_prompt(
        self,
        memories: List[str],
    ) -> str:
        """Convert memories into prompt-ready bullet points."""

        if not memories:
            return "No previous memories recorded yet."

        return "\n".join(
            f"- {memory}"
            for memory in memories
        )


@lru_cache(maxsize=1)
def get_memory_manager() -> MemoryManager:
    """
    Create and return a memory manager.

    The manager itself does not hold the memories.
    Persistent memories are stored by the vector store.
    """

    return MemoryManager()
import base64
import logging
import os
import urllib.parse
import urllib.request
from typing import Optional

from ai_companion.core.exceptions import TextToImageError
from ai_companion.core.prompts import IMAGE_ENHANCEMENT_PROMPT, IMAGE_SCENARIO_PROMPT
from ai_companion.settings import settings
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from together import Together


class ScenarioPrompt(BaseModel):
    """Class for the scenario response"""

    narrative: str = Field(..., description="The AI's narrative response to the question")
    image_prompt: str = Field(..., description="The visual prompt to generate an image representing the scene")


class EnhancedPrompt(BaseModel):
    """Class for the text prompt"""

    content: str = Field(
        ...,
        description="The enhanced text prompt to generate an image",
    )


class TextToImage:
    """A class to handle text-to-image generation using Together AI with fallback."""

    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        """Initialize the TextToImage class and validate environment variables."""
        self._validate_env_vars()
        self._together_client: Optional[Together] = None
        self.logger = logging.getLogger(__name__)

    def _validate_env_vars(self) -> None:
        """Validate that required environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not getattr(settings, var, None)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    @property
    def together_client(self) -> Together:
        """Get or create Together client instance using singleton pattern."""
        if self._together_client is None:
            self._together_client = Together(api_key=settings.TOGETHER_API_KEY)
        return self._together_client

    async def generate_image(self, prompt: str, output_path: str = "") -> bytes:
        """Generate an image from a prompt using Together AI or free fallback."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        self.logger.info(f"Generating image for prompt: '{prompt}'")

        # Attempt Together AI only if API key is configured
        together_key = getattr(settings, "TOGETHER_API_KEY", "") or ""
        if together_key.strip():
            try:
                response = self.together_client.images.generate(
                    prompt=prompt,
                    model=settings.TTI_MODEL_NAME,
                    width=1024,
                    height=768,
                    steps=4,
                    n=1,
                    response_format="b64_json",
                )
                image_data = base64.b64decode(response.data[0].b64_json)
                if output_path:
                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    self.logger.info(f"Image saved to {output_path}")
                return image_data
            except Exception as e:
                self.logger.warning(f"Together AI image generation failed ({e}). Falling back to Pollinations FLUX...")
        else:
            self.logger.info("TOGETHER_API_KEY not set — using Pollinations FLUX fallback directly.")

        # Fallback: Pollinations FLUX (free, no key required)
        try:
            encoded_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=768&seed=42&model=flux"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                image_data = resp.read()
        except Exception as fallback_err:
            raise TextToImageError(f"Failed to generate image via both Together AI and fallback: {fallback_err}") from fallback_err

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)
            self.logger.info(f"Image saved to {output_path}")

        return image_data

    async def create_scenario(self, chat_history: list = None) -> ScenarioPrompt:
        """Creates a first-person narrative scenario and corresponding image prompt based on chat history."""
        try:
            from langchain_core.output_parsers import StrOutputParser
            
            formatted_history = "\n".join([f"{msg.type.title()}: {msg.content}" for msg in chat_history[-5:]])

            self.logger.info("Creating scenario from chat history")

            llm = ChatGroq(
                model=settings.TEXT_MODEL_NAME,
                api_key=settings.GROQ_API_KEY,
                temperature=0.4,
                max_retries=2,
            )

            # Use text parsing instead of structured output
            prompt_text = IMAGE_SCENARIO_PROMPT + "\n\nFormat your response as:\nNARRATIVE: [your narrative here]\nIMAGE_PROMPT: [image prompt here]"
            
            chain = (
                PromptTemplate(
                    input_variables=["chat_history"],
                    template=prompt_text,
                )
                | llm
                | StrOutputParser()
            )

            response = chain.invoke({"chat_history": formatted_history})
            
            # Parse the response
            narrative = ""
            image_prompt = ""
            
            if "NARRATIVE:" in response and "IMAGE_PROMPT:" in response:
                parts = response.split("IMAGE_PROMPT:")
                narrative = parts[0].replace("NARRATIVE:", "").strip()
                image_prompt = parts[1].strip()
            else:
                # Fallback: use the whole response as image prompt
                narrative = "Here's what I'm seeing..."
                image_prompt = response.strip()
            
            scenario = ScenarioPrompt(narrative=narrative, image_prompt=image_prompt)
            self.logger.info(f"Created scenario: {scenario}")

            return scenario

        except Exception as e:
            raise TextToImageError(f"Failed to create scenario: {str(e)}") from e

    async def enhance_prompt(self, prompt: str) -> str:
        """Enhance a simple prompt with additional details and context."""
        try:
            from langchain_core.output_parsers import StrOutputParser
            
            self.logger.info(f"Enhancing prompt: '{prompt}'")

            llm = ChatGroq(
                model=settings.TEXT_MODEL_NAME,
                api_key=settings.GROQ_API_KEY,
                temperature=0.25,
                max_retries=2,
            )

            chain = (
                PromptTemplate(
                    input_variables=["prompt"],
                    template=IMAGE_ENHANCEMENT_PROMPT,
                )
                | llm
                | StrOutputParser()
            )

            enhanced_prompt = chain.invoke({"prompt": prompt})
            self.logger.info(f"Enhanced prompt: '{enhanced_prompt}'")

            return enhanced_prompt

        except Exception as e:
            raise TextToImageError(f"Failed to enhance prompt: {str(e)}") from e

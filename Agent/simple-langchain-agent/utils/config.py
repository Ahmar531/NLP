

import os

from dotenv import load_dotenv


# Load variables from the .env file
load_dotenv()


# Get the Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# Make sure the API key exists
if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. Please add it to your .env file."
    )
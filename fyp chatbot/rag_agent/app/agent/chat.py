import os

from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_groq import ChatGroq

from app.rag.tools import search_pdf_documents


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# GROQ MODEL
# ============================================================

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
)


# ============================================================
# LLM
# ============================================================

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0,
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a helpful AI assistant.

You have access to a tool called:
search_pdf_documents

Your responsibilities:

1. If the user asks about uploaded company documents,
   company policies, rules, procedures, or information
   contained inside PDFs, use search_pdf_documents.

2. Answer PDF-related questions using the retrieved
   document information.

3. Do not invent information from company documents.

4. If the requested information is not found in the
   uploaded documents, clearly say that it was not found.

5. For normal/general questions that are unrelated to
   company documents, answer normally using your general
   knowledge.

6. If user information is provided in the prompt as
   long-term memory, use it when relevant.

7. Do not confuse company information with personal
   user information.

8. Give clear and concise answers.

9. When document metadata is available, mention the
   relevant PDF name and page number.
"""


# ============================================================
# CREATE AGENT
# ============================================================

agent = create_agent(
    model=llm,

    tools=[
        search_pdf_documents
    ],

    system_prompt=SYSTEM_PROMPT,
)
import os

from langchain_core.tools import tool

from app.rag.vector_store import search_documents


TOP_K = int(
    os.getenv("TOP_K", "5")
)


@tool
def search_pdf_documents(query: str) -> str:
    """
    Search the uploaded PDF documents.

    Use this tool whenever the user asks a question
    that may be answered using uploaded PDFs.
    """

    documents = search_documents(
        query=query,
        k=TOP_K,
    )

    if not documents:
        return "No relevant information was found in the uploaded PDFs."

    results = []

    for document in documents:

        pdf_name = document.metadata.get(
            "pdf_name",
            "Unknown PDF"
        )

        page_number = document.metadata.get(
            "page_number",
            "Unknown"
        )

        content = document.page_content

        results.append(
            f"""
PDF: {pdf_name}
Page: {page_number}

Content:
{content}
"""
        )

    return "\n\n---\n\n".join(results)
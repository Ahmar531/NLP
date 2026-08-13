from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def process_pdf(
    pdf_path: str,
    pdf_name: str,
):
    """
    Load PDF, extract text page by page,
    attach metadata, and split into chunks.
    """

    loader = PyPDFLoader(pdf_path)

    documents = loader.load()

    for document in documents:

        # PyPDFLoader page is normally 0-based.
        page_number = document.metadata.get("page", 0) + 1

        document.metadata.update(
            {
                "pdf_name": pdf_name,
                "page_number": page_number,
                "source": pdf_name,
            }
        )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = text_splitter.split_documents(documents)

    return chunks
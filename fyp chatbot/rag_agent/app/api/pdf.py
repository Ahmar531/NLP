import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.rag.pdf_processor import process_pdf
from app.rag.vector_store import add_documents


router = APIRouter(
    prefix="/pdf",
    tags=["PDF"],
)


UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR", "./uploads")
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post("/upload")
async def upload_pdf(
    file1: UploadFile = File(...),           # ← 5 alag file fields
    file2: UploadFile = File(None),
    file3: UploadFile = File(None),
    file4: UploadFile = File(None),
    file5: UploadFile = File(None),
):
    # Sirf jo files di hain unko collect karo
    all_files = [f for f in [file1, file2, file3, file4, file5] if f is not None]

    results = []

    for file in all_files:

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="One or more files have no name."
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename}: Only PDF files are allowed."
            )

        file_path = UPLOAD_DIR / file.filename

        try:

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(
                    file.file,
                    buffer
                )

            chunks = process_pdf(
                pdf_path=str(file_path),
                pdf_name=file.filename,
            )

            number_of_chunks = add_documents(
                chunks
            )

            results.append({
                "pdf_name": file.filename,
                "chunks_created": number_of_chunks,
            })

        except Exception as e:

            raise HTTPException(
                status_code=500,
                detail=f"Error processing {file.filename}: {str(e)}"
            )

        finally:

            await file.close()

    return {
        "message": "All PDFs uploaded and indexed successfully.",
        "total_files": len(results),
        "files": results,
    }
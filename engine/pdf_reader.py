import os
import glob
import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)


def get_pdfs_from_folder(folder_path: str) -> list[str]:
    """Return a list of all PDF file paths in the given folder."""
    pattern = os.path.join(folder_path, "*.pdf")
    pdfs = sorted(glob.glob(pattern))
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in {folder_path}")
    return pdfs

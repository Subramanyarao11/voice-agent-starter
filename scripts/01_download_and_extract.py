"""
Step 1 of the data pipeline: download the myScheme dataset's PDFs from
Hugging Face and extract raw text from each.

The dataset (shrijayan/gov_myscheme) is 723 PDFs under text_data/, NOT a
clean CSV/JSON despite what the dataset card says — verified by browsing the
actual repo contents. So this step exists whether we like it or not.

Usage:
    python scripts/01_download_and_extract.py

Output:
    data/raw_pdfs/*.pdf          (downloaded)
    data/structured/raw_text.jsonl   (one JSON line per scheme: id, filename, raw_text)

Requires: huggingface_hub, pdfplumber
    pip install huggingface_hub pdfplumber
"""
import json
from pathlib import Path

from huggingface_hub import list_repo_files, hf_hub_download
import pdfplumber

REPO_ID = "shrijayan/gov_myscheme"
REPO_TYPE = "dataset"
RAW_PDF_DIR = Path("data/raw_pdfs")
OUTPUT_PATH = Path("data/structured/raw_text.jsonl")


def download_pdfs() -> list[Path]:
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    files = list_repo_files(REPO_ID, repo_type=REPO_TYPE)
    pdf_files = [f for f in files if f.startswith("text_data/") and f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs in the dataset")

    local_paths = []
    for f in pdf_files:
        local_path = hf_hub_download(
            repo_id=REPO_ID, repo_type=REPO_TYPE, filename=f, local_dir="data/raw_pdfs_hf_cache"
        )
        local_paths.append(Path(local_path))
    return local_paths


def extract_text(pdf_path: Path) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def main():
    pdf_paths = download_pdfs()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out:
        for i, pdf_path in enumerate(pdf_paths, 1):
            try:
                raw_text = extract_text(pdf_path)
            except Exception as e:
                print(f"  [SKIP] {pdf_path.name}: extraction failed ({e})")
                continue

            if not raw_text.strip():
                print(f"  [SKIP] {pdf_path.name}: empty extracted text (likely scanned image PDF)")
                continue

            record = {
                "id": pdf_path.stem,
                "filename": pdf_path.name,
                "raw_text": raw_text,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

            if i % 50 == 0:
                print(f"  ...{i}/{len(pdf_paths)} extracted")

    print(f"Done. Raw text written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

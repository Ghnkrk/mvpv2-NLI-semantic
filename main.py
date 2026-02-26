import os
import sys
from datetime import datetime

from engine.loader import load_rules
from engine.matcher import normalize_text, split_sentences
from engine.evaluator import evaluate_clause
from engine.pdf_reader import extract_text_from_pdf, get_pdfs_from_folder
from engine.report import generate_report, generate_pdf_report


INPUT_FOLDER = "checkPdf"
OUTPUT_FOLDER = "reports"
RULES_PATH = "rules.json"


def run_engine(pdf_path: str) -> dict:
    """Run the compliance engine on a single PDF and return results."""
    rules = load_rules(RULES_PATH)
    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text.strip():
        print(f"  ⚠  No text extracted from {pdf_path}")
        return {}

    text = normalize_text(raw_text)
    sentences = split_sentences(raw_text)

    results = {}
    for clause_id, clause in rules.items():
        results[clause_id] = evaluate_clause(clause, text, sentences)

    return results


def main():
    """Process all PDFs in checkPdf/ and generate gap reports in reports/."""
    pdf_files = get_pdfs_from_folder(INPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print(f"Found {len(pdf_files)} PDF(s) in {INPUT_FOLDER}/\n")

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        stem = os.path.splitext(filename)[0]

        print(f"▶ Processing: {filename}")

        results = run_engine(pdf_path)

        if not results:
            continue

        # JSON report (console + file)
        json_str = generate_report(results)
        json_out = os.path.join(OUTPUT_FOLDER, f"{stem}_report.json")
        with open(json_out, "w") as f:
            f.write(json_str)
        print(f"  ✓ JSON report → {json_out}")

        # PDF report
        pdf_out = os.path.join(OUTPUT_FOLDER, f"{stem}_report.pdf")
        generate_pdf_report(results, filename, pdf_out)
        print(f"  ✓ PDF report  → {pdf_out}")

        print()

    print("Done.")


if __name__ == "__main__":
    main()

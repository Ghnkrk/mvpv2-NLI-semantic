# NABH Compliance Engine (MVP v2)

Deterministic + semantic compliance engine for hospital SOPs against NABH standards.

## 📁 Folder Structure
- `main.py` — Main entry point
- `rules.json` — Compliance logic, signals, archetypes
- `engine/` — Core modules:
    - `loader.py` — Loads and validates `rules.json`
    - `matcher.py` — Text normalization and exact signal matching
    - `semantic.py` — Semantic enhancement layer (sentence-transformers)
    - `evaluator.py` — Archetype-based compliance scoring
    - `pdf_reader.py` — PDF text extraction
    - `report.py` — JSON and PDF report generation
- `checkPdf/` — Input PDF files
- `reports/` — Generated reports (JSON + PDF)
- `test_regression.py` — Regression tests against weak/strong docs

## 🚀 How to Use

```bash
# Run on specific files
python main.py path/to/file1.pdf path/to/file2.pdf

# Run on all files in checkPdf/
python main.py

# Debug mode (see exact/semantic scores per block)
python main.py --debug

# Regression tests
python test_regression.py
```

## 🧠 How It Works
1. **Exact matching** — keyword signals matched against document text
2. **Semantic enhancement** — if exact score is below threshold, sentence-transformers finds paraphrased evidence (score can only go UP)
3. **Archetype evaluation** — mandatory block rules determine COMPLIANT / PARTIAL / NON_COMPLIANT
4. **Mandatory safeguard** — blocks with zero exact matches remain failures regardless of semantic matches

# NABH Compliance Engine (MVP v2)

Simple deterministic engine to check hospital SOPs/manuscripts against NABH standards.

## 📁 Folder Structure
- `main.py`: Main entry point.
- `rules.json`: Contains the compliance logic, signals, and archetypes.
- `engine/`: Core logic modules:
    - `loader.py`: Loads and validates `rules.json`.
    - `matcher.py`: Text normalization and signal matching.
    - `evaluator.py`: Archetype-based compliance scoring.
    - `pdf_reader.py`: Extracts text from PDF files.
    - `report.py`: Generates JSON and PDF gap reports.
- `checkPdf/`: Put your input PDF files here.
- `reports/`: JSON and PDF reports are generated here.
- `test_regression.py`: Script to verify the engine against known "weak" and "strong" docs.

## 🚀 How to Use

### 1. Run on all files in `checkPdf/`
```bash
python main.py
```

### 2. Run on specific files
```bash
python main.py path/to/file1.pdf path/to/file2.pdf
```

### 3. Debug Mode (See reasoning trace)
```bash
python main.py --debug
```

### 4. Run Regression Tests
```bash
python test_regression.py
```

## 🧠 Core Logic Note
The engine currently uses **exact signal matching**. 
- **NON_COMPLIANT**: Zero evidence for mandatory blocks.
- **PARTIAL**: Evidence exists but is below threshold or mandatory blocks are missing.
- **COMPLIANT**: All mandatory evidence found with sufficient score.

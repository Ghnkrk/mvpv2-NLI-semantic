import os
import json
from datetime import datetime
from engine.loader import load_rules
from engine.matcher import normalize_text, split_sentences
from engine.evaluator import evaluate_clause
from engine.pdf_reader import extract_text_from_pdf
from engine.report import generate_report, generate_pdf_report
from engine.llm_suggester import generate_suggestions

class ComplianceService:
    def __init__(self, rules_path: str = "rules.json"):
        self.rules_path = rules_path
        self.rules = load_rules(rules_path)

    def analyze_document(self, pdf_path: str, output_folder: str = "reports") -> dict:
        """
        Complete analysis pipeline for a single PDF:
        Extraction -> Engine -> LLM Suggestions -> Report Generation
        """
        filename = os.path.basename(pdf_path)
        stem = os.path.splitext(filename)[0]
        os.makedirs(output_folder, exist_ok=True)

        # 1. Core Engine
        raw_text = extract_text_from_pdf(pdf_path)
        if not raw_text.strip():
            return {"error": f"No text extracted from {filename}"}

        text = normalize_text(raw_text)
        sentences = split_sentences(raw_text)

        results = {}
        for clause_id, clause in self.rules.items():
            results[clause_id] = evaluate_clause(clause, text, sentences)

        # 2. JSON Intermediate Report
        report_json_str = generate_report(results)
        report_data = json.loads(report_json_str)

        # 3. AI Suggestions
        suggestions = generate_suggestions(report_data)
        report_data["llm_suggestions"] = suggestions

        # 4. Final Output Generation
        final_json_str = json.dumps(report_data, indent=2)
        json_out = os.path.join(output_folder, f"{stem}_report.json")
        with open(json_out, "w") as f:
            f.write(final_json_str)

        pdf_out = os.path.join(output_folder, f"{stem}_report.pdf")
        generate_pdf_report(results, filename, pdf_out, suggestions=suggestions)
        
        return {
            "filename": filename,
            "report_data": report_data,
            "json_path": json_out,
            "pdf_path": pdf_out
        }

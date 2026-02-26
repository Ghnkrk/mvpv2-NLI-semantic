#!/usr/bin/env python3
"""Regression test script — runs weak + strong PDFs and validates results."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from engine.loader import load_rules
from engine.matcher import normalize_text, split_sentences
from engine.evaluator import evaluate_clause
from engine.pdf_reader import extract_text_from_pdf
from engine.report import generate_report


def run_on_pdf(pdf_path):
    rules = load_rules("rules.json")
    raw = extract_text_from_pdf(pdf_path)
    text = normalize_text(raw)
    sentences = split_sentences(raw)
    results = {}
    for cid, clause in rules.items():
        results[cid] = evaluate_clause(clause, text, sentences)
    return results


def print_results(name, results):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    for cid, r in results.items():
        print(f"  {cid}: {r['status']} (score={r['clause_score']})")
        print(f"    Mandatory failures: {r['mandatory_failures'] or '(none)'}")
        print(f"    Trace: {r['decision_trace']}")
        for bn, sc in r['block_scores'].items():
            ev = r['matched_evidence'].get(bn, [])
            print(f"      {bn}: {sc}  signals={ev}")
    print()


# --- WEAK DOC ---
print("Processing weak-doc.pdf...")
weak = run_on_pdf("checkPdf/weak-doc.pdf")
print_results("WEAK DOC", weak)

# --- STRONG DOC ---
print("Processing strong-doc.pdf...")
strong = run_on_pdf("checkPdf/strong-doc.pdf")
print_results("STRONG DOC", strong)

# --- VALIDATION ---
print("="*60)
print("  REGRESSION VALIDATION")
print("="*60)

errors = []

# Weak expectations: IMS4 → NON_COMPLIANT, others → PARTIAL
if weak["IMS4"]["status"] != "NON_COMPLIANT":
    errors.append(f"WEAK IMS4: expected NON_COMPLIANT, got {weak['IMS4']['status']}")
for cid in ["IMS3", "CQI1", "HRM2a"]:
    if weak[cid]["status"] not in ("PARTIAL", "NON_COMPLIANT"):
        errors.append(f"WEAK {cid}: expected PARTIAL/NON_COMPLIANT, got {weak[cid]['status']}")

# Strong expectations: all → COMPLIANT
for cid in ["IMS3", "IMS4", "CQI1", "HRM2a"]:
    if strong[cid]["status"] != "COMPLIANT":
        errors.append(f"STRONG {cid}: expected COMPLIANT, got {strong[cid]['status']}")

if errors:
    print("\n❌ FAILURES:")
    for e in errors:
        print(f"  • {e}")
    sys.exit(1)
else:
    print("\n✅ ALL REGRESSION TESTS PASSED")
    sys.exit(0)

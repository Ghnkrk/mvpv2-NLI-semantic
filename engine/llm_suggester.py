import os
import json
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Note: Groq uses an OpenAI-compatible endpoint, which is why the URL contains "/openai/".
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "llama-3.1-8b-instant"
TEMPERATURE = 0.2

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a NABH accreditation consultant. I will provide a list of clauses that are not fully compliant.
For each clause, provide structured improvement guidance.

Clauses to analyze:
{clauses_data}

Provide the output as a SINGLE JSON object where the keys are the Clause IDs, and the values follow this structure:
{{
  "improvement_summary": "...",
  "required_documents": ["...", "..."],
  "operational_controls": ["...", "..."],
  "audit_readiness_tip": "..."
}}

Constraints:
1. Do NOT re-evaluate compliance status.
2. Do NOT contradict the provided deterministic status.
3. Only provide actionable improvement recommendations.
4. Be concise and practical.
5. Return ONLY the JSON object.
"""

def _call_groq(prompt: str) -> str:
    """Make a synchronous call to the Groq API."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in environment.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a professional NABH consultant. You MUST output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": TEMPERATURE
    }

    logger.info(f"Calling Groq API with model: {MODEL_NAME}")
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=45)
        if response.status_code != 200:
            logger.error(f"Groq API Error {response.status_code}: {response.text}")
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise
    
    data = response.json()
    return data["choices"][0]["message"]["content"]

def _parse_llm_json(content: str) -> dict:
    """Parse JSON from LLM response with extraction fallback."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise

def generate_suggestions(report_json: dict) -> dict:
    """
    Generate LLM suggestions for non-compliant and partial clauses using a single batch call.
    Returns a dictionary mapping clause_id to suggestions.
    """
    try:
        clauses = report_json.get("clauses", {})
        batch_data = []
        target_ids = []

        for cid, data in clauses.items():
            if data.get("status") in ["PARTIAL", "NON_COMPLIANT"]:
                target_ids.append(cid)
                
                # Weak blocks: score < 0.5 but > 0
                block_scores = data.get("block_scores", {})
                weak_blocks = [n for n, s in block_scores.items() if 0 < s < 0.5]
                
                batch_data.append({
                    "id": cid,
                    "intent": data.get("intent", "N/A"),
                    "status": data.get("status"),
                    "mandatory_failures": data.get("mandatory_failures", []),
                    "weak_blocks": weak_blocks,
                    "decision_trace": data.get("decision_trace", "N/A")
                })

        if not batch_data:
            return {}

        prompt = PROMPT_TEMPLATE.format(clauses_data=json.dumps(batch_data, indent=2))

        # Call Groq with a single retry
        content = None
        for attempt in range(2):
            try:
                content = _call_groq(prompt)
                parsed = _parse_llm_json(content)
                
                # Ensure all target IDs are present, even if empty
                final_suggestions = {}
                for cid in target_ids:
                    final_suggestions[cid] = parsed.get(cid, {
                        "improvement_summary": "Suggestion unavailable for this clause.",
                        "required_documents": [],
                        "operational_controls": [],
                        "audit_readiness_tip": "N/A"
                    })
                return final_suggestions
            except Exception as e:
                logger.warning(f"LLM batch attempt {attempt+1} failed: {e}")
                if attempt == 1:
                    # Final fallback
                    return {cid: {
                        "improvement_summary": "Error generating suggestions via API.",
                        "required_documents": [],
                        "operational_controls": [],
                        "audit_readiness_tip": f"Technical error: {str(e)}"
                    } for cid in target_ids}
        
    except Exception as e:
        logger.error(f"Critical failure in generate_suggestions: {e}")
        return {}

    return {}

import re
import nltk
from nltk.stem import PorterStemmer

# Ensure required NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

stemmer = PorterStemmer()

def normalize_text(text: str) -> str:
    """Lowercase, replace hyphens with spaces, and strip non-alphanumeric chars."""
    if not text:
        return ""
    text = text.lower()
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text

def tokenize_and_stem(text: str) -> list[str]:
    """Normalize text, tokenize, filter short tokens, and stem."""
    normalized = normalize_text(text)
    tokens = normalized.split()
    # Filter out tokens length <= 2 to ignore common stop words/noise
    tokens = [t for t in tokens if len(t) > 2]
    stemmed = [stemmer.stem(t) for t in tokens]
    return stemmed

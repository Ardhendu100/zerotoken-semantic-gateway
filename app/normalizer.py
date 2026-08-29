import re

# Pre-compiled regex patterns for zero-latency performance
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
IP_REGEX = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
CREDIT_CARD_REGEX = re.compile(r'\b(?:\d[ -]*?){13,16}\b')

def scrub_pii(text: str) -> str:
    """Scrub sensitive personal identifiers from input text."""
    text = EMAIL_REGEX.sub('<EMAIL>', text)
    text = PHONE_REGEX.sub('<PHONE_NUMBER>', text)
    text = IP_REGEX.sub('<IP_ADDRESS>', text)
    text = CREDIT_CARD_REGEX.sub('<CREDIT_CARD>', text)
    return text

def normalize_text(text: str) -> str:
    """Canonicalize text for vector similarity comparison."""
    # 1. Scrub PII
    text = scrub_pii(text)
    # 2. Lowercase
    text = text.lower()
    # 3. Collapse multiple whitespace/newlines into single space
    text = re.sub(r'\s+', ' ', text)
    # 4. Strip leading/trailing whitespaces
    return text.strip()
"""
Look Out - Content Hashing
Generates digital fingerprints for text comparison.
"""
import hashlib

def generate_hash(text: str) -> str:
    """
    Takes a string of text and returns a 64-character SHA-256 hash.
    """
    if not text:
        return ""
    
    # Text must be encoded into bytes before hashing
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
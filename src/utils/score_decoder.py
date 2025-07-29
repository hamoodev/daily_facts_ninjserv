"""
AOTTG Score Code Decoder

Utilities for decoding and verifying obfuscated score codes from Attack on Titan Tribute Game.
"""

from typing import Dict, Any


# Obfuscation map for decoding
OBF_MAP_REVERSE = {
    "Q": "0", "W": "1", "E": "2", "R": "3", "T": "4",
    "Y": "5", "U": "6", "I": "7", "O": "8", "P": "9",
    "A": "|", "S": "+"
}


def compute_checksum(decoded_str: str) -> str:
    """
    Compute checksum for decoded score string
    
    Args:
        decoded_str: The decoded score string (e.g., "15|3")
        
    Returns:
        Checksum as string
    """
    charset = "0123456789+|"
    sum_val = 0
    
    for char in decoded_str:
        if char in charset:
            index = charset.index(char)
            sum_val += index * 7
            
    return str(sum_val % 100)


def decode_score_code(encoded_part: str) -> str:
    """
    Decode the obfuscated part of the score code
    
    Args:
        encoded_part: The obfuscated string (e.g., "WYAR")
        
    Returns:
        Decoded string (e.g., "15|3")
    """
    decoded = ""
    
    for char in encoded_part:
        decoded += OBF_MAP_REVERSE.get(char, "?")
        
    return decoded


def decode_and_verify(code: str) -> Dict[str, Any]:
    """
    Decode and verify a complete score code
    
    Args:
        code: Full score code (e.g., "WYAR-126")
        
    Returns:
        Dictionary with validation results and decoded data
    """
    try:
        # Split code into encoded part and checksum
        if "-" not in code:
            return {"valid": False, "error": "Invalid format: missing checksum separator"}
            
        encoded_part, checksum_part = code.split("-", 1)
        
        if not encoded_part or not checksum_part:
            return {"valid": False, "error": "Invalid format: empty parts"}
            
    except ValueError:
        return {"valid": False, "error": "Invalid format: cannot parse code"}
    
    # Decode the score
    decoded = decode_score_code(encoded_part)
    
    # Check for invalid characters in decoded string
    if "?" in decoded:
        return {"valid": False, "error": "Invalid characters in score code"}
    
    # Verify format (should contain exactly one "|")
    if decoded.count("|") != 1:
        return {"valid": False, "error": "Invalid score format"}
        
    # Validate checksum
    expected_checksum = compute_checksum(decoded)
    is_valid = expected_checksum == checksum_part
    
    result = {
        "valid": is_valid,
        "decoded": decoded,
        "expected_checksum": expected_checksum,
        "provided_checksum": checksum_part
    }
    
    if not is_valid:
        result["error"] = "Checksum verification failed"
    
    return result


def parse_score_data(decoded_str: str) -> Dict[str, Any]:
    """
    Parse decoded score string into kills and deaths
    
    Args:
        decoded_str: Decoded score string (e.g., "15|3")
        
    Returns:
        Dictionary with kills and deaths as integers
    """
    try:
        parts = decoded_str.split("|")
        if len(parts) != 2:
            return {"valid": False, "error": "Invalid score format"}
            
        kills = int(parts[0])
        deaths = int(parts[1])
        
        # Validate reasonable ranges
        if kills < 0 or deaths < 0:
            return {"valid": False, "error": "Invalid score values: negative numbers"}
            
        if kills > 999999 or deaths > 999999:
            return {"valid": False, "error": "Invalid score values: unrealistic numbers"}
        
        return {
            "valid": True,
            "kills": kills,
            "deaths": deaths,
            "kd_ratio": kills / deaths if deaths > 0 else float(kills)
        }
        
    except ValueError:
        return {"valid": False, "error": "Invalid score format: non-numeric values"} 
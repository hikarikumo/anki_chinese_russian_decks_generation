def is_chinese_char(char):
    """
    Check if a single character is a Chinese character (汉字).
    Returns True if the character is Chinese, False otherwise.
    
    This function checks if the character falls within common Unicode ranges
    for Chinese characters:
    - CJK Unified Ideographs: U+4E00 - U+9FFF (basic Chinese characters)
    - CJK Unified Ideographs Extension A: U+3400 - U+4DBF (less common)
    """
    # if len(char) != 1:
    #     return False
        
    code_point = ord(char)
    return (0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF)

# Example usage
def test_is_chinese_char():
    test_cases = {
        '我': True,    # Common Chinese character
        'a': False,   # English letter
        '1': False,   # Number
        '。': False,  # Chinese punctuation
        '㐀': True,   # Less common Chinese character from Extension A
        ' ': False,   # Space
    }
    
    for char, expected in test_cases.items():
        result = is_chinese_char(char)
        print(f"Character '{char}': {result} (Expected: {expected})")

if __name__ == "__main__":
    test_is_chinese_char()
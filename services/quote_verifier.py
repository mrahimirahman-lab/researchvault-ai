import re
import unicodedata

def normalized_with_offsets(text):
    chars, offsets = [], []
    i = 0
    while i < len(text):
        # Join words split across physical lines, preserving source offsets.
        m = re.match(r'[-\u00ad][ \t]*\r?\n[ \t]*', text[i:])
        if m:
            i += len(m.group())
            continue
        for ch in unicodedata.normalize('NFKC', text[i]):
            if ch.isspace():
                if chars and chars[-1] != ' ':
                    chars.append(' ')
                    offsets.append(i)
            else:
                chars.append(ch)
                offsets.append(i)
        i += 1
    return ''.join(chars), offsets

def verify_quote(candidate, source):
    """Return the original source substring, never an AI rewrite."""
    needle, _ = normalized_with_offsets(candidate)
    haystack, offsets = normalized_with_offsets(source)
    needle = needle.strip()
    if len(needle) < 10 or len(needle) > 900:
        return None
    pos = haystack.find(needle)
    if pos < 0:
        return None
    return source[offsets[pos]:offsets[pos + len(needle) - 1] + 1]

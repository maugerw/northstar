# load_serialize.py
#
# Pure (WLST-independent) JSON reader and properties helpers.
#
# Jython 2.2 (WebLogic 12c) ships without the json module, so read_json_file()
# tries the standard module first and falls back to a minimal character-level
# parser that handles the exact output produced by extract/jms_serialize.py.
#
# The eval-based fallback is safe here because it processes string literals
# verbatim (never substituting keywords inside them) before calling eval().


def _json_to_python_str(s):
    # Walk the JSON string character by character, copying string literals
    # untouched and replacing the three JSON keywords (true/false/null) with
    # their Python equivalents everywhere else.
    result = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            # String literal: copy verbatim including escape sequences.
            result.append(c)
            i += 1
            while i < n:
                c = s[i]
                result.append(c)
                if c == '\\' and i + 1 < n:
                    # Escaped character: copy the next char too.
                    i += 1
                    result.append(s[i])
                    i += 1
                    continue
                elif c == '"':
                    i += 1
                    break
                i += 1
        elif s[i:i + 4] == 'true':
            result.append('True')
            i += 4
        elif s[i:i + 5] == 'false':
            result.append('False')
            i += 5
        elif s[i:i + 4] == 'null':
            result.append('None')
            i += 4
        else:
            result.append(c)
            i += 1
    return ''.join(result)


def read_json_file(path):
    # Try the standard json module first (Python 2.6+ / Jython 2.7+ / WLS 14c).
    try:
        import json
        f = open(path, 'r')
        try:
            return json.load(f)
        finally:
            f.close()
    except ImportError:
        pass

    # Jython 2.2 fallback: eval after keyword substitution.
    f = open(path, 'r')
    try:
        content = f.read()
    finally:
        f.close()
    return eval(_json_to_python_str(content))


def get(d, key, default=None):
    # Safe dict access: returns default for missing keys and for None values.
    if d is None:
        return default
    v = d.get(key)
    if v is None:
        return default
    return v


def get_str(d, key, default=None):
    v = get(d, key)
    if v is None:
        return default
    return str(v)


def get_list(d, key):
    v = get(d, key)
    if v is None:
        return []
    return v

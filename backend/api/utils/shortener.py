import base64


def encode_id(recipe_id: int) -> str:
    return base64.urlsafe_b64encode(
        str(recipe_id).encode()
    ).decode().rstrip("=")


def decode_code(code: str) -> int:
    try:
        padded = code + "=" * (-len(code) % 4)
        return int(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        return None

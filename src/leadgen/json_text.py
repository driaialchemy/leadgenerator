"""Pull one JSON value out of a model reply and drop unknown keys."""

import json

from pydantic import BaseModel


def parse_model_json(text: str, model: type[BaseModel]):
    """Read a model object. Extra keys are ignored. Known values are still checked."""
    payload = json.loads(extract_json(text))
    if isinstance(payload, dict):
        allowed = set(model.model_fields)
        payload = {key: value for key, value in payload.items() if key in allowed}
    return model.model_validate(payload)


def extract_json(text: str) -> str:
    """The first JSON object or array, with or without a fence and surrounding prose."""
    raw = text or ""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        if start < 0:
            continue
        end = _match(raw, start, opener, closer)
        if end is not None:
            return raw[start : end + 1]
    raise ValueError("The model reply has no JSON.")


def _match(text: str, start: int, opener: str, closer: str) -> int | None:
    depth = 0
    quote = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quote = False
            continue
        if char == '"':
            quote = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    return None

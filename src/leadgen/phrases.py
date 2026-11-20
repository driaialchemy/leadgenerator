"""Banned-phrase matching shared by profile checks and the verifier."""

import re


def is_banned(text: str, phrase: str) -> bool:
    """True when phrase appears in text.

    Phrases made of letters and spaces match whole words, so "free" does not
    match "freedom". A phrase with any other character, such as "$" or "%",
    matches as a substring.
    """
    if not phrase:
        return False
    folded_phrase = phrase.casefold()
    folded_text = text.casefold()
    if any(not (character.isalpha() or character.isspace()) for character in phrase):
        return folded_phrase in folded_text
    pattern = r"\b" + re.escape(folded_phrase) + r"\b"
    return re.search(pattern, folded_text) is not None

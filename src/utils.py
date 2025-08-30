from typing import Dict, Any, List


def get_synonyms(word: str, config: Dict[str, Any]) -> List[str]:
    """Return configured synonyms for the given word.

    Parameters
    ----------
    word: str
        Canonical word to look up.
    config: Dict[str, Any]
        Global configuration loaded from YAML; must contain optional
        ``synonyms`` mapping where each key has a list of alternative
        strings.
    """
    return (config.get("synonyms", {}) or {}).get(word, [])


def word_in_text(text: str, word: str, config: Dict[str, Any]) -> bool:
    """Check if ``text`` contains ``word`` or any of its synonyms.

    The lookup is case-insensitive and relies on the synonyms mapping
    present in ``config`` (see :func:`get_synonyms`)."""
    t = text.lower()
    options = [word] + get_synonyms(word, config)
    return any(opt.lower() in t for opt in options)

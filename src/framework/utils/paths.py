from __future__ import annotations


def safe_path_component(value: str) -> str:
    """Normalize an identifier for use as one portable path component."""

    return "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value
    )

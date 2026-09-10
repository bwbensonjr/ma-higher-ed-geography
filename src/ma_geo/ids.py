"""Stable identifiers and display names.

Identity never rides on a display string. `campus_id` and `institution_id`
are slugs of the source name fields, and the display names are formatted
separately, so a later change to how a name is presented cannot split one
institution into two.
"""

import re

# Words that stay lowercase inside a name unless they lead it. Only
# Manchester-by-the-Sea needs this today, but title-casing it wrongly would
# put a visibly incorrect label on the map.
_MINOR_WORDS = {"by", "the", "of", "on", "upon", "and", "at", "in"}


def slugify(value) -> str:
    """Lowercase, hyphen-separated, ASCII-alphanumeric slug.

    Missing source values arrive as an empty string, None, or a float NaN
    depending on the reader, so all three are treated as absent.
    """
    if value is None or not isinstance(value, str):
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-")


def institution_id(college: str) -> str:
    """Identity of an institution, shared by all of its campuses."""
    slug = slugify(college)
    if not slug:
        raise ValueError("institution name is empty; cannot derive an identifier")
    return slug


def campus_id(college: str, campus: str | None) -> str:
    """Identity of one campus record.

    For the 114 records with no campus name this equals the institution_id.
    That is collision-free -- such an institution has exactly one campus --
    but the two fields are not distinguishable by value, so consumers must
    read the field they mean.
    """
    institution = institution_id(college)
    campus_slug = slugify(campus)
    return f"{institution}--{campus_slug}" if campus_slug else institution


def display_name(raw) -> str:
    """Title-case an upper-case source name, keeping minor words lowercase."""
    if raw is None or not isinstance(raw, str) or not raw.strip():
        return ""
    parts = []
    for index, word in enumerate(re.split(r"(\s+|-)", raw.strip())):
        if not word or word.isspace() or word == "-":
            parts.append(word)
            continue
        lowered = word.lower()
        is_first = index == 0
        if lowered in _MINOR_WORDS and not is_first:
            parts.append(lowered)
        else:
            parts.append(lowered.capitalize())
    return "".join(parts)


MUNICIPALITY_TYPES = {
    "C": "city",
    "T": "town",
    "TC": "town with city form of government",
}


def municipality_type(code: str | None) -> str:
    """Expand the MassGIS C/T/TC code into words."""
    return MUNICIPALITY_TYPES.get((code or "").strip().upper(), "unknown")


def county_id(fips_stco: int | str) -> str:
    """5-digit state-county FIPS as a string: Suffolk is 25025."""
    return f"{int(fips_stco):05d}"


def municipality_id(town_id: int | str) -> str:
    """MassGIS TOWN_ID, 1-351, as a plain string."""
    return str(int(town_id))

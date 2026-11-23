"""Match a typed industry to an official NAICS code, and apply Census size bands.

Titles and everyday words live in config. This module does not name an industry.
"""

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from leadgen.paths import repo_root
from leadgen.schemas import Profile
from leadgen.sources.records import SearchFilter

CUTOFF = 0.62
LIVE_SIZE_NOTE = (
    "Public records don't list headcount, so the Market size card is the size view."
)
PHOENIX_SKIPPED = (
    "Phoenix permits were skipped. No permit type is mapped for the chosen industry."
)


@dataclass(frozen=True)
class Band:
    id: str
    label: str
    low: int
    high: int
    census: tuple[str, ...]


BANDS = (
    Band("1-49", "1–49", 1, 49, ("212", "220", "230", "241")),
    Band("50-99", "50–99", 50, 99, ("242",)),
    Band("100-250", "100–250", 100, 250, ("251",)),
)
BAND_IDS = tuple(band.id for band in BANDS)
_CENSUS_TO_BAND = {code: band.id for band in BANDS for code in band.census}


@dataclass(frozen=True)
class Match:
    code: str
    title: str
    confident: bool


def live_size_note(mode: str) -> str:
    if mode == "live":
        return LIVE_SIZE_NOTE
    return ""


def catalog_codes() -> set[str]:
    return {code for code, _title in load_catalog()}


def title_for(code: str) -> str:
    for item, title in load_catalog():
        if item == code:
            return title
    return ""


def sic_options_for(naics_codes: list[str]) -> list[tuple[str, str]]:
    """Return legacy SEC SIC classifications explicitly crosswalked from NAICS."""
    path = repo_root() / "config" / "naics_sic.yaml"
    if not path.is_file():
        return []
    mapping = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: list[tuple[str, str]] = []
    for code in naics_codes:
        entries = mapping.get(str(code), mapping.get(int(code), []) if str(code).isdigit() else [])
        for item in entries:
            pair = (str(item.get("code", "")), str(item.get("title", "")))
            if pair[0] and pair[1] and pair not in found:
                found.append(pair)
    return found


def labels_for(band_ids: list[str]) -> list[str]:
    chosen = set(band_ids)
    return [band.label for band in BANDS if band.id in chosen]


def ids_for_labels(labels: list[str]) -> list[str]:
    by_label = {band.label: band.id for band in BANDS}
    found = []
    for label in labels:
        band_id = by_label.get(label)
        if band_id and band_id not in found:
            found.append(band_id)
    return found


def codes_for_request(text: str) -> list[str]:
    """Confident official codes for a typed request. An unsure match returns nothing."""
    return [match.code for match in suggest(text) if match.confident]


def terms_for(codes: list[str]) -> list[str]:
    """Words that identify those industries. Used to keep a permit for the business asked for."""
    wanted = {str(code).strip() for code in codes if str(code).strip()}
    if not wanted:
        return []
    terms: list[str] = []
    path = repo_root() / "config" / "naics_synonyms.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for phrase, code in loaded.items():
        flat = _flat(str(phrase))
        if str(code).strip() in wanted and flat and flat not in terms:
            terms.append(flat)
    for code, title in load_catalog():
        if code not in wanted:
            continue
        for word in _words(title):
            if len(word) < 5 or word in _GENERIC or word in terms:
                continue
            terms.append(word)
    return terms


_GENERIC = frozenset(
    "service services limited except casino other including nonalcoholic commercial office offices".split()
)


def suggest(text: str, limit: int = 5) -> list[Match]:
    """Return exact, fuzzy, or broader NAICS matches for a typed industry or code."""
    code_query = str(text or "").strip()
    if code_query.isdigit() and 2 <= len(code_query) <= 6:
        rows = load_catalog()
        exact = [(code, title) for code, title in rows if code == code_query]
        if exact:
            return [Match(exact[0][0], exact[0][1], True)]
        prefix = [(code, title) for code, title in rows if code.startswith(code_query)]
        if prefix:
            return [Match(code, title, True) for code, title in prefix[:limit]]
        near = sorted(
            rows,
            key=lambda item: (-SequenceMatcher(None, code_query, item[0]).ratio(), item[0]),
        )
        close = [item for item in near if SequenceMatcher(None, code_query, item[0]).ratio() >= CUTOFF]
        if close:
            return [Match(code, title, True) for code, title in close[:limit]]
    words = _words(text)
    if not words:
        return []
    query = " ".join(words)
    scored: dict[str, float] = {}
    for code, phrase in _phrases():
        score = _score(query, words, phrase)
        scored[code] = max(score, scored.get(code, 0.0))
    if not scored:
        return []
    best = max(scored.values())
    # Only show candidates with a meaningful lexical relationship. The user
    # chooses among near matches; unrelated low-scoring codes are not useful.
    if best >= 0.48:
        ranked = sorted(scored, key=lambda code: (-scored[code], code))
        return [
            Match(code, title_for(code) or code, scored[code] >= CUTOFF)
            for code in ranked
            if scored[code] >= max(0.48, best - 0.18) and title_for(code)
        ][:limit]
    sectors = [code for code in scored if _is_sector(code)]
    ranked = sorted(sectors, key=lambda code: (-scored[code], code))[:3]
    return [Match(code, title_for(code) or code, False) for code in ranked if title_for(code)]


def keep_record(record, band_ids: list[str], known_only: bool) -> bool:
    """Keep a record with no headcount unless the person asked for a known size only."""
    count = record.employee_count
    if count is None:
        return not known_only
    if not band_ids:
        return True
    return any(band.low <= count <= band.high for band in BANDS if band.id in band_ids)


def size_line(records, band_ids: list[str]) -> str:
    if not band_ids or not any(record.employee_count is not None for record in records):
        return ""
    chosen = set(band_ids)
    parts = []
    for band in BANDS:
        if band.id not in chosen:
            continue
        count = sum(
            1
            for record in records
            if record.employee_count is not None and band.low <= record.employee_count <= band.high
        )
        parts.append(f"{band.label}: {count}")
    return ", ".join(parts)


def band_for_census(empszes: str) -> str:
    return _CENSUS_TO_BAND.get(str(empszes).strip(), "")


def apply_choices(
    filt: SearchFilter,
    profile: Profile,
    chosen_naics: list[str] | None,
    chosen_sizes: list[str] | None,
    known_size_only: bool,
) -> tuple[SearchFilter, list[str]]:
    """Replace the translated codes when the person picked chips or size bands."""
    data = filt.model_dump()
    notes: list[str] = []
    if chosen_naics:
        allowed = catalog_codes()
        codes = []
        for code in chosen_naics:
            if code in allowed and code not in codes:
                codes.append(code)
        data["naics"] = codes
        notes.extend(_phoenix(data, profile, codes))
    if chosen_sizes is not None:
        data["sizes"] = [band_id for band_id in chosen_sizes if band_id in BAND_IDS]
    data["known_size_only"] = bool(known_size_only)
    return SearchFilter.model_validate(data), notes


def load_catalog() -> list[tuple[str, str]]:
    cached = getattr(load_catalog, "_rows", None)
    if cached is not None:
        return cached
    path = repo_root() / "config" / "naics_2022.csv"
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("code") or "").strip()
            title = str(row.get("title") or "").strip().removesuffix("T").strip()
            if code and title:
                rows.append((code, title))
    load_catalog._rows = rows
    return rows


def _phoenix(data: dict, profile: Profile, codes: list[str]) -> list[str]:
    search_sources = {
        spec.id for spec in profile.search.sources if spec.role == "search"
    }
    if "phoenix_permits" not in search_sources:
        return []
    allowed = set(profile.search.permit_types)
    mapped = [item for item in _permit_types(codes) if item in allowed]
    if mapped:
        data["permit_type"] = mapped[0]
        return []
    if "phoenix_permits" in data["sources"]:
        data["sources"] = [item for item in data["sources"] if item != "phoenix_permits"]
        return [PHOENIX_SKIPPED]
    return []


def _permit_types(codes: list[str]) -> list[str]:
    table = _permit_map()
    found = []
    for code in codes:
        permit = str(table.get(code) or "").strip()
        if permit and permit not in found:
            found.append(permit)
    return found


def _permit_map() -> dict:
    cached = getattr(_permit_map, "_rows", None)
    if cached is not None:
        return cached
    path = repo_root() / "config" / "permit_map.yaml"
    if not path.is_file():
        _permit_map._rows = {}
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _permit_map._rows = {str(key): value for key, value in loaded.items()}
    return _permit_map._rows


def _phrases() -> list[tuple[str, str]]:
    cached = getattr(_phrases, "_rows", None)
    if cached is not None:
        return cached
    rows = [(code, _flat(title)) for code, title in load_catalog()]
    path = repo_root() / "config" / "naics_synonyms.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for phrase, code in loaded.items():
        entry = (str(code).strip(), _flat(str(phrase)))
        if entry not in rows:
            rows.append(entry)
    _phrases._rows = rows
    return rows


def _is_sector(code: str) -> bool:
    return "-" in code or (code.isdigit() and len(code) <= 2)


def _score(query: str, query_words: list[str], phrase: str) -> float:
    phrase_words = phrase.split()
    if not phrase_words:
        return 0.0
    if query_words == phrase_words:
        return 1.0
    if all(word in query_words for word in phrase_words):
        return 0.96
    if all(word in phrase_words for word in query_words):
        return 0.9
    word_score = _word_score(query_words, phrase_words)
    if word_score >= CUTOFF:
        return word_score
    ratio = SequenceMatcher(None, query, phrase).ratio()
    ordered = SequenceMatcher(
        None, " ".join(sorted(query_words)), " ".join(sorted(phrase_words))
    ).ratio()
    return max(ratio, ordered)


def _word_score(query_words: list[str], phrase_words: list[str]) -> float:
    """Compare both query coverage and title coverage to avoid one-word false matches."""
    if not query_words or not phrase_words:
        return 0.0

    def similarity(left: str, right: str) -> float:
        if left == right:
            return 1.0
        if min(len(left), len(right)) >= 4 and (left in right or right in left):
            return 0.9
        return SequenceMatcher(None, left, right).ratio()

    query_coverage = sum(max(similarity(word, candidate) for candidate in phrase_words) for word in query_words) / len(query_words)
    title_coverage = sum(max(similarity(word, candidate) for candidate in query_words) for word in phrase_words) / len(phrase_words)
    return 2 * query_coverage * title_coverage / (query_coverage + title_coverage) if query_coverage + title_coverage else 0.0


def _words(text: str) -> list[str]:
    raw = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    words = []
    for word in raw.split():
        if word in {"a", "an", "the", "of", "and", "for", "in", "with"}:
            continue
        words.append(_singular(word))
    return words


def _singular(word: str) -> str:
    if word in {"companys", "companies"}:
        return "company"
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _flat(text: str) -> str:
    return " ".join(_words(text))

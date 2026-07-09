import difflib
import os
import unicodedata


def _load_synonym_groups():
    groups = []
    dicts_dir = os.path.join(os.path.dirname(__file__), 'smart_matcher_dicts')
    if not os.path.isdir(dicts_dir):
        return groups
    for filename in sorted(os.listdir(dicts_dir)):
        if not filename.endswith('.txt'):
            continue
        filepath = os.path.join(dicts_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                words = {w.strip() for w in line.split(',') if w.strip()}
                if words:
                    groups.append(words)
    return groups


SYNONYM_GROUPS = _load_synonym_groups()


_SYNONYM_LOOKUP = {}
_SYNONYM_CANONICAL = {}
for _group in SYNONYM_GROUPS:
    _canonical = sorted(_group, key=lambda w: (-len(w), w))[0]
    for _word in _group:
        _norm = _word.lower().strip()
        if _norm:
            _SYNONYM_LOOKUP[_norm] = _canonical
            _SYNONYM_CANONICAL[_norm] = _canonical


_PLURAL_SUFFIXES_ES = ("ses", "nes", "les", "res", "des", "ces", "ses", "es")
_PLURAL_SUFFIX_S = "s"


def _strip_accents(text):
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_word(word):
    return _strip_accents(str(word or "").strip().lower())


def stem_word(word):
    normalized = _normalize_word(word)
    if not normalized or len(normalized) < 3:
        return normalized

    if normalized.endswith("mente") and len(normalized) > 7:
        return normalized[:-5]
    if normalized.endswith("cion") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("ciones") and len(normalized) > 6:
        return normalized[:-6]
    if normalized.endswith("ando") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("iendo") and len(normalized) > 6:
        return normalized[:-5]
    if normalized.endswith("ido") and len(normalized) > 4:
        return normalized[:-3]
    if normalized.endswith("ada") and len(normalized) > 4:
        return normalized[:-3]
    if normalized.endswith("ado") and len(normalized) > 4:
        return normalized[:-3]

    if normalized.endswith("ing") and len(normalized) > 5:
        return normalized[:-3]
    if normalized.endswith("tion") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("sion") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("ous") and len(normalized) > 4:
        return normalized[:-3]
    if normalized.endswith("ive") and len(normalized) > 4:
        return normalized[:-3]
    if normalized.endswith("ful") and len(normalized) > 4:
        return normalized[:-3]
    if normalized.endswith("less") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("ness") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("able") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("ible") and len(normalized) > 5:
        return normalized[:-4]
    if normalized.endswith("ly") and len(normalized) > 4:
        return normalized[:-2]
    if normalized.endswith("ed") and len(normalized) > 4:
        return normalized[:-2]
    if normalized.endswith("er") and len(normalized) > 4:
        return normalized[:-2]
    if normalized.endswith("est") and len(normalized) > 4:
        return normalized[:-3]

    for suffix in _PLURAL_SUFFIXES_ES:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 3:
            return normalized[:-len(suffix)]

    if normalized.endswith(_PLURAL_SUFFIX_S) and not normalized.endswith("ss") and len(normalized) > 3:
        return normalized[:-1]

    return normalized


def get_synonym_canonical(word):
    normalized = _normalize_word(word)
    if not normalized:
        return None
    return _SYNONYM_LOOKUP.get(normalized)


def get_synonym_group(word):
    normalized = _normalize_word(word)
    if not normalized:
        return set()
    canonical = _SYNONYM_LOOKUP.get(normalized)
    if not canonical:
        return {normalized}
    return {w for w, c in _SYNONYM_LOOKUP.items() if c == canonical}


def word_similarity(word1, word2, fuzzy_threshold=0.72):
    w1 = _normalize_word(word1)
    w2 = _normalize_word(word2)

    if not w1 or not w2:
        return 0.0

    if w1 == w2:
        return 1.0

    syn1 = get_synonym_group(w1)
    syn2 = get_synonym_group(w2)
    if syn1 & syn2:
        return 0.95

    stem1 = stem_word(w1)
    stem2 = stem_word(w2)

    if stem1 == stem2 and len(stem1) >= 3:
        return 0.88

    if stem1 in syn2 or stem2 in syn1:
        return 0.85

    for s1 in syn1:
        for s2 in syn2:
            if stem_word(s1) == stem_word(s2) and len(stem_word(s1)) >= 3:
                return 0.82

    if (w1 in w2 or w2 in w1) and min(len(w1), len(w2)) >= 3:
        containment_ratio = min(len(w1), len(w2)) / max(len(w1), len(w2))
        return 0.75 + (containment_ratio * 0.15)

    ratio = difflib.SequenceMatcher(None, w1, w2).ratio()
    if ratio >= fuzzy_threshold:
        return ratio * 0.70

    return 0.0


def smart_match_tokens(query_tokens, candidate_tokens, match_threshold=0.55):
    if not query_tokens or not candidate_tokens:
        return 0.0, []

    matched_pairs = []
    used_candidates = set()
    total_score = 0.0

    for qt in query_tokens:
        best_score = 0.0
        best_ct = None
        for idx, ct in enumerate(candidate_tokens):
            if idx in used_candidates:
                continue
            score = word_similarity(qt, ct)
            if score > best_score:
                best_score = score
                best_ct = ct
                best_idx = idx

        if best_score >= match_threshold and best_ct is not None:
            matched_pairs.append((qt, best_ct, best_score))
            used_candidates.add(best_idx)
            total_score += best_score

    coverage = total_score / max(len(query_tokens), 1)
    return min(coverage, 1.0), matched_pairs


def get_highlight_tokens_for_header(query_tokens, header_tokens, match_threshold=0.55):
    if not query_tokens or not header_tokens:
        return []

    highlight_pairs = []
    used_query = set()

    for ht in header_tokens:
        best_score = 0.0
        best_qt = None
        for qt in query_tokens:
            if qt in used_query:
                continue
            score = word_similarity(ht, qt)
            if score > best_score:
                best_score = score
                best_qt = qt

        if best_score >= match_threshold and best_qt is not None:
            highlight_pairs.append((ht, best_qt, best_score))
            used_query.add(best_qt)

    return highlight_pairs

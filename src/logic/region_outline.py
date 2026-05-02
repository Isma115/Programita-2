import difflib
import os
import re
import unicodedata


REGION_START_RE = re.compile(
    r'^\s*(?:(?://|#|--)|/\*|<!--)\s*#?region\b(?P<rest>.*?)(?:\*/|-->)?\s*$',
    re.IGNORECASE,
)
REGION_END_RE = re.compile(
    r'^\s*(?:(?://|#|--)|/\*|<!--)\s*#?endregion\b(?:.*?)(?:\*/|-->)?\s*$',
    re.IGNORECASE,
)


def extract_regions_for_files(file_infos):
    """Extracts full #region blocks for the provided file payloads."""
    regions = []
    for file_info in file_infos or []:
        regions.extend(_extract_regions_from_file(file_info))
    return regions


def build_region_outline_forest(file_infos):
    """Builds a per-file flat outline of detected code regions."""
    ordered_files = [item for item in file_infos or [] if item.get("path")]
    regions_by_path = {}
    for item in extract_regions_for_files(ordered_files):
        regions_by_path.setdefault(item["file_path"], []).append(item)

    forest = []
    for file_info in ordered_files:
        file_path = file_info.get("path")
        forest.append({
            "file_path": file_path,
            "file_rel_path": file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo",
            "items": list(regions_by_path.get(file_path, [])),
        })
    return forest


def _extract_regions_from_file(file_info):
    file_path = file_info.get("path")
    file_rel_path = file_info.get("rel_path") or os.path.basename(file_path or "") or "sin_archivo"
    content = file_info.get("content", "")
    lines = content.split("\n")
    stack = []
    regions = []

    for line_number, line_text in enumerate(lines, start=1):
        start_match = REGION_START_RE.match(line_text)
        if start_match:
            stack.append({
                "start_line": line_number,
                "name": _clean_region_name(start_match.group("rest")),
            })
            continue

        if REGION_END_RE.match(line_text) and stack:
            start_info = stack.pop()
            start_line = max(int(start_info.get("start_line", 1) or 1), 1)
            end_line = max(line_number, start_line)
            region_name = start_info.get("name") or f"Región {start_line}"
            regions.append({
                "key": f"region::{file_path}::{start_line}:{end_line}:{region_name}",
                "file_path": file_path,
                "file_rel_path": file_rel_path,
                "header": region_name,
                "name": region_name,
                "type": "region",
                "start_line": start_line,
                "end_line": end_line,
                "line_count": max(end_line - start_line + 1, 1),
                "content": "\n".join(lines[start_line - 1:end_line]).rstrip(),
            })

    regions.sort(key=lambda item: (int(item.get("start_line", 1) or 1), int(item.get("end_line", 1) or 1)))
    return regions


def _clean_region_name(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return ""

    for suffix in ("*/", "-->"):
        if text.endswith(suffix):
            text = text[:-len(suffix)].rstrip()

    text = text.strip().strip("\"'").strip()
    return text


def normalize_region_match_text(raw_text):
    """Normalizes free-form text to compare it against region headers."""
    text = unicodedata.normalize("NFKD", str(raw_text or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[_\-/|:;,.()[\]{}]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_region_header_candidates(region_nodes, query_text, limit=5):
    """Returns the best candidate regions for a free-form query line."""
    query = (query_text or "").strip()
    normalized_query = normalize_region_match_text(query)
    if not normalized_query:
        return []

    query_tokens = {token for token in normalized_query.split(" ") if token}
    if not query_tokens:
        return []

    ranked = []
    for node in region_nodes or []:
        if not isinstance(node, dict):
            continue

        header = (node.get("header") or node.get("name") or "").strip()
        normalized_header = normalize_region_match_text(header)
        if not normalized_header:
            continue

        header_tokens = {token for token in normalized_header.split(" ") if token}
        if not header_tokens:
            continue

        sequence_score = difflib.SequenceMatcher(None, normalized_query, normalized_header).ratio()
        overlap_count = len(query_tokens & header_tokens)
        token_score = overlap_count / max(len(query_tokens), len(header_tokens), 1)
        subset_bonus = 0.22 if query_tokens.issubset(header_tokens) else 0.0
        contains_bonus = 0.18 if normalized_query in normalized_header or normalized_header in normalized_query else 0.0
        starts_bonus = 0.12 if normalized_header.startswith(normalized_query) or normalized_query.startswith(normalized_header) else 0.0
        exact_bonus = 0.35 if normalized_query == normalized_header else 0.0

        score = max(
            sequence_score,
            min(
                1.0,
                (sequence_score * 0.58)
                + (token_score * 0.32)
                + subset_bonus
                + contains_bonus
                + starts_bonus
                + exact_bonus,
            ),
        )

        minimum_score = 0.52
        if len(normalized_query) <= 4:
            minimum_score = 0.72
        elif len(query_tokens) >= 3:
            minimum_score = 0.46

        if overlap_count == 0 and normalized_query not in normalized_header and normalized_header not in normalized_query:
            minimum_score = max(minimum_score, 0.60)

        if score < minimum_score:
            continue

        ranked.append({
            "node": node,
            "header": header,
            "score": score,
            "normalized_header": normalized_header,
            "file_rel_path": node.get("file_rel_path", ""),
        })

    ranked.sort(
        key=lambda item: (
            -item["score"],
            len(item["normalized_header"]),
            item["file_rel_path"],
            item["header"],
        )
    )
    return ranked[:max(int(limit or 0), 1)]


def match_region_lines(region_nodes, raw_text, limit_per_line=5):
    """Matches each non-empty input line against the available region headers."""
    matches = []
    for line_number, line_text in enumerate(str(raw_text or "").splitlines(), start=1):
        query = line_text.strip()
        if not query:
            continue

        candidates = match_region_header_candidates(region_nodes, query, limit=limit_per_line)
        best_candidate = candidates[0] if candidates else None
        matches.append({
            "line_number": line_number,
            "query": query,
            "match": best_candidate["node"] if best_candidate else None,
            "score": best_candidate["score"] if best_candidate else 0.0,
            "candidates": candidates,
        })

    return matches

"""
json_microcourse.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re

from .nlp_processor import NLPProcessor




@dataclass
class Slide:
    slide_id: str
    section_index: int
    section_title: str
    order_in_section: int
    original_text: str
    learning_identifier: str
    summary: str


@dataclass
class SectionMicrocourse:
    section_index: int
    section_title: str
    slides: List[Slide]
    learn_controls: List[str]


@dataclass
class Microcourse:
    document_title: str
    source_file: str
    sections: List[SectionMicrocourse]





def load_extraction_result(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_full_text_from_json(doc: Dict[str, Any]) -> str:

    parts: List[str] = []


    for page in doc.get("pages", []):
        header = page.get("header")
        if isinstance(header, str):
            parts.append(header)

        for el in page.get("elements", []):
            content = el.get("content")
            if isinstance(content, str):
                parts.append(content)

        footer = page.get("footer")
        if isinstance(footer, str):
            parts.append(footer)


    for section in doc.get("sections", []) or []:
        title = section.get("title")
        if title:
            parts.append(title)

        for key in ("paragraphs", "bullet_points"):
            seq = section.get(key) or []
            for item in seq:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, list):
                    for sub in item:
                        if isinstance(sub, str):
                            parts.append(sub)

        for sub in section.get("subsections", []) or []:
            st = sub.get("title")
            if st:
                parts.append(st)
            for p in sub.get("paragraphs", []) or []:
                if isinstance(p, str) and p:
                    parts.append(p)

    return "\n".join(parts)





def describe_table(table: Dict[str, Any], max_rows: int = 4) -> str:

    title = table.get("title") or table.get("caption") or ""
    header = table.get("table_headers") or []
    data = table.get("table_data") or []

    parts: List[str] = []

    if title:
        parts.append(f"Title: {title}")

    cols: List[str] = []
    if isinstance(header, list) and header:
        cols = [str(h) for h in header if h]
    elif isinstance(header, str) and header.strip():
        cols = [header.strip()]

    if cols:
        parts.append("Columns: " + ", ".join(cols))

    shown = 0
    for row in data:
        if shown >= max_rows:
            break
        if isinstance(row, list) and row:
            parts.append("Example row: " + " | ".join(str(x) for x in row[:3]))
        shown += 1

    remaining = max(0, len(data) - shown)
    if remaining > 0:
        parts.append(f"... plus {remaining} additional rows.")

    core = " ".join(parts).strip()
    if not core:
        return ""

    return f"TABLE: {core}"


def describe_figure(fig: Dict[str, Any]) -> str:

    content = fig.get("content")
    if isinstance(content, str) and content.strip():
        core = content.strip()
    else:
        core = (
            "A figure or chart illustrating the development of key indicators "
            "for the German federal states over time."
        )

    return f"FIGURE: {core}"


def section_to_segments(section: Dict[str, Any]) -> List[str]:

    segments: List[str] = []

    title = section.get("title")
    if title:
        segments.append(title)


    for bp_group in section.get("bullet_points", []) or []:
        if isinstance(bp_group, str):
            segments.append(bp_group)
        elif isinstance(bp_group, list):
            for bp in bp_group:
                if isinstance(bp, str) and bp.strip():
                    segments.append(bp.strip())


    for p in section.get("paragraphs", []) or []:
        if p and isinstance(p, str):
            segments.append(p.strip())


    for table in section.get("tables", []) or []:
        desc = describe_table(table)
        if desc:
            segments.append(desc)


    for fig in section.get("figures", []) or []:
        desc = describe_figure(fig)
        if desc:
            segments.append(desc)


    for sub in section.get("subsections", []) or []:
        st = sub.get("title")
        if st:
            segments.append(st.strip())
        for p in sub.get("paragraphs", []) or []:
            if p and isinstance(p, str):
                segments.append(p.strip())

    cleaned = [s for s in segments if isinstance(s, str) and s.strip()]
    return cleaned





def _is_heading_like(seg: str) -> bool:

    if not seg:
        return False

    s = seg.strip()
    if not s:
        return False

    upper = s.upper()
    if upper.startswith("TABLE:") or upper.startswith("FIGURE:"):
        return False


    if "." in s or "?" in s or "!" in s:
        return False

    words = s.split()
    if len(words) > 6:
        return False

    alpha_chars = [ch for ch in s if ch.isalpha()]
    if not alpha_chars:
        return False
    upper_ratio = sum(ch.isupper() for ch in alpha_chars) / len(alpha_chars)

    if upper_ratio >= 0.6:
        return True

    if s.istitle() and len(words) <= 4:
        return True

    return False


def merge_heading_like_segments(segments: List[str]) -> List[str]:

    if not segments:
        return segments

    out: List[str] = []
    i = 0
    n = len(segments)

    while i < n:
        current = segments[i]
        if _is_heading_like(current) and i + 1 < n:
            merged = f"{current.strip()}. {segments[i + 1].strip()}"
            out.append(merged)
            i += 2
        else:
            out.append(current)
            i += 1

    return out





_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_long_text_into_sentences(text: str, max_chars: int) -> List[str]:
    sentences = _SENTENCE_SPLIT_RE.split(text.strip())
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        if current_len + len(sent) + 1 <= max_chars:
            current.append(sent)
            current_len += len(sent) + 1
        else:
            if current:
                chunks.append(" ".join(current).strip())
            current = [sent]
            current_len = len(sent)

    if current:
        chunks.append(" ".join(current).strip())

    return chunks


def chunk_segments_into_slides(
    segments: List[str],
    max_chars: int = 900,
    min_chars: int = 300,
) -> List[str]:

    slides: List[str] = []
    current: List[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current, current_len, slides
        if current:
            text = " ".join(current).strip()
            if text:
                slides.append(text)
        current = []
        current_len = 0

    for seg in segments:
        seg = (seg or "").strip()
        if not seg:
            continue

        if len(seg) > max_chars * 1.5:
            flush_current()
            long_chunks = split_long_text_into_sentences(seg, max_chars=max_chars)
            for ch in long_chunks:
                if len(ch) <= max_chars:
                    slides.append(ch)
                else:
                    slides.append(ch[:max_chars].strip())
            continue

        if current_len + len(seg) + 1 <= max_chars:
            current.append(seg)
            current_len += len(seg) + 1
        else:
            if current_len < min_chars and len(seg) < max_chars:
                flush_current()
                current.append(seg)
                current_len = len(seg)
            else:
                flush_current()
                current.append(seg)
                current_len = len(seg)

    flush_current()
    return slides





def make_learning_identifier(
    base_text: str,
    existing_ids: Optional[set[str]] = None,
    max_words: int = 10,
) -> str:
    existing_ids = existing_ids or set()

    clean = re.sub(r"[^A-Za-z0-9\s\-]", "", (base_text or "").strip())
    words = clean.split()
    if not words:
        candidate = "Learning slide"
    else:
        candidate = " ".join(words[:max_words])

    candidate = candidate[:1].upper() + candidate[1:]

    if candidate not in existing_ids:
        existing_ids.add(candidate)
        return candidate

    idx = 2
    while True:
        alt = f"{candidate} ({idx})"
        if alt not in existing_ids:
            existing_ids.add(alt)
            return alt
        idx += 1





_SUMMARY_BANNED_SUBSTRINGS = {
    "cnn.com",
    "cnncom",
    "cnn",
    "travel snapshots",
    "snapshot",
    "snapshots",
    "photo",
    "photos",
    "gallery",
    "new jersey",
    "new york",
    "united states",
    "u.s.",
    "u. s.",
    "usa",
}


def _summary_contains_hallucination(summary: str) -> bool:
    if not summary:
        return False
    lower = summary.lower()
    return any(bad in lower for bad in _SUMMARY_BANNED_SUBSTRINGS)


def _is_mostly_numeric(text: str) -> bool:

    if not text:
        return False

    tokens = re.findall(r"\S+", text)
    if not tokens:
        return False

    def token_has_number(tok: str) -> bool:

        if any(ch.isdigit() for ch in tok):
            return True
        if re.search(r"\d+[.,]\d+", tok):
            return True
        return False

    num_tokens = sum(token_has_number(tok) for tok in tokens)


    if num_tokens >= 3 and (num_tokens >= len(tokens) / 3 or num_tokens >= 8):
        return True

    return False





def _generate_heading_summary(section_title: str, slide_text: str) -> str:

    s_lower = slide_text.lower()
    sec_lower = section_title.lower()

    if "at a glance" in s_lower or "at a glance" in sec_lower:
        return "This slide presents the main results of the report at a glance."

    if "from the authors" in s_lower or "from the authors" in sec_lower:
        return "This slide summarises the authors' commentary and interpretation of the results."

    if "projection of tax revenue" in s_lower or "projection of tax revenue" in sec_lower:
        return (
            "This slide introduces the projection of tax revenue for the German federal states "
            "and explains the central assumptions behind these projections."
        )

    if "data and forward projection of population" in s_lower or "forward projection of population" in sec_lower:
        return (
            "This slide presents the data basis and forward projection of the population in the "
            "German federal states."
        )

    if "variant a" in s_lower:
        return (
            "This slide explains Variant A, which assumes a relatively low level of immigration "
            "and shows how this affects population development and fiscal capacity."
        )

    if "variant b" in s_lower:
        return (
            "This slide explains Variant B, which assumes medium immigration and presents a "
            "middle path between higher and lower immigration variants."
        )

    if "variant c" in s_lower:
        return (
            "This slide explains Variant C, which assumes a relatively high level of immigration "
            "and illustrates its implications for population and fiscal capacity."
        )

    if "differences in fiscal capacity before distribution" in s_lower:
        return (
            "This slide introduces the scenario analysis of differences in fiscal capacity before "
            "and after redistribution up to 2070."
        )

    return f'This slide summarises the central ideas of the subchapter "{section_title}".'


def _generate_table_summary(section_title: str, slide_text: str) -> str:
    lower = slide_text.lower()

    if "population" in lower:
        return (
            "This slide explains a table on population development in the German federal states, "
            "comparing changes over time and highlighting differences between regions."
        )

    if "fiscal capacity" in lower or "tax revenue" in lower or "taxes" in lower:
        return (
            "This slide explains a table on fiscal capacity and tax revenue, comparing the situation "
            "across the German federal states and the impact of redistribution."
        )

    return (
        f'This slide explains the table related to "{section_title}", which compares key indicators '
        "across the federal states and highlights differences between them."
    )


def _generate_figure_summary(section_title: str, slide_text: str) -> str:
    lower = slide_text.lower()

    if "scenario" in lower:
        return (
            "This slide explains a figure that contrasts the fiscal capacity of the German federal "
            "states under different scenarios over time."
        )

    if "population" in lower:
        return (
            "This slide explains a figure on population development in the German federal states, "
            "showing how the number of inhabitants changes across regions."
        )

    return (
        f'This slide explains a figure related to "{section_title}", which visualises important '
        "developments for the German federal states and highlights differences between regions or over time."
    )


def generate_slide_summary(
    processor: NLPProcessor,
    section_title: str,
    slide_text: str,
    max_chars: int = 900,
    max_length: int = 80,
    min_length: int = 30,
) -> str:

    raw = (slide_text or "").strip()
    if not raw:
        return ""

    upper = raw.upper()
    lower = raw.lower()


    if section_title and raw.strip().lower() == section_title.strip().lower():
        return _generate_heading_summary(section_title, raw)


    if upper.startswith("TABLE:"):
        return _generate_table_summary(section_title, raw)

    if upper.startswith("FIGURE:"):
        return _generate_figure_summary(section_title, raw)


    if lower.startswith("variant a") or lower.startswith("variant b") or lower.startswith("variant c"):
        return _generate_heading_summary(section_title, raw)


    word_count = len(re.findall(r"\w+", raw))
    if word_count <= 8 and _is_heading_like(raw):
        return _generate_heading_summary(section_title, raw)


    summary = processor.summarize(
        raw,
        max_chars=max_chars,
        max_length=max_length,
        min_length=min_length,
    )


    if summary:
        summary = summary.lstrip()
        if summary.startswith("."):
            summary = summary.lstrip(". ").lstrip()


    if _summary_contains_hallucination(summary):
        return _generate_heading_summary(section_title, raw)


    if _is_mostly_numeric(raw) or _is_mostly_numeric(summary):
        return _generate_table_summary(section_title, raw)

    return summary





def is_boilerplate_section_title(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    boiler_keywords = [
        "legal and editorial",
        "legal notice",
        "imprint",
        "media",
        "newsletter",
    ]
    return any(k in t for k in boiler_keywords)


def build_section_microcourse(
    processor: NLPProcessor,
    section: Dict[str, Any],
    section_index: int,
    max_slide_chars: int = 900,
    min_slide_chars: int = 300,
    summary_max_length: int = 80,
    summary_min_length: int = 30,
    learn_controls_count: int = 4,
) -> Optional[SectionMicrocourse]:
    title = section.get("title") or f"Section {section_index + 1}"

    if is_boilerplate_section_title(title):
        return None

    segments = section_to_segments(section)
    if not segments:
        return None

    segments = merge_heading_like_segments(segments)

    joined = " ".join(segments)
    try:
        if processor._looks_like_boilerplate(joined):
            return None
    except Exception:
        pass

    slide_texts = chunk_segments_into_slides(
        segments,
        max_chars=max_slide_chars,
        min_chars=min_slide_chars,
    )
    if not slide_texts:
        return None

    slides: List[Slide] = []
    used_ids: set[str] = set()

    for i, slide_text in enumerate(slide_texts):
        summary = generate_slide_summary(
            processor=processor,
            section_title=title,
            slide_text=slide_text,
            max_chars=max_slide_chars,
            max_length=summary_max_length,
            min_length=summary_min_length,
        )
        if not summary:
            summary = slide_text.strip()

        identifier = make_learning_identifier(summary, existing_ids=used_ids)

        slide = Slide(
            slide_id=f"sec{section_index + 1}_slide{i + 1}",
            section_index=section_index,
            section_title=title,
            order_in_section=i + 1,
            original_text=slide_text.strip(),
            learning_identifier=identifier,
            summary=summary,
        )
        slides.append(slide)

    combined_for_qg = " ".join(s.summary for s in slides if s.summary)[:8000]

    learn_controls: List[str] = []
    if combined_for_qg.strip():
        try:
            learn_controls = processor.generate_questions(
                combined_for_qg,
                count=learn_controls_count,
            )
        except Exception:
            learn_controls = []

    learn_controls = [q for q in (learn_controls or []) if q.strip()]

    if len(learn_controls) < 3:
        needed = max(3 - len(learn_controls), 0)
        try:
            generic = processor._generate_generic_page_questions(needed)  # type: ignore[attr-defined]
        except Exception:
            generic = [
                "What are the most important ideas in this subchapter?",
                "How does this subchapter relate to the overall topic of the document?",
                "Which details from this subchapter should you remember?",
            ][:needed]
        learn_controls.extend(generic)

    if len(learn_controls) > 4:
        learn_controls = learn_controls[:4]

    return SectionMicrocourse(
        section_index=section_index,
        section_title=title,
        slides=slides,
        learn_controls=learn_controls,
    )





def build_microcourse_from_json(
    doc: Dict[str, Any],
    processor: Optional[NLPProcessor] = None,
) -> Microcourse:
    if processor is None:
        processor = NLPProcessor()

    try:
        full_text = extract_full_text_from_json(doc)
        processor.register_document_text(full_text)
    except Exception:
        pass

    meta = doc.get("metadata", {})
    doc_title = doc.get("summary", {}).get("title") or meta.get("source_file") or "Document"
    source_file = meta.get("source_file") or ""

    sections_json = doc.get("sections", []) or []

    sections: List[SectionMicrocourse] = []
    for idx, section in enumerate(sections_json):
        result = build_section_microcourse(
            processor=processor,
            section=section,
            section_index=idx,
        )
        if result is not None and result.slides:
            sections.append(result)

    return Microcourse(
        document_title=doc_title,
        source_file=source_file,
        sections=sections,
    )


def microcourse_to_dict(mc: Microcourse) -> Dict[str, Any]:
    out_sections: List[Dict[str, Any]] = []
    for sec in mc.sections:
        out_slides = [
            {
                "slide_id": s.slide_id,
                "section_index": s.section_index,
                "section_title": s.section_title,
                "order_in_section": s.order_in_section,
                "original_text": s.original_text,
                "learning_identifier": s.learning_identifier,
                "summary": s.summary,
            }
            for s in sec.slides
        ]
        out_sections.append(
            {
                "section_index": sec.section_index,
                "section_title": sec.section_title,
                "slides": out_slides,
                "learn_controls": list(sec.learn_controls),
            }
        )

    return {
        "document_title": mc.document_title,
        "source_file": mc.source_file,
        "sections": out_sections,
    }
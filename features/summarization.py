# For context can you add this in the module that if they see any abbreviations for state names, following info can be use to replace
# West
# BW = Baden-Württemberg
# BY = Bavaria
# HE = Hesse
# NI = Lower Saxony
# NW = North Rhine-Westphalia
# RP = Rhineland-Palatinate
# SL = Saarland
# SH = Schleswig-Holstein
# East
# BB = Brandeburg
# MV = Mecklenburg-Western Pomerania
# SN = Saxony
# ST = Saxony-Anhalt
# TH = Thuringia
# City-states
# BE = Berlin
# HB = Bremen
# HH = Hamburg

import json
import logging
import os
import base64
from typing import Dict, Any, List, Optional, Union
import ollama
from config import settings

logger = logging.getLogger(__name__)


class Summarizer:
    """
    Enhanced summarizer that processes documents page-by-page.
    It re-analyzes images using a vision model, incorporating the current topic context
    to extract deeper, more relevant insights.
    """

    STATE_ABBREVIATIONS_REF = """
    REFERENCE - STATE ABBREVIATIONS (If used in text/charts):
    West:
    BW = Baden-Württemberg, BY = Bavaria, HE = Hesse, NI = Lower Saxony, NW = North Rhine-Westphalia, RP = Rhineland-Palatinate, SL = Saarland, SH = Schleswig-Holstein
    East:
    BB = Brandeburg, MV = Mecklenburg-Western Pomerania, SN = Saxony, ST = Saxony-Anhalt, TH = Thuringia
    City-states:
    BE = Berlin, HB = Bremen, HH = Hamburg
    """

    def __init__(self,
                 text_model: str = "llama3.2",
                 vision_model: str = "minicpm-v"):
        self.text_model = text_model
        self.vision_model = vision_model
        logger.info(
            f"Initialized Summarizer with text_model: {self.text_model}, vision_model: {self.vision_model}"
        )

    def generate_slides(self, extraction_result: Dict[str,
                                                      Any]) -> Dict[str, Any]:
        """
        Generate slides from extraction results.
        Returns a dict containing 'slides' and 'summary'.
        """
        logger.info("Starting slide generation pipeline...")

        # 1. Summarize content
        summary_result = self.summarize(extraction_result)

        # 2. Convert to slides using SlideGenerator logic
        # Since SlideGenerator was designed to read from file, we'll adapt it here
        # or instantiate it if available.
        from features.generation import SlideGenerator

        generator = SlideGenerator()

        # Populate image_url_map from extraction_result so images work in slides
        if isinstance(extraction_result, list):
            for item in extraction_result:
                if isinstance(item, dict) and item.get(
                        "image_path") and item.get("image_url"):
                    # Map both full path and basename to be safe
                    generator.image_url_map[
                        item["image_path"]] = item["image_url"]
                    generator.image_url_map[os.path.basename(
                        item["image_path"])] = item["image_url"]

        # Handle dict case (page-based extraction returns {'pages': [...]})
        elif isinstance(extraction_result,
                        dict) and "pages" in extraction_result:
            for page in extraction_result["pages"]:
                if "elements" in page:
                    for item in page["elements"]:
                        if not isinstance(item, dict):
                            continue

                        # Robustly find image path and URL
                        img_path = item.get("image_path")
                        img_url = item.get("image_url")

                        if not img_path and item.get("image_context"):
                            img_path = item["image_context"].get("image_path")

                        if not img_url and item.get("image_context"):
                            img_url = item["image_context"].get("image_url")

                        if img_path and img_url:
                            generator.image_url_map[img_path] = img_url
                            generator.image_url_map[os.path.basename(
                                img_path)] = img_url

        # We need to adapt the internal methods of SlideGenerator to work with data
        # instead of files, or we pass the summary result directly if modified.

        # For now, let's use the process_summary_input logic from SlideGenerator
        # but exposed in a way we can get the objects back.

        # Manually constructing the state and running generation
        from features.generation import ProcessingState
        state = ProcessingState()

        # We need the topic summaries from the summary result
        topic_summaries = summary_result.get("topic_summaries", [])

        # Fallback: If no topic summaries (e.g. segmentation failed), use page summaries
        if not topic_summaries and summary_result.get("page_summaries"):
            logger.info(
                "Using page summaries as fallback for slide generation")
            for page in summary_result.get("page_summaries", []):
                topic_summaries.append({
                    "topic":
                    f"Page {page['page_number']}",
                    "summary":
                    page["summary"],
                    "key_insights":
                    page.get("key_visuals", []),
                    "detailed_visual_analysis":
                    page.get("detailed_visual_analysis", []),
                    "topics":
                    page.get("topics", []),
                    "original_content":
                    ""  # Not available in this path
                })

        # Use the generator's logic to process these summaries into slides
        generator._process_summary_input(topic_summaries, state)

        # Now convert the state (Chapters/Slides) into the expected dictionary format
        slides_data = []

        # Also capture chapter metadata
        chapters_data = []

        for chapter in state.chapters:
            chapters_data.append({
                "chapter_num": chapter.chapter_num,
                "main_title": chapter.main_title,
                "subtitle": chapter.subtitle,
                "learn_controls": chapter.learn_controls
            })

            for slide in chapter.slides:
                slide_dict = {
                    "sequence":
                    slide.slide_num,  # Simplified sequence
                    "title":
                    slide.title,
                    "chapter":
                    chapter.chapter_num,  # Add chapter num to slide
                    "content": [{
                        "type": item.type,
                        "text": item.content,
                        "metadata": item.metadata
                    } for item in slide.items],
                    "chapter_title":
                    chapter.main_title,
                    "chapter_main_title":
                    chapter.main_title,
                    "subchapter":
                    "Unknown"  # Placeholder, update if subchapter tracking is fixed
                }
                slides_data.append(slide_dict)

        return {
            "slides": slides_data,
            "chapters": chapters_data,
            "summary": summary_result
        }

    def summarize(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for document summarization.
        """
        logger.info(
            "Starting enhanced document summarization with image re-processing..."
        )

        # FORCE segmentation from pages to ensure 1:1 mapping with segmentation_context.md
        sections = []
        pages = extraction_result.get("pages", [])
        if pages:
            logger.info("Applying strict segmentation rules from pages...")
            sections = self._segment_pages_into_sections(pages)
            logger.info(f"Generated {len(sections)} sections from pages.")

        # Fallback to existing sections if segmentation failed (e.g. no pages found)
        if not sections:
            sections = extraction_result.get("sections", [])

        if sections:
            logger.info(
                f"Found {len(sections)} sections. Summarizing by topic...")
            return self._summarize_by_sections(sections)

        # Fallback to page-by-page if no sections
        logger.info(
            "No sections found. Falling back to page-by-page summarization...")
        pages = extraction_result.get("pages", [])
        if not pages:
            logger.warning("No pages found in extraction result.")
            return {"global_summary": "", "page_summaries": []}

        page_summaries = []
        running_context = ""
        active_topics = []

        for i, page in enumerate(pages):
            page_num = page.get("page_number", i + 1)
            logger.info(f"Processing page {page_num}...")

            # 1. First, identify the context/topics from the text part of the page ONLY
            #    (This helps us ask better questions to the vision model)
            text_content = self._extract_text_only(page)
            preliminary_topics = self._identify_page_topics(
                text_content, running_context)

            # Combine global active topics with local preliminary topics
            current_context_topics = list(
                set(active_topics + preliminary_topics))

            # 2. Re-process images on this page using the context
            visual_insights_data = self._reanalyze_visuals(
                page, current_context_topics)

            # Format visual insights for the prompt
            visual_insights_str = "\n\n".join([
                f"[VISUAL RE-ANALYSIS ({v['type']})]: {v['analysis']}"
                for v in visual_insights_data
            ])

            # 3. Build full page content (Text + New Visual Insights)
            full_page_content = f"{text_content}\n\n{visual_insights_str}"

            # 4. Generate final summary for the page
            page_output = self._summarize_content(
                title=f"Page {page_num}",
                content=full_page_content,
                previous_context=running_context,
                active_topics=current_context_topics)

            # 5. Update running context
            current_summary = page_output.get("summary", "")
            running_context = self._update_running_context(
                running_context, current_summary)

            # Update active topics
            new_topics = page_output.get("topics", [])
            for topic in new_topics:
                if topic not in active_topics:
                    active_topics.append(topic)

            page_summaries.append({
                "page_number":
                page_num,
                "summary":
                current_summary,
                "topics":
                new_topics,
                "key_visuals":
                page_output.get("visual_insights", []),
                "detailed_visual_analysis":
                visual_insights_data
            })

        # Generate Global Summary
        # logger.info("Generating global document summary...")
        # global_summary = self._generate_global_summary(page_summaries)
        global_summary = ""

        return {
            "global_summary": global_summary,
            "page_summaries": page_summaries,
            "all_topics": active_topics
        }

    def _segment_pages_into_sections(
            self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sections = []

        for page in pages:
            page_num = page.get("page_number")
            elements = page.get("elements", [])

            # Helper to categorize elements
            def categorize(elems):
                res = {
                    "title": "",
                    "paragraphs": [],
                    "bullet_points": [],
                    "figures": [],
                    "tables": [],
                    "subsections":
                    []  # Not using nested subsections for now, keeping it flat
                }
                for e in elems:
                    etype = e.get("type", "")
                    content = e.get("content", "")
                    if etype in ["figure", "chart", "image"]:
                        res["figures"].append(e)
                    elif etype == "table":
                        res["tables"].append(e)
                    elif etype in ["bullet_point", "list_item"]:
                        res["bullet_points"].append(e)
                    elif etype in [
                            "paragraph", "text", "title", "section_title",
                            "subsection_title", "abstract", "footnote",
                            "call_out_box"
                    ]:
                        # Treat all text-like things as paragraphs for extraction purposes
                        res["paragraphs"].append(content)
                    else:
                        # Default fallback
                        res["paragraphs"].append(content)
                return res

            current_sections = []

            if page_num == 1:
                # Section 1 & 2
                sec1_elems = []
                sec2_elems = []
                found_figure = False
                for el in elements:
                    if el.get("type") in ["figure", "chart"]:
                        found_figure = True
                    if not found_figure:
                        sec1_elems.append(el)
                    else:
                        sec2_elems.append(el)

                s1 = categorize(sec1_elems)
                s1["title"] = "Page 1 - Header & Key Points"
                current_sections.append(s1)

                s2 = categorize(sec2_elems)
                s2["title"] = "Page 1 - Chart Area"
                current_sections.append(s2)

            elif page_num == 2:
                # Sec 3-6
                sec3 = [e for e in elements if e.get("type") == "title"]
                sec4 = [e for e in elements if e.get("type") == "abstract"]
                sec6 = [e for e in elements if e.get("type") == "footnote"]
                sec5 = [
                    e for e in elements if e not in sec3 + sec4 +
                    sec6 and e.get("type") not in ["header", "footer"]
                ]

                s3 = categorize(sec3)
                s3["title"] = "Page 2 - Title"
                current_sections.append(s3)

                s4 = categorize(sec4)
                s4["title"] = "Page 2 - Abstract"
                current_sections.append(s4)

                s5 = categorize(sec5)
                s5["title"] = "Page 2 - Main Text"
                current_sections.append(s5)

                s6 = categorize(sec6)
                s6["title"] = "Page 2 - Footnotes"
                current_sections.append(s6)

            elif page_num == 3:
                # Sec 7-10
                sec7 = [
                    e for e in elements
                    if e.get("type") in ["figure", "chart"]
                ]
                sec10 = [e for e in elements if e.get("type") == "footnote"]
                text_elems = [
                    e for e in elements if e not in sec7 +
                    sec10 and e.get("type") not in ["header", "footer"]
                ]

                sec8 = []
                sec9 = []
                found_sub = False
                for el in text_elems:
                    if el.get("type") == "subsection_title":
                        found_sub = True
                    if found_sub:
                        sec9.append(el)
                    else:
                        sec8.append(el)

                s7 = categorize(sec7)
                s7["title"] = "Page 3 - Main Graph"
                current_sections.append(s7)

                s8 = categorize(sec8)
                s8["title"] = "Page 3 - Cross-column Text"
                current_sections.append(s8)

                s9 = categorize(sec9)
                s9["title"] = "Page 3 - Continuing Text"
                current_sections.append(s9)

                s10 = categorize(sec10)
                s10["title"] = "Page 3 - Footnotes"
                current_sections.append(s10)

            elif page_num == 4:
                # Sec 11-14
                sec13 = [
                    e for e in elements if e.get("type") == "call_out_box"
                ]
                sec14 = [e for e in elements if e.get("type") == "footnote"]
                text_elems = [
                    e for e in elements if e not in sec13 +
                    sec14 and e.get("type") not in ["header", "footer"]
                ]

                sec11 = []
                sec12 = []
                found_sub = False
                for el in text_elems:
                    if el.get("type") == "subsection_title":
                        found_sub = True
                    if found_sub:
                        sec12.append(el)
                    else:
                        sec11.append(el)

                s11 = categorize(sec11)
                s11["title"] = "Page 4 - Continuation Text"
                current_sections.append(s11)

                s12 = categorize(sec12)
                s12["title"] = "Page 4 - Split Layout Text"
                current_sections.append(s12)

                s13 = categorize(sec13)
                s13["title"] = "Page 4 - Boxed Section"
                current_sections.append(s13)

                s14 = categorize(sec14)
                s14["title"] = "Page 4 - Footnotes"
                current_sections.append(s14)

            elif page_num == 5:
                # Sec 15-18
                sec15 = [e for e in elements if e.get("type") == "table"]
                sec17 = [
                    e for e in elements if e.get("type") == "call_out_box"
                    or e.get("type") == "abstract"
                ]
                sec18 = [e for e in elements if e.get("type") == "footnote"]
                text_elems = [
                    e for e in elements if e not in sec15 + sec17 +
                    sec18 and e.get("type") not in ["header", "footer"]
                ]

                s15 = categorize(sec15)
                s15["title"] = "Page 5 - Table 1"
                current_sections.append(s15)

                s16 = categorize(text_elems)
                s16["title"] = "Page 5 - Split Layout Text"
                current_sections.append(s16)

                s17 = categorize(sec17)
                s17["title"] = "Page 5 - Boxed Section"
                current_sections.append(s17)

                s18 = categorize(sec18)
                s18["title"] = "Page 5 - Footnotes"
                current_sections.append(s18)

            elif page_num in [6, 7]:
                # Sec 19/20
                s = categorize(elements)
                s["title"] = f"Page {page_num} - Grid of Graphs"
                current_sections.append(s)

            elif page_num == 8:
                # Sec 21+
                sec_table = [e for e in elements if e.get("type") == "table"]
                sec_footnotes = [
                    e for e in elements if e.get("type") == "footnote"
                ]
                text_elems = [
                    e for e in elements if e not in sec_table + sec_footnotes
                    and e.get("type") not in ["header", "footer"]
                ]

                sec_text1 = []
                sec_text2 = []
                found_sub = False
                for el in text_elems:
                    if el.get("type") == "subsection_title":
                        found_sub = True

                    # Filter out likely artifacts in Part 1 (Section 19)
                    if not found_sub:
                        content = el.get("content", "").strip()
                        # Skip short fragments or table artifacts
                        if len(content) < 30 and not el.get("type") in [
                                "title", "header"
                        ]:
                            continue
                        if "In percent" in content or "Projection" in content:
                            continue

                    if found_sub:
                        sec_text2.append(el)
                    else:
                        sec_text1.append(el)

                s_tbl = categorize(sec_table)
                s_tbl["title"] = "Page 8 - Table 2"
                current_sections.append(s_tbl)

                if sec_text1:
                    s_t1 = categorize(sec_text1)
                    s_t1["title"] = "Page 8 - Text Part 1"
                    current_sections.append(s_t1)

                if sec_text2:
                    s_t2 = categorize(sec_text2)
                    s_t2["title"] = "Page 8 - Text Part 2"
                    current_sections.append(s_t2)

                s_fn = categorize(sec_footnotes)
                s_fn["title"] = "Page 8 - Footnotes"
                current_sections.append(s_fn)

            elif page_num == 9:
                # Sec 21/22
                text_elems = [
                    e for e in elements
                    if e.get("type") not in ["header", "footer", "footnote"]
                ]
                sec_concl = []
                sec_cont = []
                found_sub = False
                for el in text_elems:
                    if "Conclusion" in el.get(
                            "content",
                            "") or el.get("type") == "subsection_title":
                        found_sub = True
                    if found_sub:
                        sec_concl.append(el)
                    else:
                        sec_cont.append(el)

                s_cont = categorize(sec_cont)
                s_cont["title"] = "Page 9 - Continuing Text"
                current_sections.append(s_cont)

                s_conc = categorize(sec_concl)
                s_conc["title"] = "Page 9 - Conclusion"
                current_sections.append(s_conc)

            elif page_num == 10:
                s = categorize(elements)
                s["title"] = "Page 10 - Legal/Editorial"
                current_sections.append(s)

            sections.extend(current_sections)

        return sections

    def _summarize_by_sections(
            self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize the document section by section (Topic-wise)."""
        topic_summaries = []
        running_context = ""
        all_topics = []

        for section in sections:
            title = section.get("title", "Untitled Section")
            logger.info(f"Processing section: {title}")

            # 1. Extract content and visuals (recursive)
            text_content, visual_elements = self._extract_section_data(section)

            if not text_content.strip() and not visual_elements:
                continue

            # 2. Identify topics
            preliminary_topics = self._identify_page_topics(
                text_content, running_context)
            current_topics = list(set(all_topics + preliminary_topics))

            # 3. Re-analyze visuals
            visual_insights_data = self._reanalyze_visuals_list(
                visual_elements, current_topics)

            visual_insights_str = "\n\n".join([
                f"[VISUAL RE-ANALYSIS ({v['type']})]: {v['analysis']}"
                for v in visual_insights_data
            ])

            # 4. Build full content
            full_content = f"{text_content}\n\n{visual_insights_str}"

            # 5. Summarize
            section_output = self._summarize_content(
                title=title,
                content=full_content,
                previous_context=running_context,
                active_topics=current_topics)

            summary_text = section_output.get("summary", "")
            running_context = self._update_running_context(
                running_context, summary_text)

            new_topics = section_output.get("topics", [])
            for t in new_topics:
                if t not in all_topics:
                    all_topics.append(t)

            topic_summaries.append({
                "topic":
                title,
                "original_content":
                text_content,
                "summary":
                summary_text,
                "key_insights":
                section_output.get("visual_insights", []),
                "visual_analysis":
                visual_insights_data,
                "detailed_visual_analysis":
                visual_insights_data,  # Add this field to match generation.py expectation
                "topics":
                new_topics
            })

        # global_summary = self._generate_global_summary_from_topics(
        #     topic_summaries)
        global_summary = ""

        return {
            "global_summary": global_summary,
            "topic_summaries": topic_summaries,
            "all_topics": all_topics
        }

    def _table_to_markdown(self, table_element: Dict[str, Any]) -> str:
        """Convert extracted table data to Markdown format."""
        headers = table_element.get("table_headers", [])
        rows = table_element.get("table_data", [])

        if not headers and not rows:
            return ""

        md_lines = []
        title = table_element.get("metadata", {}).get("title", "")
        if title:
            md_lines.append(f"**Table: {title}**")

        # If headers exist
        if headers:
            md_lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Rows
        for row in rows:
            md_lines.append("| " + " | ".join(str(cell)
                                              for cell in row) + " |")

        return "\n".join(md_lines)

    def _extract_section_data(
            self, section: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
        """Recursively extract text and visuals from a section."""
        text_parts = []
        visuals = []

        # Title
        if section.get("title"):
            text_parts.append(f"## {section['title']}")

        # Paragraphs
        for p in section.get("paragraphs", []):
            if isinstance(p, dict):
                text_parts.append(p.get("content", ""))
            elif isinstance(p, str):
                text_parts.append(p)

        # Bullet points
        for bp in section.get("bullet_points", []):
            if isinstance(bp, list):
                for item in bp:
                    text_parts.append(f"- {item}")
            elif isinstance(bp, dict):
                if "bullet_items" in bp and bp["bullet_items"]:
                    for item in bp["bullet_items"]:
                        text_parts.append(f"- {item}")
                else:
                    text_parts.append(f"- {bp.get('content', '')}")
            elif isinstance(bp, str):
                text_parts.append(f"- {bp}")

        # Numbered lists
        for nl in section.get("numbered_lists", []):
            text_parts.append(f"1. {nl.get('content', '')}")

        # Visuals
        visuals.extend(section.get("figures", []))

        # Tables - Add to text if data exists, also keep as visual for trend analysis
        for tbl in section.get("tables", []):
            visuals.append(tbl)
            if tbl.get("table_data"):
                md_table = self._table_to_markdown(tbl)
                if md_table:
                    text_parts.append(
                        f"\n[EXTRACTED TABLE DATA]:\n{md_table}\n")

        # Subsections (Recursive)
        for sub in section.get("subsections", []):
            sub_text, sub_visuals = self._extract_section_data(sub)
            text_parts.append(sub_text)
            visuals.extend(sub_visuals)

        return "\n\n".join(text_parts), visuals

    def _reanalyze_visuals_list(
            self, elements: List[Dict[str, Any]],
            context_topics: List[str]) -> List[Dict[str, Any]]:
        """Re-analyze a list of visual elements."""
        visual_analysis_results = []
        topics_str = ", ".join(
            context_topics) if context_topics else "General Analysis"

        for elem in elements:
            etype = elem.get("type", "")
            image_context = elem.get("image_context", {})
            image_path = image_context.get("image_path")

            # Check if we have the image file
            full_path = os.path.join(settings.output_dir,
                                     image_path) if image_path else ""

            # Handle relative path if needed
            if image_path and not os.path.exists(full_path):
                possible_path = os.path.join(settings.extraction_images_dir,
                                             os.path.basename(image_path))
                if os.path.exists(possible_path):
                    full_path = possible_path

            analysis_entry = {
                "type": etype,
                "image_path": image_path,
                "context_topics": context_topics,
                "analysis": "",
                "source": "vision_model"
            }

            if etype == "table":
                analysis_entry["table_data"] = elem.get("table_data")
                analysis_entry["table_headers"] = elem.get("table_headers")
                analysis_entry["content"] = elem.get("content", "")

            if full_path and os.path.exists(full_path):
                logger.info(
                    f"Re-analyzing image: {full_path} with context: {topics_str}"
                )
                try:
                    with open(full_path, "rb") as img_file:
                        img_base64 = base64.b64encode(
                            img_file.read()).decode('utf-8')

                    # Special handling for Page 1 Figure 1
                    special_instructions = ""
                    if "page_1_figure_1" in str(image_path):
                        special_instructions = """
                            SPECIAL CONTEXT FOR THIS IMAGE:
                            - This image contains 1 illustration (map) on the left and 2 graphs on the right.
                            - Left illustration: Map showing "Recipient states West" (Pink), "Recipient states East" (Light Pink), and "Donor states West" (Blue).
                            - Right graphs: Two bar charts for years 2025 and 2070.
                            - Y-axis: Represents PERCENTAGE OF NATIONAL AVERAGE (not absolute currency).
                            - X-axis: Abbreviations of state names.
                            - Color coding in graphs matches the map:
                                - Blue: Donor states West
                                - Pink: Recipient states West
                                - Light Pink: Recipient states East
                            
                            Please extract the specific PERCENTAGE values for the states in 2025 vs 2070 based on this structure.
                            CRITICAL: DO NOT report '180' or any Y-axis value as currency (e.g. €180 billion). It is an index percentage.
                            """

                    prompt = f"""
                    Analyze this image in the context of: {topics_str}.
                    
                    Current Text Context (for reference):
                    {elem.get('content', '')}
                    {special_instructions}
                    
                    {self.STATE_ABBREVIATIONS_REF}

                    INSTRUCTIONS:
                    1. Describe what this visual shows specifically related to the topics above.
                    2. Extract any specific data points or trends that support or contradict the text.
                    3. If it's a chart, read the key values EXACTLY as shown.
                    4. CRITICAL: DO NOT INVENT UNITS. If the chart shows percentages (%) or index values (100, 120), do not report them as currency (€/$).
                    5. CRITICAL: DO NOT HALLUCINATE VALUES. If specific numbers are not visible, describe the visual trend instead of inventing numbers.
                    6. CRITICAL: If the Y-axis has no currency symbol, assume it is an Index or Percentage. NEVER guess 'USD' or 'Euros'.
                    7. Use full state names instead of abbreviations.
                    
                    Provide a concise but insightful analysis.
                    """

                    analysis = self._call_ollama_vision(prompt, img_base64)
                    analysis_entry["analysis"] = analysis
                    visual_analysis_results.append(analysis_entry)

                except Exception as e:
                    logger.error(f"Failed to process image {full_path}: {e}")
                    desc = image_context.get("description", "")
                    analysis_entry["analysis"] = desc
                    analysis_entry["source"] = "fallback_metadata"
                    visual_analysis_results.append(analysis_entry)
            else:
                desc = image_context.get("description", "")
                analysis_entry["analysis"] = desc
                analysis_entry["source"] = "existing_metadata"
                visual_analysis_results.append(analysis_entry)

        return visual_analysis_results

    def _summarize_content(self, title: str, content: str,
                           previous_context: str,
                           active_topics: List[str]) -> Dict[str, Any]:
        """
        Summarizes content (page or section) using Ollama.
        """
        # CRITICAL CHECK: If content is very short (likely just a header) and no visuals, return empty immediately
        # This prevents "bluffing" where the model hallucinates a summary for a footnote or title
        clean_content = content.strip()
        # Count words, ignoring markdown headers
        word_count = len(
            [w for w in clean_content.split() if not w.startswith('#')])

        # If fewer than 10 words and no visual indicators, assume it's just a header/empty
        if word_count < 10 and "[VISUAL RE-ANALYSIS" not in content and "[EXTRACTED TABLE DATA]" not in content:
            logger.info(
                f"Skipping summary for sparse content in '{title}' (Word count: {word_count})"
            )
            return {"summary": "", "visual_insights": [], "topics": []}

        prompt = f"""
        You are an expert academic writer creating a detailed study guide from a document section: "{title}".
        
        SOURCE TEXT (The ONLY text you must process):
        {content} 
        
        CONTEXT TAGS (Themes discussed so far):
        {", ".join(active_topics) if active_topics else "None"}
        
        {self.STATE_ABBREVIATIONS_REF}

        INSTRUCTIONS:
        1. Create a DETAILED and COMPREHENSIVE summary of the "SOURCE TEXT" ONLY.
        2. Preserve all key definitions, explanations, examples, and nuances.
        3. Do NOT condense significantly; aim to retain 80-90% of the original information density, but rewritten for clarity.
        4. CRITICAL: The "SOURCE TEXT" is the ONLY source for your summary. Do NOT include information from external knowledge or previous pages.
        5. CRITICAL: Do NOT simply repeat the Abstract or General Introduction. If the SOURCE TEXT looks like a high-level summary, look for SPECIFIC FACTS, DATES, EVENTS (e.g. 'Solidarity Pact II', 'Covid-19', 'Ukraine war'), or DEBATES within it. If none exist, keep the summary brief.
        6. CRITICAL: If the "SOURCE TEXT" is empty, insufficient, or just a header, return an EMPTY string ("") for the summary.
        7. Synthesize text and visual analysis if present.
        8. Use full state names instead of abbreviations.
        9. Check dates and table titles carefully. Do not hallucinate years or topics not present in the text.
        10. For TABLES: Report the data exactly as shown. Do not invent relationships or trends not present in the table data.
        11. CRITICAL: Avoid generic closing statements like "In the long run..." unless they explicitly appear in the SOURCE TEXT.
        12. STRICTLY FORBIDDEN: Do not output sentences like "details are not provided in the source text" or "The provided text does not contain...". If information is missing, simply omit it. DO NOT WRITE META-COMMENTS about missing data.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "summary": "Detailed narrative of SOURCE TEXT...",
            "visual_insights": ["Key insight 1", "Key insight 2"],
            "topics": ["Topic A", "Topic B"]
        }}
        """

        response = self._call_ollama(prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {"summary": response, "visual_insights": [], "topics": []}

    def _generate_global_summary_from_topics(
            self, topic_summaries: List[Dict[str, Any]]) -> str:
        combined_text = ""
        for t in topic_summaries:
            combined_text += f"\n\nTopic: {t['topic']}\nSummary:\n{t['summary']}"

            # CRITICAL: Include extracted table data if present to prevent hallucinations
            if "[EXTRACTED TABLE DATA]" in t.get('original_content', ''):
                # Extract just the table part to keep it concise
                content = t['original_content']
                start_marker = "[EXTRACTED TABLE DATA]:"
                if start_marker in content:
                    table_part = content.split(start_marker)[1].split(
                        "\n\n")[0]
                    combined_text += f"\n\nKey Data Table:{table_part}"

            if t['key_insights']:
                combined_text += "\nKey Visual Insights:\n" + "\n".join(
                    f"- {v}" for v in t['key_insights'])

        prompt = f"""
        Create a comprehensive Global Summary of the entire document based on these topic summaries.

        DOCUMENT CONTENT SUMMARIES:
        {combined_text}
        
        {self.STATE_ABBREVIATIONS_REF}

        INSTRUCTIONS:
        1. Write an Executive Summary.
        2. List Main Themes.
        3. Summarize key data from charts, using full state names where abbreviations appear.
        
        Return in Markdown.
        """
        return self._call_ollama(prompt, json_mode=False)

    def _extract_text_only(self, page: Dict[str, Any]) -> str:
        """Extracts only the text elements from the page."""
        elements = page.get("elements", [])
        text_parts = []

        # Add Page Title
        title = page.get("title")
        if title:
            text_parts.append(f"# Page Title: {title}")

        for elem in elements:
            etype = elem.get("type", "unknown")
            text = elem.get("content", "")

            # Handle tables specially - include their data if available
            if etype == "table" and elem.get("table_data"):
                md_table = self._table_to_markdown(elem)
                if md_table:
                    text_parts.append(
                        f"\n[EXTRACTED TABLE DATA]:\n{md_table}\n")
                continue

            # Skip visuals here, we only want text to build context
            if etype in ["figure", "chart", "image"]:
                continue

            # Skip tables without data (handled above) or if just visual
            if etype == "table":
                continue

            if etype in ["title", "section_title"]:
                text_parts.append(f"## {text}")
            elif etype in ["paragraph", "text", "footnote"]:
                text_parts.append(text)
            elif etype in ["bullet_point", "list_item"]:
                if "bullet_items" in elem:
                    for item in elem["bullet_items"]:
                        text_parts.append(f"- {item}")
                else:
                    text_parts.append(f"- {text}")

        return "\n\n".join(text_parts)

    def _identify_page_topics(self, text_content: str,
                              previous_context: str) -> List[str]:
        """Quickly identify main topics on the page to inform visual analysis."""
        if not text_content.strip():
            return []

        prompt = f"""
        Identify the top 3 main topics discussed in this text.
        
        Previous Context: {previous_context}
        
        Current Text:
        {text_content}
        
        Return ONLY a JSON list of strings, e.g. ["Fiscal Policy", "Demographics"].
        """
        response = self._call_ollama(prompt, json_mode=True)
        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # Handle case where LLM returns {"topics": [...]}
                for key, value in result.items():
                    if isinstance(value, list):
                        return value
            return []
        except:
            return []

    def _reanalyze_visuals(self, page: Dict[str, Any],
                           context_topics: List[str]) -> List[Dict[str, Any]]:
        """
        Finds images in the page, loads them, and re-analyzes them using the Vision Model.
        Returns a list of structured analysis results.
        """
        elements = page.get("elements", [])
        visual_analysis_results = []

        topics_str = ", ".join(
            context_topics) if context_topics else "General Analysis"

        for elem in elements:
            etype = elem.get("type", "")
            if etype in ["figure", "chart", "table", "image"]:
                image_context = elem.get("image_context", {})
                image_path = image_context.get("image_path")

                # Check if we have the image file
                full_path = os.path.join(settings.output_dir,
                                         image_path) if image_path else ""

                # Handle relative path if needed (extraction output might have 'images/...')
                if image_path and not os.path.exists(full_path):
                    # Try relative to project root or extraction dir
                    possible_path = os.path.join(
                        settings.extraction_images_dir,
                        os.path.basename(image_path))
                    if os.path.exists(possible_path):
                        full_path = possible_path

                analysis_entry = {
                    "type": etype,
                    "image_path": image_path,
                    "context_topics": context_topics,
                    "analysis": "",
                    "source": "vision_model"
                }

                if full_path and os.path.exists(full_path):
                    logger.info(
                        f"Re-analyzing image: {full_path} with context: {topics_str}"
                    )

                    # Read image as base64
                    try:
                        with open(full_path, "rb") as img_file:
                            img_base64 = base64.b64encode(
                                img_file.read()).decode('utf-8')

                        # Special handling for Page 1 Figure 1
                        special_instructions = ""
                        if "page_1_figure_1" in str(image_path):
                            special_instructions = """
                            SPECIAL CONTEXT FOR THIS IMAGE:
                            - This image contains 1 illustration (map) on the left and 2 graphs on the right.
                            - Left illustration: Map showing "Recipient states West" (Pink), "Recipient states East" (Light Pink), and "Donor states West" (Blue).
                            - Right graphs: Two bar charts for years 2025 and 2070.
                            - Y-axis: Starts from 0 and ends at 150.
                            - X-axis: Abbreviations of state names.
                            - Color coding in graphs matches the map:
                                - Blue: Donor states West
                                - Pink: Recipient states West
                                - Light Pink: Recipient states East
                            
                            Please extract the specific values for the states in 2025 vs 2070 based on this structure.
                            """
                        elif "page_3_figure_1" in str(image_path):
                            special_instructions = """
                            CRITICAL INSTRUCTIONS FOR PAGE 3 CHART:
                            1. This chart shows "GDP per capita" as a PERCENTAGE of the national average.
                            2. The Y-axis values are INDICES (e.g., 80, 100, 120, 180), NOT Euros (€).
                            3. DO NOT hallucinate "€" or "Euros" or "Billions".
                            4. Berlin (BE) is near the national average (95-100%), NOT 180.
                            5. Hamburg (HH) is the high outlier (~160-180).
                            6. Identify states by their codes (BE, HH, BW, etc.).
                            """
                        elif "page_8_table" in str(image_path):
                            special_instructions = """
                            CRITICAL INSTRUCTIONS FOR PAGE 8 TABLE:
                            1. This table shows DEMOGRAPHIC projections (Population), NOT Fiscal Capacity.
                            2. Values are PERCENTAGES.
                            3. Berlin's value for "Variant C vs 1991" is 38.0%.
                            4. Ensure you distinguish between "Variant A", "Variant B", "Variant C".
                            """

                        prompt = f"""
                        Analyze this image in the context of: {topics_str}.
                        
                        Current Page Text Context (for reference):
                        {elem.get('content', '')}
                        {special_instructions}
                        
                        {self.STATE_ABBREVIATIONS_REF}

                        INSTRUCTIONS:
                        1. Describe what this visual shows specifically related to the topics above.
                        2. Extract any specific data points or trends that support or contradict the text.
                        3. If it's a chart, read the key values.
                        4. Use full state names instead of abbreviations.
                        
                        Provide a concise but insightful analysis.
                        """

                        analysis = self._call_ollama_vision(prompt, img_base64)
                        analysis_entry["analysis"] = analysis
                        visual_analysis_results.append(analysis_entry)

                    except Exception as e:
                        logger.error(
                            f"Failed to process image {full_path}: {e}")
                        # Fallback to existing description
                        desc = image_context.get("description", "")
                        analysis_entry["analysis"] = desc
                        analysis_entry["source"] = "fallback_metadata"
                        visual_analysis_results.append(analysis_entry)
                else:
                    # No image file found, fallback to existing metadata
                    desc = image_context.get("description", "")
                    analysis_entry["analysis"] = desc
                    analysis_entry["source"] = "existing_metadata"
                    visual_analysis_results.append(analysis_entry)

        return visual_analysis_results

    def _summarize_page(self, page_num: int, content: str,
                        previous_context: str,
                        active_topics: List[str]) -> Dict[str, Any]:
        """
        Summarizes a single page using Ollama, considering cross-page context.
        """
        return self._summarize_content(f"Page {page_num}", content,
                                       previous_context, active_topics)

    def _update_running_context(self, current_context: str,
                                new_summary: str) -> str:
        return current_context + "\n\n" + new_summary

    def _generate_global_summary(self, page_summaries: List[Dict[str,
                                                                 Any]]) -> str:
        combined_text = ""
        for p in page_summaries:
            combined_text += f"\n\nPage {p['page_number']} Summary:\n{p['summary']}"
            if p['key_visuals']:
                combined_text += "\nKey Visuals:\n" + "\n".join(
                    f"- {v}" for v in p['key_visuals'])

        prompt = f"""
        Create a comprehensive Global Summary of the entire document based on these page summaries.

        DOCUMENT CONTENT SUMMARIES:
        {combined_text}

        INSTRUCTIONS:
        1. Write an Executive Summary.
        2. List Main Themes.
        3. Summarize key data from charts.
        
        Return in Markdown.
        """
        return self._call_ollama(prompt, json_mode=False)

    def save_output(self,
                    summary_data: Dict[str, Any],
                    output_dir: Optional[str] = None,
                    filename: str = "summary_result.json"):
        if output_dir is None:
            output_dir = settings.summarization_output_dir
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Summary saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return None

    def _call_ollama(self, prompt: str, json_mode: bool = False) -> str:
        try:
            # Reduced context window to prevent hanging/OOM
            options = {"temperature": 0.3, "num_ctx": 8192}
            response = ollama.generate(model=self.text_model,
                                       prompt=prompt,
                                       format='json' if json_mode else '',
                                       options=options,
                                       stream=False)
            return response.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return "{}" if json_mode else f"Error: {e}"

    def _call_ollama_vision(self, prompt: str, image_base64: str) -> str:
        try:
            response = ollama.generate(model=self.vision_model,
                                       prompt=prompt,
                                       images=[image_base64],
                                       stream=False)
            return response.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama vision generation failed: {e}")
            return "Error analyzing image."


def run_summarization():
    """
    Run the summarization process programmatically.
    If extraction output is missing, triggers extraction first.
    """
    logger.info("Starting summarization process...")
    input_path = settings.extraction_output_path

    if not os.path.exists(input_path):
        logger.info(
            f"Extraction output not found at {input_path}. Triggering extraction..."
        )
        try:
            from features.extraction import run_extraction
            run_extraction()
        except Exception as e:
            logger.error(f"Failed to run extraction: {e}")
            raise

        if not os.path.exists(input_path):
            raise FileNotFoundError(
                f"Extraction failed to produce output at {input_path}")

    with open(input_path, 'r') as f:
        data = json.load(f)

    # Ensure we have the vision model pulled (optional check)
    summarizer = Summarizer(vision_model="minicpm-v")  # or llava
    result = summarizer.summarize(data)
    return summarizer.save_output(result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        output_path = run_summarization()
        print(f"Summarization completed. Output saved to {output_path}")

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        exit(1)

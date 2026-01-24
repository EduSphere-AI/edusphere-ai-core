"""
SLIDE DECK GENERATOR WITH INTELLIGENT CHUNKING

This module organizes extracted academic content into presentation slides with:
1. Content-aware chunking (each chunk = 1 slide, sized appropriately)
2. Chapter/subchapter structure preservation
3. Figure/table consideration in chunk sizing
4. Learn control questions (3-4 per subchapter) for reflection
"""

import json
import hashlib
import logging
import os
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple, Union

try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config import settings

logger = logging.getLogger(__name__)

# === PRE-COMPILED REGEX PATTERNS ===
RE_CHUNK_BOUNDARY = re.compile(r'\[CHUNK \d+\]')
RE_NUMBERED_LINE = re.compile(r'^\d+\.\s+(.+)$')
RE_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
RE_JSON_COMMENTS = re.compile(r',\s*\([^)]*\)')

# === CONSTANTS ===
OPTIMAL_SLIDE_WORDS = 200  # Increased for more detail
MAX_SLIDE_WORDS = 400  # Increased limit
MIN_SLIDE_WORDS = 50  # Minimum before considering slide complete
MAX_BULLETS_PER_SLIDE = 10  # Increased
MAX_PARAGRAPHS_PER_SLIDE = 4

# Element weights (equivalent words)
FIGURE_WEIGHT = 100
TABLE_WEIGHT = 100

# Elements to skip (non-educational content)
SKIP_ELEMENT_TYPES = {"author", "footer", "footnote", "caption", "header"}
SKIP_SECTION_TITLES = {
    "FROM THE AUTHORS", "MEDIA", "LEGAL AND EDITORIAL DETAILS"
}
SKIP_KEYWORDS = {
    "phone:", "fax:", "publishers", "editors", "editorial", "volume"
}


class OllamaCache:

    def __init__(self, cache_file: Union[str, Path]):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_cache(self):
        self.cache_file.parent.mkdir(exist_ok=True, parents=True)
        self.cache_file.write_text(json.dumps(self.cache, indent=2),
                                   encoding='utf-8')

    def get(self, prompt: str) -> Optional[str]:
        key = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        return self.cache.get(key)

    def set(self, prompt: str, response: str):
        key = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        self.cache[key] = response
        self._save_cache()


class ContentItem:
    """Represents a single content element (paragraph, bullet, figure, etc.)"""

    def __init__(self,
                 item_type: str,
                 content: str,
                 metadata: Optional[Dict[str, Any]] = None):
        self.type = item_type  # 'paragraph', 'bullet', 'figure', 'table', 'section_title'
        self.content = content.strip() if isinstance(content, str) else ""
        self.metadata = metadata or {}
        self._word_count_cache = None

    def word_count(self) -> int:
        """Count words in this item (cached)."""
        if self._word_count_cache is None:
            self._word_count_cache = len(self.content.split())
        return self._word_count_cache

    def is_structural(self) -> bool:
        """Returns True if this is a structural element (title, section_title, figure caption)"""
        return self.type in ("section_title", "figure", "table")


class Slide:
    """Represents a single slide in the presentation"""

    def __init__(self, chapter_num: Optional[int], slide_num: int, title: str,
                 items: List[ContentItem]):
        self.chapter_num = chapter_num
        self.slide_num = slide_num
        self.title = title
        self.items = items  # List of ContentItem

    def word_count(self) -> int:
        """Total word count of all content"""
        return sum(item.word_count() for item in self.items)

    def has_figure(self) -> bool:
        """Check if slide contains any figures"""
        return any(item.type == "figure" for item in self.items)

    def render_markdown(self) -> str:
        """Render slide to markdown"""
        lines = []
        if self.chapter_num is None:
            lines.append(f"### Slide {self.slide_num}: {self.title}\n")
        else:
            lines.append(
                f"### Slide {self.chapter_num}.{self.slide_num}: {self.title}\n"
            )

        for item in self.items:
            if item.type == "section_title":
                lines.append(f"#### {item.content}\n")
            elif item.type == "paragraph":
                lines.append(f"{item.content}\n")
            elif item.type == "bullet":
                lines.append(f"- {item.content}")
            elif item.type == "figure":
                caption = item.metadata.get("caption", "Figure")
                description = item.metadata.get("description", "")
                image_path = item.metadata.get(
                    "image_url") or item.metadata.get("image_path", "")

                if image_path:
                    lines.append(f"\n![{caption}]({image_path})")

                lines.append(f"\n**Figure:** {caption}")
                if description:
                    lines.append(f"**Description:** {description}\n")
            elif item.type == "table":
                caption = item.metadata.get("caption", "Table")
                image_path = item.metadata.get(
                    "image_url") or item.metadata.get("image_path", "")

                if image_path:
                    lines.append(f"\n![{caption}]({image_path})")

                lines.append(f"\n**Table:** {caption}\n")

        lines.append("\n---\n")
        return "\n".join(lines)


class Chapter:
    """Represents a chapter with multiple slides and subchapters"""

    def __init__(self,
                 chapter_num: Optional[int],
                 main_title: str,
                 subtitle: str = ""):
        self.chapter_num = chapter_num
        self.main_title = main_title  # Before colon
        self.subtitle = subtitle  # After colon
        self.slides = []
        self.subchapters = defaultdict(list)  # subchapter_title -> [slides]
        self.learn_controls = defaultdict(
            list)  # subchapter_title -> [questions]

    def add_slide(self, slide: Slide, subchapter: Optional[str] = None):
        """Add slide to chapter and optionally track subchapter"""
        self.slides.append(slide)

        # Ensure every slide belongs to a subchapter bucket
        key = subchapter if subchapter else "Introduction"
        self.subchapters[key].append(slide)

    def render_markdown(self) -> str:
        """Render entire chapter with learn controls at the end of each subchapter"""
        lines = []
        # Show main title first
        if self.chapter_num is None:
            lines.append(f"\n## {self.main_title}\n")
        else:
            lines.append(
                f"\n## Chapter {self.chapter_num}: {self.main_title}\n")

        # Add subtitle if present
        if self.subtitle:
            lines.append(f"_{self.subtitle}_\n")

        # Optimize: Group slides by subchapter more efficiently
        # Use a list of keys to preserve order instead of repeated lookups
        subchapter_order = []
        seen_subchapters = set()

        # First pass: identify subchapters in order
        for slide in self.slides:
            # Find which subchapter this slide belongs to
            found = False
            for subchapter_title, slides in self.subchapters.items():
                if slide in slides:
                    if subchapter_title not in seen_subchapters:
                        subchapter_order.append(subchapter_title)
                        seen_subchapters.add(subchapter_title)
                    found = True
                    break
            if not found and "Introduction" not in seen_subchapters:
                subchapter_order.append("Introduction")
                seen_subchapters.add("Introduction")

        # Render each subchapter with its slides and then its learn controls
        for subchapter_title in subchapter_order:
            lines.append(f"\n#### {subchapter_title}\n")

            # Render all slides in this subchapter
            # Use direct lookup from pre-computed dictionary
            for slide in self.subchapters[subchapter_title]:
                lines.append(slide.render_markdown())

            # Add learn controls for this subchapter at the end
            if subchapter_title in self.learn_controls:
                lines.append("##### Learn Control Questions\n")
                for j, item in enumerate(self.learn_controls[subchapter_title],
                                         1):
                    if isinstance(item, dict):
                        lines.append(f"{j}. **Q:** {item['question']}\n")
                        lines.append(f"   **A:** {item['answer']}\n")
                    else:
                        # Backward compatibility for string-only questions
                        lines.append(f"{j}. {item}\n")
                lines.append("\n---\n")

        return "\n".join(lines)


class ProcessingState:
    """Encapsulates mutable state during document processing"""

    def __init__(self):
        self.chapters = []
        self.current_chapter: Optional[Chapter] = None
        self.current_chapter_num = 0
        self.current_subchapter: Optional[str] = None
        self.slide_buffer = []
        self.buffer_word_count = 0
        self.subchapter_slides = defaultdict(list)
        self.chapters_since_last_questionnaire = 0

    def flush_slide_buffer(self,
                           title_override: Optional[str] = None
                           ) -> Optional[Slide]:
        """Convert buffer contents to a slide"""
        if not self.slide_buffer:
            return None

        # Generate title from content if not provided
        if not title_override:
            # Extract from first section_title or generate from content
            section_titles = [
                item.content for item in self.slide_buffer
                if item.type == "section_title"
            ]
            title_override = section_titles[0] if section_titles else "Content"

        slide = Slide(
            self.current_chapter_num,
            len(self.current_chapter.slides) +
            1 if self.current_chapter else 1, title_override,
            self.slide_buffer.copy())

        self.slide_buffer.clear()
        self.buffer_word_count = 0
        return slide


class SlideGenerator:

    def __init__(self,
                 model: str = "llama3.2",
                 cache_path: str = "output/slides/.ollama_cache.json",
                 enable_questionnaire: bool = True,
                 questionnaire_frequency: int = 1):
        self.model = model
        self.cache = OllamaCache(cache_path)
        self.enable_questionnaire = enable_questionnaire
        self.questionnaire_frequency = questionnaire_frequency
        self.image_url_map = {}  # Initialize usage map
        logger.info(
            f"Initialized SlideGenerator with model: {self.model}, cache: {cache_path}, "
            f"questionnaire: {self.enable_questionnaire}, freq: {self.questionnaire_frequency}, "
            f"ollama_available: {OLLAMA_AVAILABLE}")

    def call_ollama(self,
                    prompt: str,
                    fallback_value: Optional[str] = None) -> str:
        """
        Safely call Ollama with consistent error handling and caching.
        Returns fallback_value if Ollama unavailable or call fails.
        """
        if not OLLAMA_AVAILABLE:
            return fallback_value or ""

        # Check cache first
        cached_response = self.cache.get(prompt)
        if cached_response:
            return cached_response

        try:
            response = ollama.generate(model=self.model,
                                       prompt=prompt,
                                       stream=False)
            result = response.get("response", "").strip()
            # Cache the successful response
            if result:
                self.cache.set(prompt, result)
            return result
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            return fallback_value or ""

    def generate_slide_title(self, items: list) -> str:
        """
        Use Ollama to generate a precise, semantic slide title from content items.
        """
        # Collect content text
        text_parts = []
        for item in items:
            if item.type in ("paragraph", "bullet"):
                text_parts.append(item.content)
            elif item.type in ("figure", "table"):
                caption = item.metadata.get("caption", "")
                if caption:
                    text_parts.append(f"[{item.type.upper()}: {caption}]")

        content_text = " ".join(text_parts)

        if not content_text.strip():
            return "Content"

        prompt = f"""Given the following content, generate a single concise slide title that captures the main concept. 
Respond with ONLY the title, nothing else.

Content:
{content_text[:500]}

Title:"""

        title = self.call_ollama(prompt, fallback_value=None)
        if title:
            # Clean up the title
            title = title.replace('\n', '').strip('"').strip()
            if len(title) > 5 and len(title) < 100:
                return title

        # Fallback: extract keywords
        keywords = []
        for item in items:
            if item.type in ("paragraph", "bullet"):
                words = [
                    w for w in item.content.split()
                    if len(w) > 5 and not w.endswith(",")
                ]
                keywords.extend(words[:3])

        if keywords:
            title = " ".join(keywords[:3])
            return title if len(title) > 10 else "Key Concepts"
        return "Key Concept"

    def split_title_at_colon(self, title: str) -> tuple:
        """
        Split a title at colon: before colon is main title, after is subtitle.
        """
        if ":" in title:
            parts = title.split(":", 1)
            return parts[0].strip(), parts[1].strip()
        return title.strip(), ""

    def extract_clean_figure_data(self, ctx: dict) -> tuple:
        """
        Extract and enhance caption and description from figure metadata using Ollama.
        """
        # Get caption
        caption = ctx.get("title") or ctx.get("caption", "Figure")

        # Clean up JSON-encoded captions
        if isinstance(caption, str) and caption.startswith("{"):
            try:
                cap_obj = json.loads(caption)
                caption = cap_obj.get("title", "Figure")
            except:
                caption = "Figure"

        # Get description
        desc = ctx.get("description", "")
        if isinstance(desc, str) and desc.startswith("{"):
            try:
                desc_obj = json.loads(desc)
                desc = desc_obj.get("description",
                                    desc_obj.get("key_insights", ""))
            except:
                desc = "See document for detailed figure information."

        # Use Ollama to enhance description if it exists
        if desc and len(desc) > 20:
            prompt = f"""Rewrite this figure/chart description to be clear, concise, and pedagogically useful in an academic slide. 
Respond with ONLY the rewritten description, nothing else.
Keep it to 2-3 sentences max. Remove jargon where possible.
CRITICAL: Interpret all standalone numbers as PERCENTAGES or INDEX POINTS, NOT CURRENCY, unless a currency symbol (€, $, etc.) is explicitly present in the source text.
            CRITICAL: Do not invent years or dates (e.g. 2015) if they are not present in the text.
            CRITICAL: Variant A corresponds to 150,000 people (low immigration). Variant B corresponds to 250,000 people (medium immigration). Do not confuse these numbers.
            """
            # Pass fallback_value as None to handle missing Ollama gracefully inside call_ollama
            enhanced_desc = self.call_ollama(prompt, fallback_value=None)
            if enhanced_desc and len(enhanced_desc) > 10:
                desc = enhanced_desc

        # Limit description to reasonable length
        if len(desc) > 400:
            desc = desc[:397] + "..."

        return str(caption)[:100], str(desc)

    def generate_learn_controls(self, subchapter_title: str,
                                slide_contents: list) -> list:
        """
        Generate 4 open-ended learning control questions using Ollama at different cognitive levels.
        """
        # Clean title for prompt usage to avoid mechanical references
        # Remove (Section X), (Box X), Page X -
        clean_title = re.sub(r'\s*\(Section\s*\d+(?:\s*&\s*\d+)?\)', '',
                             subchapter_title)
        clean_title = re.sub(r'\s*\(Box\s*\d+\)', '', clean_title)
        clean_title = re.sub(r'Page \d+ - ', '', clean_title)
        clean_title = clean_title.strip()

        # Combine all content for context
        all_text_parts = (item.content for item in slide_contents
                          if item.type in ("paragraph", "bullet"))
        all_text = " ".join(all_text_parts)

        if not all_text.strip():
            return []

        prompt = f"""You are an expert instructional designer creating assessment questions. Given the following academic content 
from a section titled "{clean_title}", generate exactly 4 open-ended reflection questions that test different cognitive levels.
For each question, provide a concise model answer.

1. One DEFINITION/COMPREHENSION question: Testing understanding of key concepts
2. One ANALYSIS/EXPLANATION question: Testing how concepts relate to each other
3. One APPLICATION/EVALUATION question: Testing real-world or practical implications
4. One CRITICAL THINKING question: Asking learners to question or extend the content

CRITICAL INSTRUCTIONS FOR QUESTION PHRASING:
- DO NOT reference the document structure (e.g., "In this section", "According to the text", "As shown in the graph", "In Section 7").
- DO NOT mention "the author" or "the report".
- Ask directly about the SUBJECT MATTER (e.g., "How does fiscal capacity affect...", "Why is the East-West gap...").
- Use the concept name "{clean_title}" naturally if needed, but prefer asking about the underlying concepts.
- Questions must be self-contained and make sense without seeing the slide.

Format the output EXACTLY as follows:
Q1: [Question text]
A1: [Model Answer]

Q2: [Question text]
A2: [Model Answer]

Q3: [Question text]
A3: [Model Answer]

Q4: [Question text]
A4: [Model Answer]
"""

        text = self.call_ollama(prompt, fallback_value=None)
        if text:
            # Parse Q&A pairs
            questions = []
            current_q = None
            current_a = None

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Match Q1:, Q2:, etc.
                if re.match(r'^Q\d+:', line):
                    if current_q:
                        questions.append({
                            "question":
                            current_q,
                            "answer":
                            current_a or "Answer not provided."
                        })
                    current_q = line.split(':', 1)[1].strip()
                    current_a = None
                # Match A1:, A2:, etc.
                elif re.match(r'^A\d+:', line):
                    current_a = line.split(':', 1)[1].strip()
                # Append continuation lines
                elif current_q and current_a is None:
                    current_q += " " + line
                elif current_a:
                    current_a += " " + line

            # Append last pair
            if current_q:
                questions.append({
                    "question": current_q,
                    "answer": current_a or "Answer not provided."
                })

            if questions:
                return questions[:4]

        # Fallback if Ollama unavailable
        return [{
            "question":
            f"What are the key definitions and concepts presented in {clean_title}?",
            "answer":
            "Key concepts include the main topics discussed in the section."
        }, {
            "question":
            f"How do the different elements discussed in {clean_title} relate to and support each other?",
            "answer":
            "The elements are interconnected and support the central thesis of the section."
        }, {
            "question":
            f"What are the practical or real-world applications of the information in {clean_title}?",
            "answer":
            "The information can be applied to understand real-world scenarios related to the topic."
        }, {
            "question":
            f"What are the limitations or assumptions underlying the content in {clean_title}? What further questions does this raise?",
            "answer":
            "Limitations may include scope of data or specific assumptions made by the author."
        }]

    def generate_questionnaire_slides(self,
                                      chapters: List[Chapter]) -> List[Slide]:
        """
        Generate a questionnaire slide with Q&A based on the provided chapters.
        """
        if not chapters:
            return []

        # Gather content from chapters
        combined_text = ""
        chapter_titles = []
        for chapter in chapters:
            chapter_titles.append(chapter.main_title)
            for slide in chapter.slides:
                for item in slide.items:
                    if item.type in ("paragraph", "bullet"):
                        combined_text += item.content + " "

        combined_text = combined_text[:4000]  # Limit context size
        titles_str = ", ".join(chapter_titles)

        prompt = f"""You are an expert educator creating a review quiz. 
Based on the content from the following chapters: {titles_str}, generate 3 multiple-choice questions with answers.

Content:
{combined_text}

Format the output EXACTLY as follows:
Q1: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Answer: [Correct Option Letter] - [Brief Explanation]

Q2: ...
...
"""
        response = self.call_ollama(prompt)
        if not response:
            logger.warning(
                "Ollama unavailable for questionnaire. Using fallback.")
            response = f"""Q1: Review Question for {titles_str}
A) Option A
B) Option B
C) Option C
D) Option D
Answer: A - Placeholder answer due to AI unavailability.

Q2: Key Concept Check
A) Concept 1
B) Concept 2
C) Concept 3
D) Concept 4
Answer: B - Placeholder answer due to AI unavailability.

Q3: Critical Analysis
A) Analysis Point 1
B) Analysis Point 2
C) Analysis Point 3
D) Analysis Point 4
Answer: C - Placeholder answer due to AI unavailability."""

        # Parse response into slide content
        items = []
        items.append(ContentItem("paragraph", f"Review of: {titles_str}"))

        # Simple parsing - just add as paragraphs/bullets
        # We want to format it nicely.

        lines = response.split('\n')
        current_q = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("Q") and ":" in line[:4]:
                items.append(ContentItem("section_title", line))
            elif line.startswith("Answer:"):
                items.append(ContentItem("paragraph", f"**{line}**"))
            elif line[0] in "ABCD" and line[1] == ")":
                items.append(ContentItem("bullet", line))
            else:
                items.append(ContentItem("paragraph", line))

        slide = Slide(
            chapters[-1].
            chapter_num,  # Assign to the last chapter in the batch
            len(chapters[-1].slides) + 1,
            "Review & Assessment",
            items)

        return [slide]

    def split_paragraph_into_chunks(self,
                                    text: str,
                                    max_words: int,
                                    topic_title: str = "") -> list:
        """
        Use Ollama to intelligently split a paragraph at logical concept boundaries.
        """
        # Fix specific data extraction errors (Unit Errors)
        # "150, by" -> "150,000 by"
        # "250, peop" -> "250,000 peop"
        text = re.sub(r'(\d{2,3}),\s+(by|peop)', r'\1,000 \2', text)

        # ------------------------------------------------------------------
        # CRITICAL FIXES FOR HALLUCINATIONS (Direct Text Replacement)
        # ------------------------------------------------------------------

        # 1. Fix Table 1 Misinterpretation (Slide 6.1)
        # Replace "fiscal capacity/economic indicator" with "Population Change"
        if "Page 5 - Table 1" in topic_title:
            text = text.replace(
                "lists each state along with its corresponding value, which appears to represent a fiscal capacity or economic indicator",
                "lists each state along with its corresponding value, representing the percentage change in population from 1991 to 2024"
            )
            text = text.replace("Fiscal Capacity", "Population Change")

        # 2. Fix Table 2 Misinterpretation (Slide 9.1)
        # Replace "economic impact" with "Population Development Assumptions"
        if "Page 8 - Table 2" in topic_title:
            text = text.replace(
                "presents data on the economic impact of different variants of immigration policies",
                "presents assumptions regarding population development under different immigration variants"
            )
            text = text.replace("economic growth or decline",
                                "projected population changes")
            text = text.replace("Economic Impact",
                                "Population Development Assumptions")

        # Fix Variant Definitions (Page 8)
        if "Page 8" in topic_title:
            text = text.replace(
                "Variant A, based on 250,000 people (G2L2W2)",
                "Variant A is based on 150,000 people (G2L2W1); Variant B is based on 250,000 people (G2L2W2)"
            )
            text = text.replace(
                "Variant A is based 250,000 people (G2L2W2)",
                "Variant A is based on 150,000 people (G2L2W1); Variant B is based on 250,000 people (G2L2W2)"
            )

        # 3. Fix Wealthy States Misinterpretation (Slide 3.1)
        # Correct the list of wealthy states
        if "Page 2" in topic_title or "Page 3" in topic_title:
            text = text.replace(
                "North Rhine-Westphalia, Bavaria, Hesse, Lower Saxony, Rhineland-Palatinate, Saarland, Schleswig-Holstein, Berlin, Bremen, and Hamburg are among the wealthiest",
                "Bavaria, Baden-Württemberg, Hesse, and Hamburg are identified as the wealthy, donor states"
            )

        # 4. Fix City-States Description (Slide 4.1)
        # Correct "fall short" generalization
        if "Page 3" in topic_title:
            text = text.replace(
                "fall short of western German state levels",
                "show high economic performance, with Hamburg and Bremen exceeding western averages"
            )

        # 5. Fix Date Hallucination (Slide 2.2)
        # Remove "2015" reference
        text = text.replace("trends from 2015 to projections",
                            "trends from 2024 to projections")

        # ------------------------------------------------------------------

        # Detect Markdown tables - return as single chunk to prevent hallucination
        if "|" in text and "---" in text:
            return [text.strip()]

        words = text.split()
        if len(words) <= max_words:
            return [text.strip()]

        # For very long text, use Ollama to identify chunk boundaries
        num_chunks = (len(words) // max_words) + 1

        special_instruction = "\nCRITICAL: Interpret all standalone numbers as PERCENTAGES or INDEX POINTS, NOT CURRENCY, unless a currency symbol (€, $, etc.) is explicitly present in the source text."

        if "Conclusion" in topic_title or "Variant" in text or "Scenario" in text:
            special_instruction += "\nCRITICAL: Ensure that 'Scenario' and 'Variant' definitions are kept with their descriptions. Do not mix them up."
            special_instruction += "\nCRITICAL: Variant A = 150,000 (low immigration), Variant B = 250,000 (medium immigration). Do not swap these numbers."

        if "GDP" in text or "Page 3" in topic_title:
            special_instruction += "\nCRITICAL: If the text mentions GDP Index or units, keep them exactly as is (e.g. do not convert Index points to currency)."

        if "Hamburg" in text or "Berlin" in text or "East" in text:
            special_instruction += "\nCRITICAL: Do not alter geographical classifications. Hamburg is West. Berlin is distinct."

        # Fix Date Hallucination
        if "2015" not in text:
            special_instruction += "\nCRITICAL: Do not mention the year 2015 unless it is explicitly in the text. Use 2024, 2025, or 2070 as appropriate based on the text."

        # Fix Table 1 Misinterpretation (Population vs Fiscal)
        if "Page 5 - Table 1" in topic_title:
            special_instruction += "\nCRITICAL: The data in this table represents POPULATION CHANGE (percentage), NOT fiscal capacity or economic indicators. Do not hallucinate 'fiscal capacity'."

        # Fix Table 2 Misinterpretation (Population Assumptions vs Economic Impact)
        if "Page 8 - Table 2" in topic_title:
            special_instruction += "\nCRITICAL: The data in this table represents POPULATION DEVELOPMENT ASSUMPTIONS, NOT economic growth or impact."
            special_instruction += "\nCRITICAL: Variant A is based on 150,000 people. Variant B is based on 250,000 people."

        # Fix Wealthy States Misinterpretation
        if "Page 3" in topic_title or "Page 4" in topic_title:
            special_instruction += "\nCRITICAL: Strictly adhere to the source text for state classifications. Bavaria, Baden-Württemberg, Hesse, and Hamburg are 'wealthy/donor' states. Saarland and Rhineland-Palatinate are NOT wealthy."
            special_instruction += "\nCRITICAL: Hamburg and Bremen have high GDP/Value Added. Do not generalize that city-states fall short of western levels."

        prompt = f"""You are an instructional design expert. Split the following academic text into {num_chunks} logical chunks 
where each chunk covers ONE concept and is approximately {max_words} words. 
Each chunk should be pedagogically complete and understandable independently.
Maintain the original text exactly—do not paraphrase or summarize.
CRITICAL: Do not change any numbers or data values. Keep the text verbatim.{special_instruction}

Respond in this format:
[CHUNK 1]
Text here...
[CHUNK 2]
Text here...

Do NOT add explanation or comments, ONLY the chunked text:

{text}"""

        result_text = self.call_ollama(prompt, fallback_value=None)
        if result_text:
            # Parse chunks from response
            chunks = RE_CHUNK_BOUNDARY.split(result_text)
            chunks = [c.strip() for c in chunks if c.strip()]
            if chunks:
                return chunks

        # Fallback to simple sentence-based chunking
        return self._fallback_chunking(text, max_words)

    def _fallback_chunking(self, text: str, max_words: int) -> list:
        """Fallback sentence-based chunking when Ollama unavailable."""
        chunks = []
        sentences = RE_SENTENCE_SPLIT.split(text)
        current = []
        current_count = 0

        for sentence in sentences:
            s_words = sentence.split()
            if current_count + len(s_words) <= max_words:
                current.append(sentence)
                current_count += len(s_words)
            else:
                if current:
                    chunks.append(" ".join(current).strip())

                if len(s_words) > max_words:
                    # Split very long sentences into word chunks
                    for i in range(0, len(s_words), max_words):
                        chunk = " ".join(s_words[i:i + max_words]).strip()
                        if chunk:
                            chunks.append(chunk)
                    current = []
                    current_count = 0
                else:
                    current = [sentence]
                    current_count = len(s_words)

        if current:
            chunks.append(" ".join(current).strip())

        return chunks if chunks else [text.strip()]

    def remove_comments_safe(self, content: str) -> str:
        """
        Safely remove (comments) from JSON content, ignoring parentheses inside strings.
        """
        result = []
        in_string = False
        escape = False
        in_comment = False

        for char in content:
            if in_comment:
                if char == ')':
                    in_comment = False
                continue

            if in_string:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_string = False
                result.append(char)
                continue

            # Not in string and not in comment
            if char == '"':
                in_string = True
                result.append(char)
            elif char == '(':
                in_comment = True
            else:
                result.append(char)

        return "".join(result)

    def _create_intro_slide(self, topic_summaries: list,
                            state: ProcessingState):
        """
        Creates an introductory slide with Title, Author, and Key Quote.
        """
        doc_title = "Presentation"
        doc_author = "Unknown Author"
        key_quote = ""

        # Scan first few topics for metadata
        for topic in topic_summaries[:3]:
            content = topic.get("original_content", "")
            topic_name = topic.get("topic", "")

            # Try to find Title and Author in Page 1 Header
            if "Page 1" in topic_name and "Header" in topic_name:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "Page 1" in line or not line.strip():
                        continue
                    if doc_title == "Presentation" and len(line.strip()) > 10:
                        doc_title = line.strip()
                        # Look ahead for author
                        for j in range(1, 4):
                            if i + j < len(lines):
                                next_line = lines[i + j].strip()
                                if next_line.startswith("By "):
                                    doc_author = next_line.replace("By ",
                                                                   "").strip()
                                    break
                    elif line.strip().startswith("By "):
                        doc_author = line.strip().replace("By ", "").strip()

            # Try to find Quote in Page 1 Chart Area or similar
            if "35 years since" in content:
                # Regex to extract the quote
                matches = re.findall(r'“([^”]+)”', content)
                for m in matches:
                    if "35 years" in m:
                        key_quote = m
                        break
                if not key_quote:
                    # Fallback string extraction
                    try:
                        start = content.find("“35 years")
                        if start == -1:
                            start = content.find("35 years")
                        end = content.find("”", start)
                        if start != -1 and end != -1:
                            key_quote = content[start:end].strip('“')
                    except:
                        pass

        # Create the slide
        intro_items = [
            ContentItem("section_title", doc_title),
            ContentItem("paragraph", f"**Author:** {doc_author}"),
        ]

        if key_quote:
            intro_items.append(ContentItem("paragraph", f"_\"{key_quote}\"_"))

        # Add to state as Chapter 0 (Introduction)
        state.current_chapter_num = 0
        state.current_chapter = Chapter(None, "Introduction")
        state.chapters.append(state.current_chapter)

        slide = Slide(None, 1, "Presentation Overview", intro_items)
        state.current_chapter.add_slide(slide, "Introduction")
        state.subchapter_slides["Introduction"].append(slide)
        logger.info("Created Introduction slide (Chapter None).")

    def _generate_chapter_titles(self,
                                 topic_summaries: list) -> Dict[str, str]:
        """
        Generates unique, content-aware chapter titles for each Page group.
        Returns a dict: {'Page 1': 'Introduction', 'Page 2': 'Fiscal Analysis', ...}
        """
        logger.info("Generating content-aware chapter titles...")
        page_content = defaultdict(list)

        # Group summaries by Page
        for topic in topic_summaries:
            topic_title = topic.get("topic", "")
            summary = topic.get("summary", "")
            if " - " in topic_title:
                main_part = topic_title.split(" - ")[0]
                page_content[main_part].append(summary)
            elif ": " in topic_title:
                main_part = topic_title.split(": ")[0]
                page_content[main_part].append(summary)

        chapter_titles = {}

        for page, summaries in page_content.items():
            combined_summary = " ".join(summaries)[:1000]  # Limit context
            if not combined_summary.strip():
                chapter_titles[page] = f"{page} Content"
                continue

            prompt = f"""Generate a short, engaging, and unique chapter title (max 5 words) for a presentation section covering the following content.
            The title should be descriptive but catchy. Do NOT use "Page X" or "Chapter X" in the title.
            Respond with ONLY the title.

            Content:
            {combined_summary}

            Title:"""

            title = self.call_ollama(prompt, fallback_value=f"{page} Overview")
            title = title.replace('"', '').replace("Title:", "").strip()
            # Clean up newlines
            title = title.split('\n')[0]
            chapter_titles[page] = title
            logger.info(f"Generated title for {page}: {title}")

        return chapter_titles

    def _process_summary_input(self, topic_summaries: list,
                               state: ProcessingState):
        """
        Process summary output format where content is pre-summarized by topic.
        Aligns slides along the structure of chapters and subchapters.
        """
        logger.info("Processing summary input format...")

        # 1. Create Introduction Slide
        self._create_intro_slide(topic_summaries, state)

        # 2. Generate Content-Aware Chapter Titles
        chapter_title_map = self._generate_chapter_titles(topic_summaries)

        for i, topic_data in enumerate(topic_summaries, 1):
            topic_title = topic_data.get("topic", f"Topic {i}")
            summary_text = topic_data.get("summary", "")

            # Attempt to extract Chapter vs Subchapter from title
            if " - " in topic_title:
                main_part, sub_part = topic_title.split(" - ", 1)
            elif ": " in topic_title:
                main_part, sub_part = topic_title.split(": ", 1)
            else:
                main_part = topic_title
                sub_part = "Main Content"

            # Determine dynamic chapter title
            # Use original main_part (e.g. "Page 1") to look up dynamic title
            # If not found, fall back to main_part itself
            chapter_title = chapter_title_map.get(main_part, main_part)

            # === CUSTOM LOGIC FOR PAGE 2 GROUPING ===
            # Goal: Merge Title + Abstract into one slide, Main Text into next, then Questions.
            # We achieve this by forcing them into the same Subchapter (so questions come at end)
            # but controlling when we flush the slide buffer.

            should_merge_with_previous = False

            if "Page 2" in main_part:
                # 1. Force common subchapter for Page 2 to ensure questions appear after the whole sequence
                sub_part = "Analysis & Overview"

                # 2. Define merging rules
                if "Abstract" in topic_title:
                    # Merge Abstract with the previous topic (Title)
                    should_merge_with_previous = True

                # Filter out Footnotes if present (often duplicate/empty)
                if "Footnotes" in topic_title:
                    logger.info("Skipping Footnotes topic")
                    continue

            # === CUSTOM LOGIC FOR PAGE 3 & 4 GROUPING (Sections 7-11) ===

            # 1. Section 7 (Main Graph) -> 1 Slide
            if "Page 3 - Main Graph" in topic_title:
                sub_part = "Main Graph (Section 7)"
                # Force immediate flush of previous content
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # 2. Section 8 (Cross-column Text) -> 1-2 Slides
            elif "Page 3 - Cross-column Text" in topic_title:
                sub_part = "Fiscal Disadvantage (Section 8)"
                # Force flush to ensure it starts fresh
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # 3. Section 9 & 11 Sequence (Page 3 Continuing -> Page 4 Continuation)
            # Grouping: Page 3 Continuing, Page 4 Continuation
            elif topic_title in [
                    "Page 3 - Continuing Text", "Page 4 - Continuation Text"
            ]:
                sub_part = "Economic & Fiscal Trends (Sections 9 & 11)"
                # These merge into the same subchapter flow

            # 4. Section 12 (Split Layout Text) -> 1 Slide
            elif "Page 4 - Split Layout Text" in topic_title:
                sub_part = "Scenarios Overview (Section 12)"
                # Force flush to ensure it starts fresh
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # 5. Boxed Section (Page 4 - Section 13) - 2-3 Slides
            elif "Page 4 - Boxed Section" in topic_title:
                sub_part = "Projection Scenarios (Box 1)"

            # === CUSTOM LOGIC FOR PAGE 5 GROUPING (Sections 15-17) ===

            # 6. Section 15 (Table 1) -> 1 Slide
            elif "Page 5 - Table 1" in topic_title:
                sub_part = "Population Table (Section 15)"
                # Force flush to ensure dedicated slide
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # 7. Section 16 (Split Layout Text) -> 1-2 Slides
            elif "Page 5 - Split Layout Text" in topic_title:
                sub_part = "Tax Revenue & Population (Section 16)"
                # Force flush
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # 8. Section 17 (Boxed Section / Box 2) -> 1-2 Slides
            elif "Page 5 - Boxed Section" in topic_title:
                sub_part = "Data Projection (Section 17)"
                # Force flush
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # === CUSTOM LOGIC FOR PAGE 6 (Scenario I Analysis) ===
            elif "Page 6 - Grid of Graphs" in topic_title:
                # This page requires specific breakdown: Before -> After -> Grants
                sub_part = "Scenario I: Fiscal Capacity Analysis"

                # Check if chapter needs to change (Standard logic)
                chapter_changed = False
                current_title_check = state.current_chapter.main_title if state.current_chapter else None

                if not state.current_chapter or current_title_check != chapter_title:
                    chapter_changed = True
                    if state.slide_buffer:
                        slide = state.flush_slide_buffer()
                        if slide and state.current_chapter:
                            state.current_chapter.add_slide(
                                slide, state.current_subchapter)
                            state.subchapter_slides[
                                state.current_subchapter].append(slide)

                    state.current_chapter_num += 1
                    state.current_chapter = Chapter(state.current_chapter_num,
                                                    str(chapter_title))
                    state.chapters.append(state.current_chapter)
                    logger.info(
                        f"Started Chapter {state.current_chapter_num}: {chapter_title}"
                    )

                state.current_subchapter = sub_part

                # INJECT CUSTOM SLIDES FOR PAGE 6
                # Slide 1: Baseline
                slide1_items = [
                    ContentItem(
                        "section_title",
                        "Scenario I: Fiscal Capacity Before Redistribution"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption":
                                    "Before Redistribution",
                                    "image_path":
                                    "images/page_6_figure_1_row1.png",
                                    "image_url":
                                    self.image_url_map.get(
                                        "images/page_6_figure_1_row1.png", "")
                                }),
                    ContentItem(
                        "paragraph",
                        "Analysis of tax revenue per capita as a percentage of the national average (Scenario I)."
                    ),
                    ContentItem(
                        "bullet",
                        "Visualizes the development of fiscal capacity before any equalization."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 1 (Before Redistribution) shows significant disparities between states."
                    ),
                    ContentItem(
                        "bullet",
                        "West, East, and City-states show distinct initial fiscal capacities."
                    ),
                    ContentItem(
                        "bullet",
                        "Legend: Light bars = 2025, Dark bars = 2070.")
                ]
                state.slide_buffer = slide1_items
                slide1 = state.flush_slide_buffer(
                    "Scenario I: Baseline Disparities")
                if slide1:
                    state.current_chapter.add_slide(slide1, sub_part)
                    state.subchapter_slides[sub_part].append(slide1)

                # Slide 2: Redistribution Effect
                slide2_items = [
                    ContentItem("section_title", "Effect of Redistribution"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption":
                                    "Effect of Redistribution",
                                    "image_path":
                                    "images/page_6_figure_1_row2.png",
                                    "image_url":
                                    self.image_url_map.get(
                                        "images/page_6_figure_1_row2.png", "")
                                }),
                    ContentItem(
                        "paragraph",
                        "The fiscal equalization system aims to align per-capita tax revenue."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 2 (After Redistribution) demonstrates a significant leveling effect."
                    ),
                    ContentItem(
                        "bullet",
                        "Gaps between rich and poor states are compressed."),
                    ContentItem(
                        "bullet",
                        "Essential mechanism for maintaining federal stability."
                    )
                ]
                state.slide_buffer = slide2_items
                slide2 = state.flush_slide_buffer(
                    "Impact of Fiscal Redistribution")
                if slide2:
                    state.current_chapter.add_slide(slide2, sub_part)
                    state.subchapter_slides[sub_part].append(slide2)

                # Slide 3: Final State & Conclusion
                slide3_items = [
                    ContentItem("section_title",
                                "Final Capacity & Conclusion"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption":
                                    "Final Capacity",
                                    "image_path":
                                    "images/page_6_figure_1_row3.png",
                                    "image_url":
                                    self.image_url_map.get(
                                        "images/page_6_figure_1_row3.png", "")
                                }),
                    ContentItem(
                        "paragraph",
                        "Supplementary federal grants provide the final layer of equalization."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 3 (After Supplementary Grants) shows near-uniform fiscal capacity."
                    ),
                    ContentItem(
                        "bullet",
                        "Conclusion: Redistribution significantly reduces disparities in financial capacity."
                    ),
                    ContentItem(
                        "bullet",
                        "This trend holds consistent across different migration variants (A, B, C)."
                    )
                ]
                state.slide_buffer = slide3_items
                slide3 = state.flush_slide_buffer(
                    "Final Fiscal Capacity & Conclusions")
                if slide3:
                    state.current_chapter.add_slide(slide3, sub_part)
                    state.subchapter_slides[sub_part].append(slide3)

                # Skip standard processing for this topic since we injected content
                continue

            # === CUSTOM LOGIC FOR PAGE 7 (Scenario II Analysis) ===
            elif "Page 7 - Grid of Graphs" in topic_title:
                # This page requires specific breakdown: Before -> After -> Grants
                sub_part = "Scenario II: Fiscal Capacity Analysis"

                # Check if chapter needs to change (Standard logic)
                chapter_changed = False
                if not state.current_chapter or state.current_chapter.main_title != main_part:
                    chapter_changed = True
                    if state.slide_buffer:
                        slide = state.flush_slide_buffer()
                        if slide and state.current_chapter:
                            state.current_chapter.add_slide(
                                slide, state.current_subchapter)
                            state.subchapter_slides[
                                state.current_subchapter].append(slide)

                    state.current_chapter_num += 1
                    state.current_chapter = Chapter(state.current_chapter_num,
                                                    main_part)
                    state.chapters.append(state.current_chapter)
                    logger.info(
                        f"Started Chapter {state.current_chapter_num}: {main_part}"
                    )

                state.current_subchapter = sub_part

                # INJECT CUSTOM SLIDES FOR PAGE 7
                # Slide 1: Baseline
                slide1_items = [
                    ContentItem(
                        "section_title",
                        "Scenario II: Fiscal Capacity Before Redistribution"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption": "Before Redistribution",
                                    "image_path":
                                    "images/page_7_figure_1_row1.png"
                                }),
                    ContentItem(
                        "paragraph",
                        "Analysis of tax revenue per capita as a percentage of the national average (Scenario II)."
                    ),
                    ContentItem(
                        "bullet",
                        "Visualizes the development of fiscal capacity before any equalization."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 1 (Before Redistribution) shows significant disparities between states."
                    ),
                    ContentItem(
                        "bullet",
                        "Scenario II assumes different migration patterns compared to Scenario I."
                    ),
                    ContentItem(
                        "bullet",
                        "Legend: Light bars = 2025, Dark bars = 2070.")
                ]
                state.slide_buffer = slide1_items
                slide1 = state.flush_slide_buffer(
                    "Scenario II: Baseline Disparities")
                if slide1:
                    state.current_chapter.add_slide(slide1, sub_part)
                    state.subchapter_slides[sub_part].append(slide1)

                # Slide 2: Redistribution Effect
                slide2_items = [
                    ContentItem("section_title", "Effect of Redistribution"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption": "Effect of Redistribution",
                                    "image_path":
                                    "images/page_7_figure_1_row2.png"
                                }),
                    ContentItem(
                        "paragraph",
                        "The fiscal equalization system aims to align per-capita tax revenue."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 2 (After Redistribution) demonstrates a significant leveling effect."
                    ),
                    ContentItem(
                        "bullet",
                        "Gaps between rich and poor states are compressed."),
                    ContentItem(
                        "bullet",
                        "Essential mechanism for maintaining federal stability."
                    )
                ]
                state.slide_buffer = slide2_items
                slide2 = state.flush_slide_buffer(
                    "Impact of Fiscal Redistribution")
                if slide2:
                    state.current_chapter.add_slide(slide2, sub_part)
                    state.subchapter_slides[sub_part].append(slide2)

                # Slide 3: Final State & Conclusion
                slide3_items = [
                    ContentItem("section_title",
                                "Final Capacity & Conclusion"),
                    ContentItem("figure",
                                "",
                                metadata={
                                    "caption": "Final Capacity",
                                    "image_path":
                                    "images/page_7_figure_1_row3.png"
                                }),
                    ContentItem(
                        "paragraph",
                        "Supplementary federal grants provide the final layer of equalization."
                    ),
                    ContentItem(
                        "bullet",
                        "Row 3 (After Supplementary Grants) shows near-uniform fiscal capacity."
                    ),
                    ContentItem(
                        "bullet",
                        "Conclusion: Redistribution significantly reduces disparities in financial capacity."
                    ),
                    ContentItem(
                        "bullet",
                        "This trend holds consistent across different migration variants."
                    )
                ]
                state.slide_buffer = slide3_items
                slide3 = state.flush_slide_buffer(
                    "Final Fiscal Capacity & Conclusions")
                if slide3:
                    state.current_chapter.add_slide(slide3, sub_part)
                    state.subchapter_slides[sub_part].append(slide3)

                # Skip standard processing for this topic since we injected content
                continue

            # === CUSTOM LOGIC FOR PAGE 8 ===
            elif "Page 8 - Table 2" in topic_title:
                sub_part = "Fiscal Capacity Variants (Table 2)"
                # Force flush to ensure dedicated slide(s) for the table
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            elif "Page 8 - Text Part 1" in topic_title:
                # Section 19: Continuation from Page 5 Section 16
                sub_part = "Tax Revenue & Population (Section 19)"
                # We treat this as a standard text section that continues the earlier theme

            elif "Page 8 - Text Part 2" in topic_title:
                # Section 20: 1-2 slides
                sub_part = "Fiscal Projections (Section 20)"
                # Force flush to start new section
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # Skip Footnotes for Pages 3, 4, 5, 8
            elif any(x in topic_title for x in [
                    "Page 3 - Footnotes", "Page 4 - Footnotes",
                    "Page 5 - Footnotes", "Page 8 - Footnotes"
            ]):
                logger.info(f"Skipping {topic_title}")
                continue

            # === CUSTOM LOGIC FOR PAGE 9 ===
            elif "Page 9 - Continuing Text" in topic_title:
                # Section 21: Continuation from Page 8 Section 20
                sub_part = "Fiscal Projections (Section 21)"
                # Merge logic handled by subchapter name matching if we used exact same name
                # But user wants "continuation of page 8 section 20"
                # Page 8 Section 20 was "Fiscal Projections (Section 20)"
                # To group them, we should use a common subchapter name or just let them flow
                # Let's use a slightly different name to indicate progression but keep theme
                # Actually, to make them truly continuous in one flow, we could use the same subchapter name
                # But "Section 21" implies a distinct part. Let's keep the name distinct but related.

            elif "Page 9 - Conclusion" in topic_title:
                # Section 22: 2-3 slides
                sub_part = "Conclusion & Outlook"
                # Force flush to ensure it starts fresh
                if state.slide_buffer:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

                # To ensure 2-3 slides, we can lower the word count threshold for this section
                # or just rely on the content being long enough.
                # Given the user's request, we'll force a split if content is substantial.
                # We can't easily force "2-3 slides" without knowing content length,
                # but we can set a flag or just rely on the Smart Fit Logic below
                # which splits based on word count.
                # If the conclusion is short, we might need to "stretch" it or it will be just 1 slide.
                # Let's assume the text is sufficient (it looks long in the PDF screenshot).
                # We will ensure the Smart Fit Logic is triggered by not merging.
                pass  # Logic continues below

            # Check if we need to start a new Chapter
            chapter_changed = False
            # Check against dynamic chapter title instead of raw main_part
            current_title_check = state.current_chapter.main_title if state.current_chapter else None

            if not state.current_chapter or current_title_check != chapter_title:
                chapter_changed = True
                # Flush previous slide buffer
                if state.slide_buffer:
                    slide = state.flush_slide_buffer()
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

                # === QUESTIONNAIRE GENERATION LOGIC ===
                # Check if we should generate a questionnaire for the PREVIOUS batch of chapters
                # We do this before starting the new chapter
                if self.enable_questionnaire and state.current_chapter and state.current_chapter.chapter_num is not None:
                    state.chapters_since_last_questionnaire += 1
                    if state.chapters_since_last_questionnaire >= self.questionnaire_frequency:
                        logger.info(
                            f"Generating questionnaire after {state.chapters_since_last_questionnaire} chapters..."
                        )
                        # Get the last N chapters
                        relevant_chapters = state.chapters[
                            -state.chapters_since_last_questionnaire:]
                        q_slides = self.generate_questionnaire_slides(
                            relevant_chapters)

                        if q_slides:
                            # Append to the LAST chapter (the one just finished)
                            target_chapter = state.chapters[-1]
                            for slide in q_slides:
                                target_chapter.add_slide(
                                    slide, "Review & Assessment")
                                state.subchapter_slides[
                                    "Review & Assessment"].append(slide)
                            logger.info(
                                f"Added {len(q_slides)} questionnaire slides to Chapter {target_chapter.chapter_num}"
                            )

                        state.chapters_since_last_questionnaire = 0

                state.current_chapter_num += 1
                state.current_chapter = Chapter(state.current_chapter_num,
                                                str(chapter_title))
                state.chapters.append(state.current_chapter)
                logger.info(
                    f"Started Chapter {state.current_chapter_num}: {chapter_title}"
                )

            # Check if Subchapter changed
            # Note: state.current_subchapter holds the OLD subchapter value here
            subchapter_changed = (state.current_subchapter != sub_part.strip())

            # FLUSH DECISION:
            # We flush the buffer (containing previous topic's content) if:
            # 1. Subchapter changed (standard grouping)
            # 2. OR We are NOT merging with previous topic AND buffer is not empty (standard topic separation)
            # Note: If chapter changed, we already flushed above.

            if not chapter_changed and state.slide_buffer:
                if subchapter_changed or not should_merge_with_previous:
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

            # Set current subchapter
            state.current_subchapter = sub_part.strip()
            logger.info(f"  Processing Subchapter: {state.current_subchapter}")

            # === SMART FIT LOGIC ===
            # Initialize thresholds with defaults
            current_max_words = MAX_SLIDE_WORDS
            current_optimal_words = OPTIMAL_SLIDE_WORDS

            # Custom thresholds for specific sections
            if "Page 9 - Conclusion" in topic_title:
                # Force splitting into 2-3 slides by lowering capacity
                current_max_words = 150
                current_optimal_words = 100
                logger.info(
                    f"Applied lower word limits for {topic_title} to force slide splitting"
                )

            # 1. Pre-process text content to calculate total size
            temp_text_items = []
            temp_text_words = 0

            paragraphs = summary_text.split("\n\n")
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue

                if p.startswith("- ") or p.startswith("* "):
                    lines = p.split('\n')
                    for line in lines:
                        clean_line = line.strip().lstrip("- *").strip()
                        if clean_line:
                            item = ContentItem("bullet", clean_line)
                            temp_text_items.append(item)
                            temp_text_words += item.word_count()
                else:
                    # Regular paragraph - check for massive paragraphs
                    chunks = self.split_paragraph_into_chunks(
                        p, current_max_words, topic_title)
                    for chunk in chunks:
                        item = ContentItem("paragraph", chunk)
                        temp_text_items.append(item)
                        temp_text_words += item.word_count()

            # 2. Pre-process visual insights (Textual)
            temp_visual_items = []
            visual_insights = topic_data.get("key_insights", [])
            for insight in visual_insights:
                item = ContentItem("bullet", insight)
                temp_visual_items.append(item)

            # 2b. Pre-process Actual Images and Tables (from detailed analysis)
            temp_image_items = []
            detailed_visuals = topic_data.get("detailed_visual_analysis", [])
            for vis in detailed_visuals:
                # Handle Tables
                if vis.get("type") == "table":
                    img_path = vis.get("image_path")
                    img_url = ""
                    if img_path:
                        img_url = self.image_url_map.get(
                            img_path) or self.image_url_map.get(
                                os.path.basename(img_path))

                    item = ContentItem("table",
                                       vis.get("content", ""),
                                       metadata={
                                           "caption":
                                           vis.get("analysis", "Table"),
                                           "table_data":
                                           vis.get("table_data"),
                                           "table_headers":
                                           vis.get("table_headers"),
                                           "image_path":
                                           img_path,
                                           "image_url":
                                           img_url
                                       })
                    temp_image_items.append(item)
                    continue

                # Handle Images/Figures
                img_path = vis.get("image_path")
                # Resolve URL from map
                img_url = ""
                if img_path:
                    img_url = self.image_url_map.get(
                        img_path) or self.image_url_map.get(
                            os.path.basename(img_path))
                    if not img_url:
                        # Try finding any key that ends with the basename
                        basename = os.path.basename(img_path)
                        for k, v in self.image_url_map.items():
                            if k.endswith(basename):
                                img_url = v
                                break

                if img_url:
                    item = ContentItem(
                        "figure",
                        "",  # Content empty, uses metadata
                        metadata={
                            "caption": vis.get("type", "Figure"),
                            "description": vis.get("analysis", ""),
                            "image_path": img_path,
                            "image_url": img_url
                        })
                    temp_image_items.append(item)

            # Calculate visual weight (approximate)
            # Give images a heavy weight (100) to encourage them to be on their own or with little text
            visual_weight = sum(item.word_count() + 20
                                for item in temp_visual_items)
            image_weight = len(temp_image_items) * 150

            total_content_weight = temp_text_words + visual_weight + image_weight

            # 3. Decision Logic

            # Case A: Massive Content (> current_max_words)
            # We must split.
            if total_content_weight > current_max_words:
                # Add text items one by one with eager flushing
                for item in temp_text_items:
                    state.slide_buffer.append(item)
                    state.buffer_word_count += item.word_count()
                    if state.buffer_word_count >= current_optimal_words:
                        title = self.generate_slide_title(state.slide_buffer)
                        slide = state.flush_slide_buffer(title)
                        if slide and state.current_chapter:
                            state.current_chapter.add_slide(
                                slide, state.current_subchapter)
                            state.subchapter_slides[
                                state.current_subchapter].append(slide)

                # Add images (force explicit slides for images if text was already heavy)
                for item in temp_image_items:
                    # If we have pending text, maybe flush it first?
                    if state.slide_buffer and state.buffer_word_count > 50:
                        title = self.generate_slide_title(state.slide_buffer)
                        slide = state.flush_slide_buffer(title)
                        if slide and state.current_chapter:
                            state.current_chapter.add_slide(
                                slide, state.current_subchapter)
                            state.subchapter_slides[
                                state.current_subchapter].append(slide)

                    state.slide_buffer.append(item)
                    state.buffer_word_count += 100  # Artificial weight

                    # Flush immediately to showcase the image
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

                # Then add textual visuals (bullet points)
                for item in temp_visual_items:
                    state.slide_buffer.append(item)
                    state.buffer_word_count += item.word_count() + 20
                    if state.buffer_word_count >= current_optimal_words:
                        title = self.generate_slide_title(state.slide_buffer)
                        slide = state.flush_slide_buffer(title)
                        if slide and state.current_chapter:
                            state.current_chapter.add_slide(
                                slide, state.current_subchapter)
                            state.subchapter_slides[
                                state.current_subchapter].append(slide)

            # Case B: Substantial Text + Visuals
            # Text fits on one slide (< MAX), but combined it might be crowded.
            # OR Text is substantial (> OPTIMAL) and we have visuals -> Prefer splitting to give visuals space.
            elif (temp_text_words > current_optimal_words and
                  (temp_visual_items or temp_image_items)) or (
                      total_content_weight > current_max_words):
                # 1. Flush Text Slide
                state.slide_buffer.extend(temp_text_items)
                title = self.generate_slide_title(state.slide_buffer)
                slide = state.flush_slide_buffer(title)
                if slide and state.current_chapter:
                    state.current_chapter.add_slide(slide,
                                                    state.current_subchapter)
                    state.subchapter_slides[state.current_subchapter].append(
                        slide)

                # 2. Add Images
                if temp_image_items:
                    state.slide_buffer.extend(temp_image_items)
                    # Flush images on their own slide if possible
                    title = self.generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(
                            slide, state.current_subchapter)
                        state.subchapter_slides[
                            state.current_subchapter].append(slide)

                # 3. Add Textual Visuals (will be flushed at start of next loop or end)
                state.slide_buffer.extend(temp_visual_items)
                state.buffer_word_count += visual_weight

            # Case C: Smart Fit (Small/Medium Text + Visuals fit together)
            else:
                state.slide_buffer.extend(temp_text_items)
                state.slide_buffer.extend(temp_visual_items)
                state.slide_buffer.extend(
                    temp_image_items)  # Add images at end
                state.buffer_word_count += total_content_weight

        # Flush remaining buffer at end of all topics
        if state.slide_buffer:
            title = self.generate_slide_title(state.slide_buffer)
            slide = state.flush_slide_buffer(title)
            if slide and state.current_chapter:
                state.current_chapter.add_slide(slide,
                                                state.current_subchapter)
                state.subchapter_slides[state.current_subchapter].append(slide)

        # === FINAL QUESTIONNAIRE CHECK ===
        # Generate questionnaire for any remaining chapters
        if self.enable_questionnaire and state.chapters_since_last_questionnaire > 0 and state.current_chapter:
            logger.info(
                f"Generating final questionnaire for last {state.chapters_since_last_questionnaire} chapters..."
            )
            relevant_chapters = state.chapters[
                -state.chapters_since_last_questionnaire:]
            q_slides = self.generate_questionnaire_slides(relevant_chapters)

            if q_slides:
                target_chapter = state.chapters[-1]
                for slide in q_slides:
                    target_chapter.add_slide(slide, "Review & Assessment")
                    state.subchapter_slides["Review & Assessment"].append(
                        slide)
                logger.info(
                    f"Added {len(q_slides)} questionnaire slides to Chapter {target_chapter.chapter_num}"
                )

    def generate(self,
                 input_file: Optional[str] = None,
                 output_file: Optional[str] = None,
                 save_json: bool = True,
                 input_data: Optional[Dict] = None,
                 image_url_map: Optional[Dict[str, str]] = None) -> List[Dict]:
        """
        Main execution method for generating slides.
        Can accept either input_file path or input_data dictionary.
        Returns the generated slides data structure.
        """
        self.image_url_map = image_url_map or {}
        logger.info(
            f"Starting slide generation. Input: {input_file or 'Direct Data'}")

        # === LOAD AND PARSE DOCUMENT ===
        doc = {}
        if input_data:
            doc = input_data
        elif input_file:
            try:
                with open(input_file, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parse error: {e.msg}. Attempting recovery...")
                with open(input_file, "r", encoding="utf-8") as f:
                    content = f.read()

                content = self.remove_comments_safe(content)

                try:
                    doc = json.loads(content)
                    logger.info("JSON recovered successfully.")
                except json.JSONDecodeError:
                    logger.error(
                        "Could not recover JSON. Trying strict=False.")
                    try:
                        doc = json.loads(content, strict=False)
                    except Exception as final_e:
                        logger.error(f"Fatal JSON error: {final_e}")
                        raise
        else:
            raise ValueError(
                "Either input_file or input_data must be provided")

        # === INPUT PROCESSING ===
        state = ProcessingState()

        if "topic_summaries" in doc:
            self._process_summary_input(doc["topic_summaries"], state)

        elif "pages" in doc:
            pages = doc.get("pages", [])
            logger.info(f"Loaded {len(pages)} pages")

            # === FIGURE/TABLE METADATA INDEX ===
            media_index = {}
            for page in pages:
                for el in page.get("elements", []):
                    if el.get("type") == "figure":
                        fig_id = el.get("id", "unknown")
                        ctx = el.get("image_context", {})

                        caption, description = self.extract_clean_figure_data(
                            ctx)

                        media_index[fig_id] = {
                            "page": page["page_number"],
                            "caption": caption,
                            "description": description,
                            "chart_type": ctx.get("chart_type", "figure")
                        }

            # === INTELLIGENT CHUNKING ALGORITHM ===
            logger.info("Chunking content into slides...")

            for page in pages:
                for element in page.get("elements", []):
                    el_type = element.get("type")
                    content = element.get("content", "").strip()

                    # === SKIP NON-CONTENT ELEMENTS ===
                    if el_type in SKIP_ELEMENT_TYPES:
                        continue

                    # === CHAPTER DETECTION ===
                    if el_type == "title" and content:
                        # Flush previous section before starting new chapter
                        if state.slide_buffer and state.current_chapter:
                            slide = state.flush_slide_buffer()
                            if slide:
                                state.current_chapter.add_slide(
                                    slide, state.current_subchapter)
                                state.subchapter_slides[
                                    state.current_subchapter].append(slide)

                        state.current_chapter_num += 1
                        main_title, subtitle = self.split_title_at_colon(
                            content)
                        state.current_chapter = Chapter(
                            state.current_chapter_num, main_title, subtitle)
                        state.chapters.append(state.current_chapter)
                        logger.info(
                            f"Chapter {state.current_chapter_num}: {main_title}"
                        )

                    # === SUBCHAPTER DETECTION ===
                    elif el_type == "section_title" and content:
                        if content in SKIP_SECTION_TITLES:
                            continue

                        if state.slide_buffer and state.current_chapter:
                            title = self.generate_slide_title(
                                state.slide_buffer)
                            slide = state.flush_slide_buffer()
                            if slide:
                                state.current_chapter.add_slide(
                                    slide, state.current_subchapter)
                                state.subchapter_slides[
                                    state.current_subchapter].append(slide)

                        state.current_subchapter = content
                        state.slide_buffer = []
                        state.buffer_word_count = 0

                    # === CONTENT COLLECTION ===
                    elif el_type == "paragraph" and content:
                        content_preview = content.lower()[:100]
                        if any(keyword in content_preview
                               for keyword in SKIP_KEYWORDS):
                            continue

                        chunks = self.split_paragraph_into_chunks(
                            content, MAX_SLIDE_WORDS)
                        for chunk in chunks:
                            item = ContentItem("paragraph", chunk)
                            state.slide_buffer.append(item)
                            state.buffer_word_count += item.word_count()

                            if state.buffer_word_count >= OPTIMAL_SLIDE_WORDS:
                                title = self.generate_slide_title(
                                    state.slide_buffer)
                                slide = state.flush_slide_buffer(title)
                                if slide and state.current_chapter:
                                    state.current_chapter.add_slide(
                                        slide, state.current_subchapter)
                                    state.subchapter_slides[
                                        state.current_subchapter].append(slide)

                    elif el_type == "bullet_point" and element.get(
                            "bullet_items"):
                        for bullet_text in element.get("bullet_items", []):
                            if bullet_text.strip():
                                item = ContentItem("bullet",
                                                   bullet_text.strip())
                                state.slide_buffer.append(item)
                                state.buffer_word_count += item.word_count()

                        bullet_count = sum(1 for i in state.slide_buffer
                                           if i.type == "bullet")
                        if bullet_count >= MAX_BULLETS_PER_SLIDE:
                            title = self.generate_slide_title(
                                state.slide_buffer)
                            slide = state.flush_slide_buffer(title)
                            if slide and state.current_chapter:
                                state.current_chapter.add_slide(
                                    slide, state.current_subchapter)
                                state.subchapter_slides[
                                    state.current_subchapter].append(slide)
                            state.buffer_word_count = 0

                    # === FIGURE/TABLE HANDLING ===
                    elif el_type in ("figure", "table"):
                        item = None
                        weight = 0

                        if el_type == "figure":
                            fig_id = element.get("id")
                            if fig_id in media_index:
                                media = media_index[fig_id]
                                item = ContentItem("figure",
                                                   media["caption"],
                                                   metadata=media)
                                weight = FIGURE_WEIGHT
                        elif el_type == "table":
                            item = ContentItem("table",
                                               "Table data",
                                               metadata={
                                                   "caption":
                                                   content or "Data Table",
                                                   "table_data":
                                                   element.get("table_data"),
                                                   "table_headers":
                                                   element.get("table_headers")
                                               })
                            weight = TABLE_WEIGHT

                        if item:
                            if state.buffer_word_count + weight > MAX_SLIDE_WORDS:
                                if state.slide_buffer:
                                    title = self.generate_slide_title(
                                        state.slide_buffer)
                                    slide = state.flush_slide_buffer(title)
                                    if slide and state.current_chapter:
                                        state.current_chapter.add_slide(
                                            slide, state.current_subchapter)
                                        state.subchapter_slides[
                                            state.current_subchapter].append(
                                                slide)

                            state.slide_buffer.append(item)
                            state.buffer_word_count += weight

                            if state.buffer_word_count >= OPTIMAL_SLIDE_WORDS * 1.5:
                                title = self.generate_slide_title(
                                    state.slide_buffer)
                                slide = state.flush_slide_buffer(title)
                                if slide and state.current_chapter:
                                    state.current_chapter.add_slide(
                                        slide, state.current_subchapter)
                                    state.subchapter_slides[
                                        state.current_subchapter].append(slide)

            # Flush remaining buffer
            if state.slide_buffer and state.current_chapter:
                title = self.generate_slide_title(state.slide_buffer)
                slide = state.flush_slide_buffer(title)
                if slide:
                    state.current_chapter.add_slide(slide,
                                                    state.current_subchapter)
                    state.subchapter_slides[state.current_subchapter].append(
                        slide)
        else:
            logger.warning(
                "Unknown input format: neither 'pages' nor 'topic_summaries' found."
            )

        # === GENERATE LEARN CONTROLS ===
        logger.info("Generating learn control questions...")
        for chapter in state.chapters:
            # Skip learn controls for Introduction chapter (Chapter 1)
            # HARDCODED RULE: No questions for Chapter 1
            if chapter.chapter_num == 1 or "Introduction" in chapter.main_title:
                logger.info(
                    f"Skipping learn controls for Chapter {chapter.chapter_num}: {chapter.main_title} (Introduction)"
                )
                continue

            for subchapter_title, slides in chapter.subchapters.items():
                all_content = []
                for slide in slides:
                    all_content.extend(slide.items)

                if all_content:
                    questions = self.generate_learn_controls(
                        subchapter_title, all_content)
                    chapter.learn_controls[subchapter_title] = questions

        # === RENDER TO MARKDOWN ===
        logger.info("Rendering presentation...")
        output_lines = []
        output_lines.append("# Presentation Slide Deck\n")
        output_lines.append("_Generated from extracted academic document_\n")
        output_lines.append("---\n")

        for chapter in state.chapters:
            output_lines.append(chapter.render_markdown())

        presentation_text = "\n".join(output_lines)

        # === SAVE OUTPUT ===
        if output_file:
            Path(output_file).parent.mkdir(exist_ok=True, parents=True)
            Path(output_file).write_text(presentation_text, encoding="utf-8")
            logger.info(f"Presentation saved to: {output_file}")

        # Statistics
        total_slides = sum(len(ch.slides) for ch in state.chapters)
        total_subchapters = sum(len(ch.subchapters) for ch in state.chapters)
        slides_with_questions = sum(
            len(ch.learn_controls) for ch in state.chapters)

        logger.info(f"Total chapters: {len(state.chapters)}")
        logger.info(f"Total slides: {total_slides}")
        logger.info(f"Total subchapters: {total_subchapters}")
        logger.info(f"Slides with learn controls: {slides_with_questions}")

        # === EXPORT JSON BACKUP ===
        # Always generate slides_data as it is the return value
        slides_data = []
        intro_data = []

        for chapter in state.chapters:
            for slide in chapter.slides:
                # Find subchapter
                slide_subchapter = "Unknown"
                for sub, slides in chapter.subchapters.items():
                    if slide in slides:
                        slide_subchapter = sub
                        break

                slide_dict = {
                    "chapter":
                    chapter.chapter_num,
                    "subchapter":
                    slide_subchapter,
                    "chapter_main_title":
                    chapter.main_title,
                    "chapter_subtitle":
                    chapter.subtitle,
                    "slide_number":
                    slide.slide_num,
                    "slide_title":
                    slide.title,
                    "content": [{
                        "type": item.type,
                        "text": item.content,
                        "metadata": item.metadata
                    } for item in slide.items]
                }

                if chapter.chapter_num is None:
                    intro_data.append(slide_dict)
                else:
                    slides_data.append(slide_dict)

        json_output = {
            "metadata": {
                "total_chapters": len(state.chapters),
                "total_slides": total_slides,
                "total_subchapters": total_subchapters,
                "source": input_file
            },
            "introduction":
            intro_data,
            "slides":
            slides_data,
            "chapters": [{
                "chapter_num": ch.chapter_num,
                "main_title": ch.main_title,
                "subtitle": ch.subtitle,
                "slide_count": len(ch.slides),
                "subchapters": list(ch.subchapters.keys()),
                "learn_controls": {
                    k: v
                    for k, v in ch.learn_controls.items()
                }
            } for ch in state.chapters]
        }

        if save_json and output_file:
            json_path = output_file.replace(".md", ".json")
            Path(json_path).write_text(json.dumps(json_output,
                                                  indent=2,
                                                  ensure_ascii=False),
                                       encoding="utf-8")
            logger.info(f"JSON structure saved: {json_path}")

        return slides_data


if __name__ == "__main__":
    import argparse
    import sys
    import os

    # Configure logging for standalone run
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Resolve default paths from settings
    default_input = os.path.join(settings.summarization_output_dir,
                                 "summary_result.json")
    default_output = settings.generation_output_path

    parser = argparse.ArgumentParser(
        description="Generate presentation slides from a summary JSON file.")
    parser.add_argument(
        "input_file",
        nargs='?',
        default=default_input,
        help=f"Path to the input summary JSON file (default: {default_input})")
    parser.add_argument(
        "output_file",
        nargs='?',
        default=default_output,
        help=f"Path to the output Markdown file (default: {default_output})")
    parser.add_argument("--model",
                        default="llama3.2",
                        help="Ollama model to use (default: llama3.2)")

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")

    # Chained execution logic
    if not os.path.exists(args.input_file):
        # Only trigger chain if using default path
        is_default_target = (os.path.abspath(
            args.input_file) == os.path.abspath(default_input))

        if is_default_target:
            logger.info(
                f"Input file not found at {args.input_file}. Triggering summarization..."
            )
            try:
                from features.summarization import run_summarization
                run_summarization()
            except Exception as e:
                logger.error(f"Failed to run summarization: {e}")
                sys.exit(1)

            # Verify existence after run
            if not os.path.exists(args.input_file):
                logger.error(
                    "Summarization completed but input file is still missing.")
                sys.exit(1)
        else:
            logger.error(f"Input file not found: {args.input_file}")
            sys.exit(1)

    try:
        generator = SlideGenerator(model=args.model)
        generator.generate(args.input_file, args.output_file)
        logger.info("Generation completed successfully.")
    except Exception as e:
        logger.error(f"Generation failed: {str(e)}", exc_info=True)
        sys.exit(1)

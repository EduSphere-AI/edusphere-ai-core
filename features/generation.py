"""
SLIDE DECK GENERATOR WITH INTELLIGENT CHUNKING

This script organizes extracted academic content into presentation slides with:
1. Content-aware chunking (each chunk = 1 slide, sized appropriately)
2. Chapter/subchapter structure preservation
3. Figure/table consideration in chunk sizing
4. Learn control questions (3-4 per subchapter) for reflection
"""

import json
import hashlib
from pathlib import Path
from collections import defaultdict
import re

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# === PRE-COMPILED REGEX PATTERNS ===
RE_CHUNK_BOUNDARY = re.compile(r'\[CHUNK \d+\]')
RE_NUMBERED_LINE = re.compile(r'^\d+\.\s+(.+)$')
RE_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
RE_JSON_COMMENTS = re.compile(r',\s*\([^)]*\)')

# === CONFIG ===
MODEL = "llama3.2"
INPUT_FILE = r"D:\schmalkalden uni\third semester\TADS\output\extraction_result.json"
OUTPUT_FILE = "slides/presentation.md"
CACHE_FILE = "slides/.ollama_cache.json"

# === CONSTANTS ===
OPTIMAL_SLIDE_WORDS = 120  # Reduced for better readability
MAX_SLIDE_WORDS = 250      # Hard limit
MIN_SLIDE_WORDS = 30       # Minimum before considering slide complete
MAX_BULLETS_PER_SLIDE = 8  # Reduced to avoid overcrowding
MAX_PARAGRAPHS_PER_SLIDE = 3

# Element weights (equivalent words)
FIGURE_WEIGHT = 100
TABLE_WEIGHT = 100

# Elements to skip (non-educational content)
SKIP_ELEMENT_TYPES = {"author", "footer", "footnote", "caption", "header"}
SKIP_SECTION_TITLES = {"FROM THE AUTHORS", "MEDIA", "LEGAL AND EDITORIAL DETAILS"}
SKIP_KEYWORDS = {"phone:", "fax:", "publishers", "editors", "editorial", "volume"}

# === CACHING UTILITIES ===
class OllamaCache:
    def __init__(self, cache_file):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_cache(self):
        self.cache_file.parent.mkdir(exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, indent=2), encoding='utf-8')

    def get(self, prompt):
        key = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        return self.cache.get(key)

    def set(self, prompt, response):
        key = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        self.cache[key] = response
        self._save_cache()

ollama_cache = OllamaCache(CACHE_FILE)

# === HELPER FUNCTIONS ===
def remove_comments_safe(content: str) -> str:
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

def call_ollama(prompt: str, fallback_value: str = None) -> str:
    """
    Safely call Ollama with consistent error handling and caching.
    Returns fallback_value if Ollama unavailable or call fails.
    """
    if not OLLAMA_AVAILABLE:
        return fallback_value or ""
    
    # Check cache first
    cached_response = ollama_cache.get(prompt)
    if cached_response:
        return cached_response

    try:
        response = ollama.generate(model=MODEL, prompt=prompt, stream=False)
        result = response.get("response", "").strip()
        # Cache the successful response
        if result:
            ollama_cache.set(prompt, result)
        return result
    except Exception as e:
        return fallback_value or ""
def generate_slide_title_ollama(items: list) -> str:
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
    
    title = call_ollama(prompt, fallback_value=None)
    if title:
        # Clean up the title
        title = title.replace('\n', '').strip('"').strip()
        if len(title) > 5 and len(title) < 100:
            return title
    
    # Fallback: extract keywords
    keywords = []
    for item in items: 
        if item.type in ("paragraph", "bullet"):
            words = [w for w in item.content.split() if len(w) > 5 and not w.endswith(",")]
            keywords.extend(words[:3])
    
    if keywords:
        title = " ".join(keywords[:3])
        return title if len(title) > 10 else "Key Concepts"
    return "Key Concept"

def generate_slide_title(items: list) -> str:
    """
    Generate a short, meaningful slide title from content items using Ollama.
    """
    return generate_slide_title_ollama(items)

def split_title_at_colon(title: str) -> tuple:
    """
    Split a title at colon: before colon is main title, after is subtitle.
    
    Returns:
        Tuple of (main_title, subtitle)
    """
    if ":" in title:
        parts = title.split(":", 1)
        return parts[0].strip(), parts[1].strip()
    return title.strip(), ""

def extract_chapter_title_from_content(items: list) -> str:
    """
    Extract a meaningful chapter title from the first paragraph.
    """
    for item in items:
        if item.type == "paragraph" and len(item.content) > 50:
            # Get first sentence
            sentences = item.content.split(".")
            title = sentences[0].strip()
            if len(title) > 80:
                title = title[:80].rsplit(" ", 1)[0]
            return title
    return "Chapter Content"
    

def extract_clean_figure_data(ctx: dict) -> tuple:
    """
    Extract and enhance caption and description from figure metadata using Ollama.
    
    Returns:
        Tuple of (caption, description)
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
            desc = desc_obj.get("description", desc_obj.get("key_insights", ""))
        except:
            desc = "See document for detailed figure information."
    
    # Use Ollama to enhance description if it exists
    if desc and len(desc) > 20:
        prompt = f"""Rewrite this figure/chart description to be clear, concise, and pedagogically useful in an academic slide. 
Keep it to 2-3 sentences max. Remove jargon where possible.

Description:
{desc[:300]}

Clear description:"""
        # Pass fallback_value as None to handle missing Ollama gracefully inside call_ollama
        enhanced_desc = call_ollama(prompt, fallback_value=None)
        if enhanced_desc and len(enhanced_desc) > 10:
            desc = enhanced_desc
    
    # Limit description to reasonable length
    if len(desc) > 400:
        desc = desc[:397] + "..."
    
    return str(caption)[:100], str(desc)

# === OLLAMA INTEGRATION ===
def generate_learn_controls(subchapter_title: str, slide_contents: list) -> list:
    """
    Generate 4 open-ended learning control questions using Ollama at different cognitive levels.
    Questions test: comprehension, analysis, application, and critical thinking.
    """
    # Combine all content for context
    # Optimize: Use generator expression instead of list comprehension for memory efficiency
    all_text_parts = (
        item.content for item in slide_contents 
        if item.type in ("paragraph", "bullet")
    )
    all_text = " ".join(all_text_parts)
    
    if not all_text.strip():
        return []
    
    prompt = f"""You are an expert instructional designer creating assessment questions. Given the following academic content 
from a section titled "{subchapter_title}", generate exactly 4 open-ended reflection questions that test different cognitive levels:

1. One DEFINITION/COMPREHENSION question: Testing understanding of key concepts
2. One ANALYSIS/EXPLANATION question: Testing how concepts relate to each other
3. One APPLICATION/EVALUATION question: Testing real-world or practical implications
4. One CRITICAL THINKING question: Asking learners to question or extend the content

All questions must:
- Be directly based on the provided content
- Be open-ended (not yes/no)
- Be appropriate for academic learners
- Be clear and answerable
- Not contain the answer within the question 

Content:
{all_text[:2500]}

Generate questions in this exact format (one per line, numbered 1-4):
1. [Definition/Comprehension question]
2. [Analysis/Explanation question]
3. [Application/Evaluation question]
4. [Critical Thinking question]

Respond ONLY with the numbered questions, nothing else:"""

    text = call_ollama(prompt, fallback_value=None)
    if text:
        # Parse numbered questions
        questions = []
        for line in text.split('\n'):
            match = RE_NUMBERED_LINE.match(line.strip())
            if match:
                q = match.group(1).strip()
                if len(q) > 10:  # Ensure question is substantive
                    questions.append(q)
        
        if questions:
            return questions[:4]
    
    # Fallback if Ollama unavailable
    return [
        f"What are the key definitions and concepts presented in {subchapter_title}?",
        f"How do the different elements discussed in {subchapter_title} relate to and support each other?",
        f"What are the practical or real-world applications of the information in {subchapter_title}?",
        f"What are the limitations or assumptions underlying the content in {subchapter_title}? What further questions does this raise?"
    ]

# === DOCUMENT STRUCTURE CLASSES ===
class ContentItem:
    """Represents a single content element (paragraph, bullet, figure, etc.)"""
    
    def __init__(self, item_type: str, content: str, metadata: dict = None):
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
    
    def __init__(self, chapter_num: int, slide_num: int, title: str, items: list):
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
        lines.append(f"### Slide {self.chapter_num}.{self.slide_num}: {self.title}\n")
        
        for item in self.items:
            if item.type == "paragraph":
                lines.append(f"{item.content}\n")
            elif item.type == "bullet":
                lines.append(f"- {item.content}")
            elif item.type == "figure":
                caption = item.metadata.get("caption", "Figure")
                description = item.metadata.get("description", "")
                lines.append(f"\n**Figure:** {caption}")
                if description:
                    lines.append(f"**Description:** {description}\n")
            elif item.type == "table":
                caption = item.metadata.get("caption", "Table")
                lines.append(f"\n**Table:** {caption}\n")
        
        lines.append("\n---\n")
        return "\n".join(lines)


def split_paragraph_into_chunks_ollama(text: str, max_words: int) -> list:
    """
    Use Ollama to intelligently split a paragraph at logical concept boundaries.
    Ensures each chunk is pedagogically complete and covers one concept.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text.strip()]
    
    # For very long text, use Ollama to identify chunk boundaries
    num_chunks = (len(words) // max_words) + 1
    prompt = f"""You are an instructional design expert. Split the following academic text into {num_chunks} logical chunks 
where each chunk covers ONE concept and is approximately {max_words} words. 
Each chunk should be pedagogically complete and understandable independently.
Maintain the original text exactly—do not paraphrase or summarize.

Respond in this format:
[CHUNK 1]
Text here...
[CHUNK 2]
Text here...

Do NOT add explanation or comments, ONLY the chunked text:

{text}"""
    
    result_text = call_ollama(prompt, fallback_value=None)
    if result_text:
        # Parse chunks from response
        chunks = RE_CHUNK_BOUNDARY.split(result_text)
        chunks = [c.strip() for c in chunks if c.strip()]
        if chunks:
            return chunks
    
    # Fallback to simple sentence-based chunking
    return _fallback_chunking(text, max_words)

def _fallback_chunking(text: str, max_words: int) -> list:
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
                    chunk = " ".join(s_words[i:i+max_words]).strip()
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

def split_paragraph_into_chunks(text: str, max_words: int) -> list:
    """Split a long paragraph text into chunks using Ollama for intelligent concept-based boundaries."""
    return split_paragraph_into_chunks_ollama(text, max_words)

class Chapter:
    """Represents a chapter with multiple slides and subchapters"""
    
    def __init__(self, chapter_num: int, main_title: str, subtitle: str = ""):
        self.chapter_num = chapter_num
        self.main_title = main_title  # Before colon
        self.subtitle = subtitle      # After colon
        self.slides = []
        self.subchapters = defaultdict(list)  # subchapter_title -> [slides]
        self.learn_controls = defaultdict(list)  # subchapter_title -> [questions]
    
    def add_slide(self, slide: Slide, subchapter: str = None):
        """Add slide to chapter and optionally track subchapter"""
        self.slides.append(slide)
        
        # Ensure every slide belongs to a subchapter bucket
        key = subchapter if subchapter else "Introduction"
        self.subchapters[key].append(slide)
    
    def render_markdown(self) -> str:
        """Render entire chapter with learn controls at the end of each subchapter"""
        lines = []
        # Show main title first
        lines.append(f"\n## Chapter {self.chapter_num}: {self.main_title}\n")
        
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
                for j, question in enumerate(self.learn_controls[subchapter_title], 1):
                    lines.append(f"{j}. {question}\n")
                lines.append("\n---\n")
        
        return "\n".join(lines)

# === LOAD AND PARSE DOCUMENT ===
print("[INFO] Loading extraction result...")
try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        doc = json.load(f)
except json.JSONDecodeError as e:
    # Try to fix common JSON corruption issues (comments, trailing commas)
    print(f"[WARN] JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Remove inline comments like (comment text) safely
    content = remove_comments_safe(content)
    
    try:
        doc = json.loads(content)
        print("[OK] JSON recovered after removing corrupted comments")
    except json.JSONDecodeError:
        print("[ERROR] Could not recover JSON. Trying with strict=False...")
        doc = json.loads(content, strict=False)

pages = doc.get("pages", [])
print(f"[INFO] Loaded {len(pages)} pages")

# === FIGURE/TABLE METADATA INDEX ===
media_index = {}
for page in pages:
    for el in page.get("elements", []):
        if el.get("type") == "figure":
            fig_id = el.get("id", "unknown")
            ctx = el.get("image_context", {})
            
            caption, description = extract_clean_figure_data(ctx)
            
            media_index[fig_id] = {
                "page": page["page_number"],
                "caption": caption,
                "description": description,
                "chart_type": ctx.get("chart_type", "figure")
            }

# === INTELLIGENT CHUNKING ALGORITHM ===
print("[INFO] Chunking content into slides...")

class ProcessingState:
    """Encapsulates mutable state during document processing"""
    def __init__(self):
        self.chapters = []
        self.current_chapter = None
        self.current_chapter_num = 0
        self.current_subchapter = None
        self.slide_buffer = []
        self.buffer_word_count = 0
        self.subchapter_slides = defaultdict(list)
    
    def flush_slide_buffer(self, title_override: str = None) -> Slide:
        """Convert buffer contents to a slide"""
        if not self.slide_buffer:
            return None
        
        # Generate title from content if not provided
        if not title_override:
            # Extract from first section_title or generate from content
            section_titles = [item.content for item in self.slide_buffer if item.type == "section_title"]
            title_override = section_titles[0] if section_titles else "Content"
        
        slide = Slide(self.current_chapter_num, len(self.current_chapter.slides) + 1 if self.current_chapter else 1, 
                      title_override, self.slide_buffer.copy())
        
        self.slide_buffer.clear()
        self.buffer_word_count = 0
        return slide

state = ProcessingState()

# Track subchapter sequences for learn controls
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
                    state.current_chapter.add_slide(slide, state.current_subchapter)
                    state.subchapter_slides[state.current_subchapter].append(slide)
            
            state.current_chapter_num += 1
            main_title, subtitle = split_title_at_colon(content)
            state.current_chapter = Chapter(state.current_chapter_num, main_title, subtitle)
            state.chapters.append(state.current_chapter)
            print("[INFO] Chapter {}: {} {}".format(state.current_chapter_num, main_title, 
                                                     "- " + subtitle if subtitle else ""))
        
        # === SUBCHAPTER DETECTION ===
        elif el_type == "section_title" and content:
            # Skip certain section titles
            if content in SKIP_SECTION_TITLES:
                continue
            
            # Flush buffer before new section
            if state.slide_buffer and state.current_chapter:
                title = generate_slide_title(state.slide_buffer)
                slide = state.flush_slide_buffer()
                if slide:
                    state.current_chapter.add_slide(slide, state.current_subchapter)
                    state.subchapter_slides[state.current_subchapter].append(slide)
            
            state.current_subchapter = content
            state.slide_buffer = []
            state.buffer_word_count = 0
        
        # === CONTENT COLLECTION ===
        elif el_type == "paragraph" and content:
            # Skip editorial/administrative paragraphs
            content_preview = content.lower()[:100]
            if any(keyword in content_preview for keyword in SKIP_KEYWORDS):
                continue

            # If paragraph is exceptionally long, split into multiple paragraph items
            chunks = split_paragraph_into_chunks(content, MAX_SLIDE_WORDS)
            for chunk in chunks:
                item = ContentItem("paragraph", chunk)
                state.slide_buffer.append(item)
                state.buffer_word_count += item.word_count()

                # Flush if buffer reaches target
                if state.buffer_word_count >= OPTIMAL_SLIDE_WORDS:
                    title = generate_slide_title(state.slide_buffer)
                    slide = state.flush_slide_buffer(title)
                    if slide and state.current_chapter:
                        state.current_chapter.add_slide(slide, state.current_subchapter)
                        state.subchapter_slides[state.current_subchapter].append(slide)
        
        elif el_type == "bullet_point" and element.get("bullet_items"):
            for bullet_text in element.get("bullet_items", []):
                if bullet_text.strip():
                    item = ContentItem("bullet", bullet_text.strip())
                    state.slide_buffer.append(item)
                    state.buffer_word_count += item.word_count()
            
            # Flush if too many bullets
            bullet_count = sum(1 for i in state.slide_buffer if i.type == "bullet")
            if bullet_count >= MAX_BULLETS_PER_SLIDE:
                title = generate_slide_title(state.slide_buffer)
                slide = state.flush_slide_buffer(title)
                if slide and state.current_chapter:
                    state.current_chapter.add_slide(slide, state.current_subchapter)
                    state.subchapter_slides[state.current_subchapter].append(slide)
                state.buffer_word_count = 0
        
        # === FIGURE/TABLE HANDLING (influences chunk size) ===
        elif el_type in ("figure", "table"):
            # Determine element item and weight
            item = None
            weight = 0
            
            if el_type == "figure":
                fig_id = element.get("id")
                if fig_id in media_index:
                    media = media_index[fig_id]
                    item = ContentItem("figure", media["caption"], metadata=media)
                    weight = FIGURE_WEIGHT
            elif el_type == "table":
                item = ContentItem("table", "Table data", metadata={"caption": content or "Data Table"})
                weight = TABLE_WEIGHT
            
            if item:
                # Check if we should flush current buffer first
                 # Flush if adding this would exceed max size
                 if state.buffer_word_count + weight > MAX_SLIDE_WORDS:
                     if state.slide_buffer:
                         title = generate_slide_title(state.slide_buffer)
                         slide = state.flush_slide_buffer(title)
                         if slide and state.current_chapter:
                             state.current_chapter.add_slide(slide, state.current_subchapter)
                             state.subchapter_slides[state.current_subchapter].append(slide)
                 
                 # Add item to buffer (either existing or fresh)
                 state.slide_buffer.append(item)
                 state.buffer_word_count += weight
                 
                 # Check if we should flush NOW (if slide is now "full enough")
                 # We use a threshold slightly higher than OPTIMAL to allow combining fig + text
                 # but if it's already big, flush to avoid overcrowding next text
                 if state.buffer_word_count >= OPTIMAL_SLIDE_WORDS * 1.5:
                      title = generate_slide_title(state.slide_buffer)
                      slide = state.flush_slide_buffer(title)
                      if slide and state.current_chapter:
                         state.current_chapter.add_slide(slide, state.current_subchapter)
                         state.subchapter_slides[state.current_subchapter].append(slide)

# Flush remaining buffer
if state.slide_buffer and state.current_chapter:
    title = generate_slide_title(state.slide_buffer)
    slide = state.flush_slide_buffer(title)
    if slide:
        state.current_chapter.add_slide(slide, state.current_subchapter)
        state.subchapter_slides[state.current_subchapter].append(slide)

# === GENERATE LEARN CONTROLS ===
print("[INFO] Generating learn control questions...")
for chapter in state.chapters:
    for subchapter_title, slides in chapter.subchapters.items():
        # Collect all content from subchapter slides
        all_content = []
        for slide in slides:
            all_content.extend(slide.items)
        
        # Generate questions
        if all_content:
            questions = generate_learn_controls(subchapter_title, all_content)
            chapter.learn_controls[subchapter_title] = questions

# === RENDER TO MARKDOWN ===
print("[INFO] Rendering presentation...")
output_lines = []
output_lines.append("# Presentation Slide Deck\n")
output_lines.append("_Generated from extracted academic document_\n")
output_lines.append("---\n")

for chapter in state.chapters:
    output_lines.append(chapter.render_markdown())

presentation_text = "\n".join(output_lines)

# === SAVE OUTPUT ===
Path(OUTPUT_FILE).parent.mkdir(exist_ok=True)
Path(OUTPUT_FILE).write_text(presentation_text, encoding="utf-8")

# Statistics
total_slides = sum(len(ch.slides) for ch in state.chapters)
total_subchapters = sum(len(ch.subchapters) for ch in state.chapters)
slides_with_questions = sum(len(ch.learn_controls) for ch in state.chapters)

print("[OK] Presentation created: {}".format(OUTPUT_FILE))
print("[INFO] Total chapters: {}".format(len(state.chapters)))
print("[INFO] Total slides: {}".format(total_slides))
print("[INFO] Total subchapters: {}".format(total_subchapters))
print("[INFO] Slides with learn controls: {}".format(slides_with_questions))

# === EXPORT JSON BACKUP ===
slides_data = []
for chapter in state.chapters:
    for slide in chapter.slides:
        slides_data.append({
            "chapter": chapter.chapter_num,
            "chapter_main_title": chapter.main_title,
            "chapter_subtitle": chapter.subtitle,
            "slide_number": slide.slide_num,
            "slide_title": slide.title,
            "content": [
                {"type": item.type, "text": item.content, "metadata": item.metadata}
                for item in slide.items
            ]
        })

json_output = {
    "metadata": {
        "total_chapters": len(state.chapters),
        "total_slides": total_slides,
        "total_subchapters": total_subchapters,
        "source": INPUT_FILE
    },
    "slides": slides_data,
    "chapters": [
        {
            "chapter_num": ch.chapter_num,
            "main_title": ch.main_title,
            "subtitle": ch.subtitle,
            "slide_count": len(ch.slides),
            "subchapters": list(ch.subchapters.keys()),
            "learn_controls": {k: v for k, v in ch.learn_controls.items()}
        }
        for ch in state.chapters
    ]
}

json_path = OUTPUT_FILE.replace(".md", ".json")
Path(json_path).write_text(json.dumps(json_output, indent=2, ensure_ascii=False), encoding="utf-8")
print("[OK] JSON structure saved: {}".format(json_path))

"""
SLIDE DECK GENERATOR WITH INTELLIGENT CHUNKING

This script organizes extracted academic content into presentation slides with:
1. Content-aware chunking (each chunk = 1 slide, sized appropriately)
2. Chapter/subchapter structure preservation
3. Figure/table consideration in chunk sizing
4. Learn control questions (3-4 per subchapter) for reflection
"""

import json
from pathlib import Path
from collections import defaultdict
import re
import ollama


# === CONFIG ===
MODEL = "llama3.2"
INPUT_FILE = r"D:\schmalkalden uni\third semester\TADS\output\extraction_result.json"
OUTPUT_FILE = "slides/presentation.md"

# === CONSTANTS ===
OPTIMAL_SLIDE_WORDS = 150  # Target word count per slide (aligned to slide rules)
MAX_SLIDE_WORDS = 300      # Hard limit for slide word count
MIN_SLIDE_WORDS = 50       # Minimum before considering slide complete
MAX_BULLETS_PER_SLIDE = 10
MAX_PARAGRAPHS_PER_SLIDE = 3

# Elements to skip (non-educational content)
SKIP_ELEMENT_TYPES = {"author", "footer", "footnote", "caption", "header"}
SKIP_SECTION_TITLES = {"FROM THE AUTHORS", "MEDIA", "LEGAL AND EDITORIAL DETAILS"}

# === HELPER FUNCTIONS ===
def generate_slide_title_ollama(items: list) -> str:
    """
    Use Ollama to generate a precise, semantic slide title from content items.
    """
    # Collect content text
    content_text = " ".join([item.content for item in items if item.type in ("paragraph", "bullet")])
    
    if not content_text.strip():
        return "Content"
    
    prompt = f"""Given the following content, generate a single concise slide title (max 8 words) that captures the main concept. 
Respond with ONLY the title, nothing else.

Content:
{content_text[:500]}

Title:"""
    
    try:
        import ollama
        response = ollama.generate(model=MODEL, prompt=prompt, stream=False)
        title = response.get("response", "").strip()
        # Clean up the title
        title = title.replace('\n', '').strip('"').strip()
        return title if len(title) > 5 and len(title) < 100 else "Key Concept"
    except Exception as e:
        # Fallback: extract keywords
        keywords = []
        for item in items: 
            if item.type in ("paragraph", "bullet"):
                words = [w for w in item.content.split() if len(w) > 5 and not w.endswith(",")]
                keywords.extend(words[:3])
        if keywords:
            title = " ".join(keywords[:3])
            return title if len(title) > 10 else "Key Concepts"
        return "Content"

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
        try:
            response = ollama.generate(model=MODEL, prompt=prompt, stream=False)
            enhanced_desc = response.get("response", "").strip()
            if enhanced_desc and len(enhanced_desc) > 10:
                desc = enhanced_desc
        except:
            pass  # Use original description
    
    # Limit description to reasonable length
    if len(desc) > 400:
        desc = desc[:397] + "..."
    
    return str(caption)[:100], str(desc)

# === OLLAMA INTEGRATION ===
def generate_learn_controls(subchapter_title: str, slide_contents: list) -> list:
    """
    Generate 4 open-ended learning control questions using Ollama at different cognitive levels.
    Questions test: comprehension, analysis, application, and critical thinking.
    
    Args:
        subchapter_title: Title of the subchapter
        slide_contents: List of all content (ContentItem objects) in subchapter
    
    Returns:
        List of 4 question strings
    """
    # Combine all content for context
    all_text = " ".join([
        item.content for item in slide_contents 
        if item.type in ("paragraph", "bullet")
    ])
    
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

    try:
        import ollama
        response = ollama.generate(model=MODEL, prompt=prompt, stream=False)
        text = response.get("response", "").strip()
        
        # Parse numbered questions
        questions = []
        for line in text.split('\n'):
            match = re.match(r'^\d+\.\s+(.+)$', line.strip())
            if match:
                q = match.group(1).strip()
                if len(q) > 10:  # Ensure question is substantive
                    questions.append(q)
        
        return questions[:4] if questions else []
    except Exception as e:
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
    
    def word_count(self) -> int:
        """Count words in this item."""
        return len(self.content.split())
    
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
    
    try:
        import ollama
        response = ollama.generate(model=MODEL, prompt=prompt, stream=False)
        result_text = response.get("response", "").strip()
        
        # Parse chunks from response
        chunks = re.split(r'\[CHUNK \d+\]', result_text)
        chunks = [c.strip() for c in chunks if c.strip()]
        return chunks if chunks else [text.strip()]
    except Exception as e:
        # Fallback to simple sentence-based chunking
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current = []
        current_count = 0
        for s in sentences:
            s_words = s.split()
            if current_count + len(s_words) <= max_words:
                current.append(s)
                current_count += len(s_words)
            else:
                if current:
                    chunks.append(" ".join(current).strip())
                if len(s_words) > max_words:
                    i = 0
                    while i < len(s_words):
                        part = " ".join(s_words[i:i+max_words])
                        chunks.append(part.strip())
                        i += max_words
                    current = []
                    current_count = 0
                else:
                    current = [s]
                    current_count = len(s_words)
        if current:
            chunks.append(" ".join(current).strip())
        return chunks

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
        if subchapter:
            self.subchapters[subchapter].append(slide)
    
    def render_markdown(self) -> str:
        """Render entire chapter with learn controls at the end of each subchapter"""
        lines = []
        # Show main title first
        lines.append(f"\n## Chapter {self.chapter_num}: {self.main_title}\n")
        
        # Add subtitle if present
        if self.subtitle:
            lines.append(f"_{self.subtitle}_\n")
        
        # Group slides by subchapter
        subchapter_order = {}
        for i, slide in enumerate(self.slides):
            # Find which subchapter this slide belongs to
            for subchapter_title, subchapter_slides in self.subchapters.items():
                if slide in subchapter_slides:
                    if subchapter_title not in subchapter_order:
                        subchapter_order[subchapter_title] = []
                    subchapter_order[subchapter_title].append(slide)
                    break
        
        # Render each subchapter with its slides and then its learn controls
        for subchapter_title in subchapter_order:
            lines.append(f"\n#### {subchapter_title}\n")
            
            # Render all slides in this subchapter
            for slide in subchapter_order[subchapter_title]:
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
    doc = json.load(open(INPUT_FILE, "r", encoding="utf-8"))
except json.JSONDecodeError as e:
    # Try to fix common JSON corruption issues (comments, trailing commas)
    print(f"[WARN] JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # Remove inline comments like (comment text)
    content = re.sub(r',\s*\(.*?\)', ',', content)
    content = re.sub(r',\s*\(.*?$', ',', content, flags=re.MULTILINE)
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

chapters = []
current_chapter = None
current_chapter_num = 0
current_subchapter = None
slide_buffer = []
buffer_word_count = 0

def flush_slide_buffer(title_override: str = None) -> Slide:
    """Convert buffer contents to a slide"""
    if not slide_buffer:
        return None
    
    # Generate title from content if not provided
    if not title_override:
        # Extract from first section_title or generate from content
        section_titles = [item.content for item in slide_buffer if item.type == "section_title"]
        title_override = section_titles[0] if section_titles else "Content"
    
    slide = Slide(current_chapter_num, len(current_chapter.slides) + 1 if current_chapter else 1, 
                  title_override, slide_buffer.copy())
    
    slide_buffer.clear()
    global buffer_word_count
    buffer_word_count = 0
    return slide

# Track subchapter sequences for learn controls
subchapter_slides = defaultdict(list)

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
            if slide_buffer and current_chapter:
                slide = flush_slide_buffer()
                if slide:
                    current_chapter.add_slide(slide, current_subchapter)
                    subchapter_slides[current_subchapter].append(slide)
            
            current_chapter_num += 1
            main_title, subtitle = split_title_at_colon(content)
            current_chapter = Chapter(current_chapter_num, main_title, subtitle)
            chapters.append(current_chapter)
            print("[INFO] Chapter {}: {} {}".format(current_chapter_num, main_title, 
                                                     "- " + subtitle if subtitle else ""))
        
        # === SUBCHAPTER DETECTION ===
        elif el_type == "section_title" and content:
            # Skip certain section titles
            if content in SKIP_SECTION_TITLES:
                continue
            
            # Flush buffer before new section
            if slide_buffer and current_chapter:
                title = generate_slide_title(slide_buffer)
                slide = flush_slide_buffer(title)
                if slide:
                    current_chapter.add_slide(slide, current_subchapter)
                    subchapter_slides[current_subchapter].append(slide)
            
            current_subchapter = content
            slide_buffer = []
            buffer_word_count = 0
        
        # === CONTENT COLLECTION ===
        elif el_type == "paragraph" and content:
            # Skip editorial/administrative paragraphs
            if any(keyword in content.lower()[:100] for keyword in ["phone:", "fax:", "publishers", "editors", "editorial", "volume"]):
                continue

            # If paragraph is exceptionally long, split into multiple paragraph items
            chunks = split_paragraph_into_chunks(content, MAX_SLIDE_WORDS)
            for chunk in chunks:
                item = ContentItem("paragraph", chunk)
                slide_buffer.append(item)
                buffer_word_count += item.word_count()

                # Flush if buffer reaches target
                if buffer_word_count >= OPTIMAL_SLIDE_WORDS:
                    title = generate_slide_title(slide_buffer)
                    slide = flush_slide_buffer(title)
                    if slide and current_chapter:
                        current_chapter.add_slide(slide, current_subchapter)
                        subchapter_slides[current_subchapter].append(slide)
        
        elif el_type == "bullet_point" and element.get("bullet_items"):
            for bullet_text in element.get("bullet_items", []):
                if bullet_text.strip():
                    item = ContentItem("bullet", bullet_text.strip())
                    slide_buffer.append(item)
                    buffer_word_count += item.word_count()
            
            # Flush if too many bullets
            bullet_count = sum(1 for i in slide_buffer if i.type == "bullet")
            if bullet_count >= MAX_BULLETS_PER_SLIDE:
                title = generate_slide_title(slide_buffer)
                slide = flush_slide_buffer(title)
                if slide and current_chapter:
                    current_chapter.add_slide(slide, current_subchapter)
                    subchapter_slides[current_subchapter].append(slide)
                buffer_word_count = 0
        
        # === FIGURE/TABLE HANDLING (influences chunk size) ===
        elif el_type == "figure":
            fig_id = element.get("id")
            if fig_id in media_index:
                media = media_index[fig_id]
                
                # Flush current buffer first
                if slide_buffer and current_chapter:
                    title = generate_slide_title(slide_buffer)
                    slide = flush_slide_buffer(title)
                    if slide:
                        current_chapter.add_slide(slide, current_subchapter)
                        subchapter_slides[current_subchapter].append(slide)
                    slide_buffer.clear()
                    buffer_word_count = 0
                
                # Create dedicated figure slide
                fig_item = ContentItem("figure", media["caption"], metadata=media)
                fig_slide = Slide(current_chapter_num, len(current_chapter.slides) + 1 if current_chapter else 1,
                                 f"Figure: {media['caption']}", [fig_item])
                if current_chapter:
                    current_chapter.add_slide(fig_slide, current_subchapter)
                    subchapter_slides[current_subchapter].append(fig_slide)
        
        elif el_type == "table":
            # Similar handling for tables
            if slide_buffer and current_chapter:
                title = generate_slide_title(slide_buffer)
                slide = flush_slide_buffer(title)
                if slide:
                    current_chapter.add_slide(slide, current_subchapter)
                    subchapter_slides[current_subchapter].append(slide)
                slide_buffer.clear()
                buffer_word_count = 0
            
            table_item = ContentItem("table", "Table data", metadata={"caption": content or "Data Table"})
            table_slide = Slide(current_chapter_num, len(current_chapter.slides) + 1 if current_chapter else 1,
                               f"Table: {content}", [table_item])
            if current_chapter:
                current_chapter.add_slide(table_slide, current_subchapter)
                subchapter_slides[current_subchapter].append(table_slide)

# Flush remaining buffer
if slide_buffer and current_chapter:
    title = generate_slide_title(slide_buffer)
    slide = flush_slide_buffer(title)
    if slide:
        current_chapter.add_slide(slide, current_subchapter)
        subchapter_slides[current_subchapter].append(slide)

# === GENERATE LEARN CONTROLS ===
print("[INFO] Generating learn control questions...")
for chapter in chapters:
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

for chapter in chapters:
    output_lines.append(chapter.render_markdown())

presentation_text = "\n".join(output_lines)

# === SAVE OUTPUT ===
Path(OUTPUT_FILE).parent.mkdir(exist_ok=True)
Path(OUTPUT_FILE).write_text(presentation_text, encoding="utf-8")

# Statistics
total_slides = sum(len(ch.slides) for ch in chapters)
total_subchapters = sum(len(ch.subchapters) for ch in chapters)
slides_with_questions = sum(len(ch.learn_controls) for ch in chapters)

print("[OK] Presentation created: {}".format(OUTPUT_FILE))
print("[INFO] Total chapters: {}".format(len(chapters)))
print("[INFO] Total slides: {}".format(total_slides))
print("[INFO] Total subchapters: {}".format(total_subchapters))
print("[INFO] Slides with learn controls: {}".format(slides_with_questions))

# === EXPORT JSON BACKUP ===
slides_data = []
for chapter in chapters:
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
        "total_chapters": len(chapters),
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
        for ch in chapters
    ]
}

json_path = OUTPUT_FILE.replace(".md", ".json")
Path(json_path).write_text(json.dumps(json_output, indent=2, ensure_ascii=False), encoding="utf-8")
print("[OK] JSON structure saved: {}".format(json_path))

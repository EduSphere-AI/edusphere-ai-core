# pdf_course_extractor_summarization/structure.py


class Structurer:
    def __init__(self):
        self.slide_counter = 1


    def build_hierarchy(self, blocks):

        chapters = []
        current_chapter = None
        current_subchapter = None
        last_page = None

        def start_chapter(title: str):
            nonlocal current_chapter, current_subchapter, last_page
            chap_id = len(chapters) + 1
            current_chapter = {
                "id": chap_id,
                "title": title or f"Chapter {chap_id}",
                "subchapters": [],
                "blocks": [],
            }
            chapters.append(current_chapter)
            current_subchapter = None
            last_page = None

        def ensure_chapter(default_title: str = "General"):
            nonlocal current_chapter
            if current_chapter is None:
                start_chapter(default_title)

        def start_subchapter(title: str):
            nonlocal current_subchapter
            ensure_chapter()
            sub_id = len(current_chapter["subchapters"]) + 1
            current_subchapter = {
                "id": sub_id,
                "title": title or f"Section {sub_id}",
                "blocks": [],
            }
            current_chapter["subchapters"].append(current_subchapter)

        for block in blocks:
            page = block.metadata.get("page")


            if block.type == "title":

                if current_chapter is None:
                    start_chapter(block.text.strip() or "General")
                continue

            elif block.type == "chapter-title":
                start_chapter(block.text.strip() or "Chapter")

            elif block.type == "subchapter-title":
                start_subchapter(block.text.strip() or "Section")
                continue


            if page is not None and page != last_page:

                last_page = page

                start_subchapter(f"Page {page}")


            if current_subchapter is None:
                start_subchapter("Overview")


            current_subchapter["blocks"].append(block)
            current_chapter["blocks"].append(block)


        if not chapters:
            start_chapter("General")
            if current_subchapter is None:
                start_subchapter("Overview")

        return chapters


    def create_slides(self, chapters):

        slides = []

        for chap in chapters:
            for sub in chap["subchapters"]:
                text_buffer = []

                for block in sub["blocks"]:
                    if block.type in ("image", "page_image"):

                        if text_buffer:
                            slides.extend(
                                self._flush_text_slides(text_buffer, chap, sub)
                            )
                            text_buffer = []

                        images = block.content.get("images", [])
                        slide = {
                            "id": self.slide_counter,
                            "type": "content_image",
                            "chapter_id": chap["id"],
                            "subchapter_id": sub["id"],
                            "title": sub["title"],
                            "images": images,
                            "metadata": {
                                "page": block.metadata.get("page"),
                                "kind": block.metadata.get(
                                    "source",
                                    "figure" if block.type == "image" else "page_snapshot",
                                ),
                                "ocr_text": block.metadata.get("ocr_text", ""),
                            },
                        }
                        slides.append(slide)
                        self.slide_counter += 1

                    else:

                        if getattr(block, "text", "").strip():
                            text_buffer.append(block)


                if text_buffer:
                    slides.extend(self._flush_text_slides(text_buffer, chap, sub))

        return slides

    def _flush_text_slides(self, blocks, chap, sub, max_words: int = 120):

        generated_slides = []
        current_words = []

        def emit_slide():
            nonlocal current_words
            if not current_words:
                return
            slide_text = " ".join(current_words).strip()
            if not slide_text:
                current_words = []
                return
            slide = {
                "id": self.slide_counter,
                "type": "content_text",
                "chapter_id": chap["id"],
                "subchapter_id": sub["id"],
                "title": sub["title"],
                "text": slide_text,
                "metadata": {},
            }
            generated_slides.append(slide)
            self.slide_counter += 1
            current_words = []

        for b in blocks:
            words = b.text.split()
            if not words:
                continue


            if current_words and len(current_words) + len(words) > max_words:
                emit_slide()

            current_words.extend(words)


        emit_slide()
        return generated_slides


    def _clean_questions_list(
        self,
        questions,
        min_length: int = 15,
        banned_substrings=None,
        banned_tokens=None,
        global_seen=None,
    ):

        if not questions:
            return []

        if banned_substrings is None:
            banned_substrings = set()
        if banned_tokens is None:
            banned_tokens = set()
        if global_seen is None:
            global_seen = set()

        cleaned = []

        for q in questions:
            if not q:
                continue


            q_str = " ".join(str(q).split()).strip()
            if not q_str:
                continue


            tokens = q_str.split()
            if len(tokens) < 3:
                continue


            if len(q_str) < min_length:
                continue

            q_lower = q_str.lower()


            if any(b in q_lower for b in banned_substrings):
                continue
            if any(bt in q_lower for bt in banned_tokens):
                continue


            if q_lower in global_seen:
                continue

            global_seen.add(q_lower)
            cleaned.append(q_str)

        return cleaned

    def sanitize_questions_on_chapters(self, chapters, min_length: int = 15) -> None:

        if not chapters:
            return

        banned_substrings = {
            "weekly report",
            "diw weekly",
            "weekly important",
            "at a glance",
            "issn",
            "newsletter",
            "newsletter_en",
            "newsletter_de",
            "kundenservice",
            "customer service",
            "editorial",
            "legal notice",
            "legal information",
            "legal and editorial",
            "legal and editorial details",
            "imprint",
            "privacy policy",
            "www.",
            "http://",
            "https://",
            "pdf file",
            "how many questions",
            "number of questions",
            "study question",
            "study questions",
        }

        banned_tokens = {
            "weekly",
            "report",
            "glance",
            "legal",
            "editorial",
            "newsletter",
            "kundenservice",
            "service",
            "imprint",
            "issn",
            "diw",
            "page",
            "media",
            "gmbh",
            "kg",
            "berlin",
            "germany",
            "question",
            "questions",
        }

        global_seen = set()

        for chap in chapters:

            chap_qs = chap.get("questions")
            if chap_qs:
                chap["questions"] = self._clean_questions_list(
                    chap_qs,
                    min_length=min_length,
                    banned_substrings=banned_substrings,
                    banned_tokens=banned_tokens,
                    global_seen=global_seen,
                )


            for sub in chap.get("subchapters", []):
                sub_qs = sub.get("questions") or []
                cleaned = self._clean_questions_list(
                    sub_qs,
                    min_length=min_length,
                    banned_substrings=banned_substrings,
                    banned_tokens=banned_tokens,
                    global_seen=global_seen,
                )


                if not cleaned:
                    generic_candidates = [
                        "What are the main points discussed on this page?",
                        "How does this part of the report contribute to understanding the fiscal capacity of German federal states?",
                    ]
                    cleaned_generic = []
                    for g in generic_candidates:
                        g_norm = " ".join(g.split()).strip().lower()
                        if g_norm in global_seen:
                            continue
                        global_seen.add(g_norm)
                        cleaned_generic.append(g)
                    if cleaned_generic:
                        cleaned = cleaned_generic

                sub["questions"] = cleaned
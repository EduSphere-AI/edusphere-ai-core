import os
import json
import argparse
from typing import Any, Dict, List, Tuple

from tqdm import tqdm

try:
    from .config import Config
    from .extractor import PDFExtractor
    from .image_processor import ImageProcessor
    from .nlp_processor import NLPProcessor
    from .structure import Structurer
    from .postprocessing.enhance_figures_and_tables import enhance_figures_and_tables
except ImportError:
    from config import Config
    from extractor import PDFExtractor
    from image_processor import ImageProcessor
    from nlp_processor import NLPProcessor
    from structure import Structurer
    from postprocessing.enhance_figures_and_tables import enhance_figures_and_tables


class UltimateCourseExtractor:
    def __init__(self, pdf_path: str, output_dir: str) -> None:
        self.pdf_path = pdf_path
        self.output_dir = output_dir or Config.DEFAULT_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        self.extractor = PDFExtractor(pdf_path, self.output_dir)
        self.img_processor = ImageProcessor(self.output_dir)
        self.nlp = NLPProcessor()
        self.structurer = Structurer()
        self._doc_summary: str = ""

    # ----------------- main pipeline -----------------
    def process(self) -> Dict[str, Any]:
        print("--- Starting Extraction ---")


        print("Extracting content from PDF...")
        blocks = self.extractor.extract_content()
        print(f"Extracted {len(blocks)} blocks.")


        print("Processing images...")
        for block in tqdm(blocks, desc="Images"):
            if getattr(block, "type", None) == "image":
                images_list = getattr(block, "content", {}).get("images", [])
                for img_item in images_list:
                    path = img_item.get("path")
                    if not path:
                        continue
                    result = self.img_processor.process_image(path, block.id)
                    if result:
                        img_item["masked_filename"] = (
                            os.path.basename(result.get("masked_image_path"))
                            if result.get("masked_image_path")
                            else None
                        )
                        img_item["ocr_items"] = result.get("ocr_items", [])
                        ocr_text = result.get("ocr_text")
                        if ocr_text:
                            block.metadata["ocr_text"] = ocr_text


        print("Structuring content...")
        chapters = self.structurer.build_hierarchy(blocks)
        slides = self.structurer.create_slides(chapters)


        print("Generating summaries and questions...")
        self._apply_nlp(chapters, blocks)


        self._attach_nlp_to_slides(slides, chapters)


        final_db = {
            "document": {
                "metadata": self._build_document_metadata(slides),
                "content_blocks": [self._serialize_block(b) for b in blocks],
                "hierarchy": self._serialize_hierarchy(chapters),
                "slides": slides,
            }
        }

        return final_db

    # ----------------- NLP helpers -----------------
    def _gather_text(self, blocks: List[Any]) -> str:

        parts: List[str] = []
        for b in blocks:
            txt = getattr(b, "text", "") or ""
            if txt.strip():
                parts.append(txt.strip())

            meta = getattr(b, "metadata", {}) or {}
            ocr_txt = meta.get("ocr_text", "")
            if isinstance(ocr_txt, str) and ocr_txt.strip():
                parts.append(ocr_txt.strip())

        return " ".join(parts)

    def _apply_nlp(self, chapters: List[Dict[str, Any]], blocks: List[Any]) -> None:

        doc_text = self._gather_text(blocks)

        self.nlp.register_document_text(doc_text)


        doc_summary = ""
        if (
            self.nlp.summarizer
            and len(doc_text.split()) >= Config.MIN_WORDS_FOR_SUMMARY
        ):
            doc_summary = self.nlp.summarize(
                doc_text,
                max_chars=Config.DOC_MAX_CHARS,
                max_length=Config.DOC_SUMMARY_MAX,
                min_length=Config.DOC_SUMMARY_MIN,
            )
        self._doc_summary = doc_summary

        enable_qg = getattr(Config, "ENABLE_QG", True)
        enable_quizzes = getattr(Config, "ENABLE_QUIZZES", True)
        questions_per_sub = getattr(Config, "QUESTIONS_PER_SUBCHAPTER", 3)
        quiz_max_items = getattr(Config, "QUIZ_MAX_ITEMS_PER_SUBCHAPTER", 3)


        for chap in tqdm(chapters, desc="NLP"):

            chap_blocks: List[Any] = []
            for sub in chap.get("subchapters", []):
                chap_blocks.extend(sub.get("blocks", []))
            chap_text = self._gather_text(chap_blocks)

            chap_summary = ""
            if (
                self.nlp.summarizer
                and len(chap_text.split()) >= Config.MIN_WORDS_FOR_SUMMARY
            ):
                chap_summary = self.nlp.summarize(
                    chap_text,
                    max_chars=Config.CHAPTER_MAX_CHARS,
                    max_length=Config.CHAPTER_SUMMARY_MAX,
                    min_length=Config.CHAPTER_SUMMARY_MIN,
                )
            chap["summary"] = chap_summary


            for sub in chap.get("subchapters", []):
                sub_blocks = sub.get("blocks", [])
                sub_text = self._gather_text(sub_blocks)
                has_text = bool(sub_text and sub_text.strip())


                sub_summary = ""
                if (
                    has_text
                    and self.nlp.summarizer
                    and len(sub_text.split()) >= Config.MIN_WORDS_FOR_SUMMARY
                ):
                    sub_summary = self.nlp.summarize(
                        sub_text,
                        max_chars=Config.SUBCHAPTER_MAX_CHARS,
                        max_length=Config.SUBCHAPTER_SUMMARY_MAX,
                        min_length=Config.SUBCHAPTER_SUMMARY_MIN,
                    )
                sub["summary"] = sub_summary


                questions: List[str] = []
                if has_text and enable_qg:
                    questions = self.nlp.generate_questions(
                        sub_text,
                        count=questions_per_sub,
                    )


                quiz_items: List[Dict[str, Any]] = []
                if has_text and enable_quizzes:
                    quiz_items = self.nlp.generate_quiz_items(
                        sub_text,
                        base_questions=questions,
                        max_items=quiz_max_items,
                    )


                if has_text:
                    if not questions and quiz_items:
                        questions = [
                            q.get("question", "")
                            for q in quiz_items
                            if q.get("question", "").strip()
                        ]

                    if questions and not quiz_items:
                        quiz_items = [
                            {"type": "open", "question": q}
                            for q in questions
                            if str(q).strip()
                        ]

                    if not questions and not quiz_items:

                        fallback_questions = self.nlp._generate_generic_page_questions(
                            questions_per_sub
                        )
                        questions = fallback_questions
                        quiz_items = [
                            {"type": "open", "question": q} for q in fallback_questions
                        ]
                else:
                    questions = []
                    quiz_items = []

                sub["questions"] = questions
                sub["quizzes"] = quiz_items

    def _attach_nlp_to_slides(
        self, slides: List[Dict[str, Any]], chapters: List[Dict[str, Any]]
    ) -> None:

        sub_index: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for chap in chapters:
            chap_id = chap.get("id")
            for sub in chap.get("subchapters", []):
                sub_id = sub.get("id")
                sub_index[(chap_id, sub_id)] = sub

        for slide in slides:
            key = (slide.get("chapter_id"), slide.get("subchapter_id"))
            sub = sub_index.get(key)
            if sub:
                slide["summary"] = sub.get("summary", "")
                slide["questions"] = sub.get("questions", [])
                slide["quizzes"] = sub.get("quizzes", [])
            else:
                slide["summary"] = ""
                slide["questions"] = []
                slide["quizzes"] = []

    # ----------------- serialization helpers -----------------
    def _build_document_metadata(self, slides: List[Dict[str, Any]]) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "source": self.pdf_path,
            "total_slides": len(slides),
        }
        if self._doc_summary:
            meta["summary"] = self._doc_summary
        return meta

    def _serialize_block(self, block: Any) -> Dict[str, Any]:
        return {
            "id": getattr(block, "id", None),
            "type": getattr(block, "type", None),
            "text": getattr(block, "text", None),
            "content": getattr(block, "content", {}),
            "metadata": getattr(block, "metadata", {}),
        }

    def _serialize_hierarchy(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        ser_chapters: List[Dict[str, Any]] = []
        for c in chapters:
            ser_subs: List[Dict[str, Any]] = []
            for s in c.get("subchapters", []):
                ser_subs.append(
                    {
                        "id": s.get("id"),
                        "title": s.get("title"),
                        "summary": s.get("summary", ""),
                        "questions": s.get("questions", []),
                        "quizzes": s.get("quizzes", []),
                    }
                )
            ser_chapters.append(
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "summary": c.get("summary", ""),
                    "subchapters": ser_subs,
                }
            )
        return {"chapters": ser_chapters}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Course Content from PDF")
    parser.add_argument("pdf_path", help="Path to input PDF")
    parser.add_argument(
        "--output",
        default=Config.DEFAULT_OUTPUT_DIR,
        help="Output directory",
    )
    args = parser.parse_args()

    extractor = UltimateCourseExtractor(args.pdf_path, args.output)
    final_db = extractor.process()


    final_db = enhance_figures_and_tables(final_db)

    out_file = os.path.join(args.output, "final_normalized_db.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_db, f, indent=4, ensure_ascii=False)

    print(f"Done! Saved to {out_file}")


if __name__ == "__main__":
    main()
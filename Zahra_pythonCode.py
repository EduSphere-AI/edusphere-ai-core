# PDF analysis and summarization pipeline.
# This script:
#   1. Extracts text from one or more PDF files,
#   2. Splits the text into sections based on ALL-CAPS headings,
#   3. Summarizes each section with LexRank (sumy),
#   4. Extracts all tables using pdfplumber,
#   5. Saves everything into a standardized JSON file.

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import nltk
import pdfplumber
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer


# -------------------------- Paths & configuration ---------------------------

# Folder where this Python file lives
BASE_DIR: Path = Path(__file__).resolve().parent

# Absolute path to my PDF in the Desktop/TADS2 folder
DEFAULT_PDF_FILES: List[Path] = [
    Path(r"C:\Users\Ghazaleh2023\OneDrive\Desktop\TADS2\dwr-25-40-1.pdf"),
]

# Output JSON file path
OUTPUT_JSON_PATH: Path = BASE_DIR / "standardized_course_data.json"


# ------------------------ NLTK setup ----------------------------------------

def ensure_nltk_models() -> None:
    """
    Make sure required NLTK data is available.
    This prevents runtime errors when the tokenizer is used.
    """
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)


# ------------------------ PDF text extraction -------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text from all pages of a PDF using pdfplumber.

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.

    Returns
    -------
    str
        Concatenated text of all pages.
    """
    all_text: str = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                all_text += page_text + "\n"

    return all_text


# ------------------------- Section splitting --------------------------------

def split_into_sections(all_text: str, min_words: int = 15) -> List[Dict[str, str]]:
    """
    Splitting the document text into sections based on ALL-CAPS headings.

    Parameters
    ----------
    all_text : str
        Full document text.
    min_words : int
        Minimum number of words required to keep a section.

    Returns
    -------
    List[Dict[str, str]]
        Each dict has:
        - "section": section title (normalized),
        - "content": body text for that section.
    """
    # Headings look like: "\nSOME TITLE HERE\n"
    section_pattern = r"\n([A-Z][A-Z\s\-&]+)\n"
    parts = re.split(section_pattern, all_text)

    sections: List[Dict[str, str]] = []

    for i in range(1, len(parts), 2):
        raw_name = parts[i]
        raw_content = parts[i + 1]

        section_name = raw_name.strip().title()
        section_content = raw_content.strip()

        if len(section_content.split()) >= min_words:
            sections.append(
                {
                    "section": section_name,
                    "content": section_content,
                }
            )

    return sections


# ------------------------- Section summarization ----------------------------

def summarize_sections(
    sections: List[Dict[str, str]],
    sentences_per_section: int = 3,
    language: str = "english",
) -> List[Dict[str, Any]]:
    """
    Summarizing each section using the LexRank extractive summarizer.

    Parameters
    ----------
    sections : list of dict
        As returned by split_into_sections().
    sentences_per_section : int
        Number of sentences to keep per summary.
    language : str
        Language for the tokenizer (default: "english").

    Returns
    -------
    List[Dict[str, Any]]
        Each dict has:
        - "section": original section name,
        - "summary": list of summary sentences.
    """
    summarizer = LexRankSummarizer()
    summaries: List[Dict[str, Any]] = []

    for section in sections:
        content = section["content"]
        parser = PlaintextParser.from_string(content, Tokenizer(language))
        summary_sentences = [
            str(sentence)
            for sentence in summarizer(parser.document, sentences_per_section)
        ]

        summaries.append(
            {
                "section": section["section"],
                "summary": summary_sentences,
            }
        )

    return summaries


# ------------------------- Table extraction ---------------------------------

def extract_tables_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extracting all tables from a PDF file.

    Parameters
    ----------
    pdf_path : Path
        PDF path.

    Returns
    -------
    List[Dict[str, Any]]
        Each dict has:
        - "page": 1-based page index,
        - "table_number": index of the table on that page,
        - "table": raw table data (list of rows).
    """
    tables_data: List[Dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for pg_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for tbl_num, table in enumerate(tables, start=1):
                tables_data.append(
                    {
                        "page": pg_num,
                        "table_number": tbl_num,
                        "table": table,
                    }
                )

    return tables_data


# ------------------------- High-level processing ----------------------------

def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Running the full pipeline on a single PDF.

    Returns a dictionary with:
        - "source_file": path to the PDF,
        - "sections": summarized sections,
        - "tables": extracted tables.
    """
    text = extract_pdf_text(pdf_path)
    sections = split_into_sections(text)
    summaries = summarize_sections(sections)
    tables = extract_tables_from_pdf(pdf_path)

    return {
        "source_file": str(pdf_path),
        "sections": summaries,
        "tables": tables,
    }


def process_all_pdfs(pdf_list: List[Path]) -> List[Dict[str, Any]]:
    """
    Applying the pipeline to a list of PDF files.
    """
    results: List[Dict[str, Any]] = []
    for pdf_path in pdf_list:
        results.append(process_pdf(pdf_path))
    return results


def save_to_json(data: Any, output_path: Path) -> None:
    """
    Saving processed data to a JSON file.
    """
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------- Script entry point -------------------------------

def main() -> None:
    """
    Entry point when run as a script.
    """
    ensure_nltk_models()

    for p in DEFAULT_PDF_FILES:
        if not p.exists():
            raise FileNotFoundError(f"Input PDF not found: {p}")

    standardized_data = process_all_pdfs(DEFAULT_PDF_FILES)

    for file_data in standardized_data:
        print(
            f"File: {file_data['source_file']} | "
            f"Sections: {len(file_data['sections'])} | "
            f"Tables: {len(file_data['tables'])}"
        )

    save_to_json(standardized_data, OUTPUT_JSON_PATH)
    print(f"\nStandardized data saved to: {OUTPUT_JSON_PATH}")


if __name__ == "__main__":
    main()

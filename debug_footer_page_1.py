import pdfplumber
import sys


def debug_page_1_footer():
    pdf_path = "/Users/siddhantdalvi/DEV/MAIN/RAG/edusphere-ai-core/data/input.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(extra_attrs=['fontname', 'size'])

        page_height = float(page.height)
        footer_zone = page_height * 0.92

        print(f"Page Height: {page_height}")
        print(f"Footer Zone Start: {footer_zone}")

        footer_words = [w for w in words if w.get("top", 0) > footer_zone]

        print(f"\nFound {len(footer_words)} footer words:")
        for w in footer_words:
            print(
                f"Text: '{w['text']}' | x0: {w['x0']:.2f} | x1: {w['x1']:.2f} | top: {w['top']:.2f}"
            )


if __name__ == "__main__":
    debug_page_1_footer()

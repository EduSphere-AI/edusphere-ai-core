import pdfplumber
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inspect_page_3_bottom():
    pdf_path = "data/input.pdf"

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[2]  # Page 3
        height = page.height
        width = page.width

        print(f"Page 3 Dimensions: {width}x{height}")

        words = page.extract_words(extra_attrs=['fontname', 'size'])

        # Find the specific text
        target_text = "In comparative economic analyses"

        found_words = []
        for w in words:
            if target_text in w['text'] or w['text'] in target_text.split():
                # Simple check to find the region
                if "comparative" in w['text'] and "economic" in words[
                        words.index(w) + 1]['text']:
                    found_words.append(w)

        # Let's just look for words in the bottom 20% of the page
        bottom_words = [w for w in words if w['top'] > height * 0.75]

        print(f"\n--- Words in bottom 25% (y > {height * 0.75}) ---")

        # Group by line roughly
        lines = {}
        for w in bottom_words:
            y = round(w['top'], 0)
            if y not in lines: lines[y] = []
            lines[y].append(w)

        for y in sorted(lines.keys()):
            line_text = " ".join([w['text'] for w in lines[y]])
            if "comparative" in line_text or "economic" in line_text:
                print(f"\nY={y} (Relative: {y/height:.2f}): {line_text}")
                # Print font sizes
                sizes = [w['size'] for w in lines[y]]
                print(f"  Font sizes: {sizes}")
                print(f"  Avg Size: {sum(sizes)/len(sizes)}")


if __name__ == "__main__":
    inspect_page_3_bottom()

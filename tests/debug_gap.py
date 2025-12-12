import pdfplumber
import sys


def check_gap():
    pdf_path = "data/input.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[2]  # Page 3
        words = page.extract_words()

        # Find "states in the"
        left_words = [
            w for w in words
            if "states" in w['text'] and "in" in words[words.index(w) +
                                                       1]['text']
        ]
        # Find "In comparative"
        right_words = [w for w in words if "comparative" in w['text']]

        if left_words and right_words:
            # Assuming they are on the same line
            # Find the specific line
            target_y = 0
            for lw in left_words:
                for rw in right_words:
                    if abs(lw['top'] - rw['top']) < 5:
                        target_y = lw['top']
                        print(f"Found matching line at Y={target_y}")

                        # Get all words on this line
                        line_words = [
                            w for w in words if abs(w['top'] - target_y) < 5
                        ]
                        line_words.sort(key=lambda w: w['x0'])

                        print("Words on line:")
                        for i, w in enumerate(line_words):
                            print(
                                f"{i}: '{w['text']}' x1={w['x1']:.2f} x0_next={line_words[i+1]['x0']:.2f} Gap={line_words[i+1]['x0'] - w['x1']:.2f}"
                                if i < len(line_words) -
                                1 else f"{i}: '{w['text']}'")


if __name__ == "__main__":
    check_gap()

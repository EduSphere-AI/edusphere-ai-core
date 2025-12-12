import pdfplumber


def inspect_page_2_details():
    with pdfplumber.open("data/input.pdf") as pdf:
        page = pdf.pages[1]  # Page 2

        print(f"Page 2 size: {page.width}x{page.height}")

        words = page.extract_words(extra_attrs=["fontname", "size"])

        targets = [
            "immediately", "disrepair", "state", "1", "Finanzausgleich",
            "equaliza-"
        ]

        print(
            f"{'Text':<20} {'Size':<10} {'Top':<10} {'Bottom':<10} {'Font':<20}"
        )
        print("-" * 70)

        for w in words:
            if any(t in w['text'] for t in targets):
                print(
                    f"{w['text']:<20} {w['size']:<10.2f} {w['top']:<10.2f} {w['bottom']:<10.2f} {w['fontname']:<20}"
                )

        print("\n--- Sequence check for 'state of 1 disrepair' ---")
        for i, w in enumerate(words):
            if "disrepair" in w['text']:
                start = max(0, i - 5)
                end = min(len(words), i + 5)
                sequence = " ".join(
                    [word['text'] for word in words[start:end]])
                print(f"Sequence: ...{sequence}...")

                for j in range(start, end):
                    word = words[j]
                    print(
                        f"'{word['text']}' -> Size: {word['size']:.2f}, Top: {word['top']:.2f}"
                    )


if __name__ == "__main__":
    inspect_page_2_details()

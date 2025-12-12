import pdfplumber

def inspect_page_2_break():
    """Inspect where the paragraph split occurs on page 2"""
    with pdfplumber.open("data/input.pdf") as pdf:
        page = pdf.pages[1]  # Page 2 (0-indexed)
        words = page.extract_words(extra_attrs=['fontname', 'size'])
        
        # Find words around the break point (between "circumstances" and "Even before")
        print("Looking for words around the break...")
        for i, w in enumerate(words):
            if "circumstances" in w['text'] or "Even before" in w['text']:
                # Print surrounding words
                start = max(0, i - 3)
                end = min(len(words), i + 8)
                print(f"\nContext around '{w['text']}':")
                for j in range(start, end):
                    word = words[j]
                    print(f"  [{j}] '{word['text']}' | top={word['top']:.1f} | size={word['size']:.1f} | font={word['fontname']}")

if __name__ == "__main__":
    inspect_page_2_break()

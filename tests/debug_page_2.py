import pdfplumber
import json

def inspect_page_2():
    pdf_path = "data/input.pdf"
    with pdfplumber.open(pdf_path) as pdf:
        # Page 2 is index 1
        page = pdf.pages[1]
        
        print(f"Page {page.page_number} dimensions: {page.width}x{page.height}")
        
        # Extract words to see if Abstract text is there
        words = page.extract_words()
        abstract_words = [w for w in words if "ABSTRACT" in w['text'] or "unification" in w['text']]
        print("\n--- Searching for 'ABSTRACT' and 'unification' ---")
        for w in abstract_words:
            print(w)
            
        # Extract raw text
        print("\n--- Raw Text Extraction ---")
        print(page.extract_text())
        
        # Check for rects (colored backgrounds)
        print("\n--- Rectangles (Potential Backgrounds) ---")
        for rect in page.rects:
            print(f"Rect: x={rect['x0']:.2f}, y={rect['top']:.2f}, w={rect['width']:.2f}, h={rect['height']:.2f}, color={rect.get('non_stroking_color')}")

        # Check for images
        print("\n--- Images ---")
        for img in page.images:
            print(f"Image: x={img['x0']:.2f}, y={img['top']:.2f}, w={img['width']:.2f}, h={img['height']:.2f}")

if __name__ == "__main__":
    inspect_page_2()

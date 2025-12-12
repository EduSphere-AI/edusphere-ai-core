import pdfplumber
import fitz

def inspect_page_4_structure():
    pdf_path = "data/input.pdf"
    
    print("--- PyMuPDF Rects ---")
    doc = fitz.open(pdf_path)
    page = doc[3] # Page 4
    
    # Print drawings/rects
    for draw in page.get_drawings():
        # Check if it's a filled rect
        if draw['fill']:
            rect = draw['rect']
            print(f"Rect: {rect}, Fill: {draw['fill']}")
            
    print("\n--- PDFPlumber Rects ---")
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[3]
        print(f"Page size: {p.width}x{p.height}")
        for rect in p.rects:
            print(f"Rect: x0={rect['x0']}, top={rect['top']}, x1={rect['x1']}, bottom={rect['bottom']}")
            # Check color if available
            if 'non_stroking_color' in rect:
                print(f"  Color: {rect['non_stroking_color']}")
                
        # Also check words in the "Box 1" area
        # Based on previous debug, Box 1 title is around top 822 (footer?) No wait.
        # Previous debug showed "Box 1" caption at top? No, let's check the JSON.
        # JSON says "Box 1" is a caption.
        
        # Let's find where "For the purposes" is.
        words = p.extract_words()
        box_words = [w for w in words if "purposes" in w['text']]
        if box_words:
            print(f"\n'purposes' found at: {box_words[0]}")
            
        # Check "Outlined below"
        main_words = [w for w in words if "Outlined" in w['text']]
        if main_words:
            print(f"'Outlined' found at: {main_words[0]}")
        
        # Check density calculation
        # Simulate the logic
        rect = {'x0': 325.984, 'top': 96.0, 'x1': 575.433, 'bottom': 660.0}
        bbox = (rect['x0'], rect['top'], rect['x1'], rect['bottom'])
        cropped = p.crop(bbox)
        text = cropped.extract_text()
        print(f"
Extracted text from rect length: {len(text) if text else 0}")
        if text:
            print(f"Start of text: {text[:50]}...")
            area = (rect['x1'] - rect['x0']) * (rect['bottom'] - rect['top'])
            density = len(text.strip()) / area
            print(f"Density: {density}")
            print(f"Threshold: 0.008")
            print(f"Passes? {density >= 0.008}")

if __name__ == "__main__":
    inspect_page_4_structure()

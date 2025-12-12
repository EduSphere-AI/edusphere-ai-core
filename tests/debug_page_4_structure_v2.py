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
            
        words = p.extract_words()
        
        # Check "Box 1"
        box_words = [w for w in words if "Box" in w['text']]
        for w in box_words:
             print(f"'Box' found at: {w}")
             
        # Check "Projection"
        proj_words = [w for w in words if "Projection" in w['text']]
        if proj_words:
            print(f"'Projection' found at: {proj_words[0]}")
            
        # Check density calculation
        # Simulate the logic
        rect = {'x0': 325.984, 'top': 96.0, 'x1': 575.433, 'bottom': 660.0}
        bbox = (rect['x0'], rect['top'], rect['x1'], rect['bottom'])
        cropped = p.crop(bbox)
        text = cropped.extract_text()
        print(f"\nExtracted text from rect length: {len(text) if text else 0}")
        if text:
            print(f"Start of text: {text[:50]}...")
            area = (rect['x1'] - rect['x0']) * (rect['bottom'] - rect['top'])
            density = len(text.strip()) / area
            print(f"Density: {density}")
            print(f"Threshold: 0.008")
            print(f"Passes? {density >= 0.008}")

if __name__ == "__main__":
    inspect_page_4_structure()

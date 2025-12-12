import pdfplumber
import sys

def inspect_page_4_rects():
    pdf_path = "data/input.pdf"
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 4:
            print("PDF has fewer than 4 pages")
            return
            
        page = pdf.pages[3] # Page 4
        print(f"Page 4 size: {page.width}x{page.height}")
        
        print(f"Number of rects: {len(page.rects)}")
        
        # Filter relevant rects (likely the gray box)
        # Box 1 is on the right side.
        page_width = float(page.width)
        right_half_start = page_width * 0.5
        
        potential_box_rects = []
        for i, rect in enumerate(page.rects):
            x0, top, x1, bottom = rect['x0'], rect['top'], rect['x1'], rect['bottom']
            w = x1 - x0
            h = bottom - top
            
            # Check if it's on the right side and has significant size
            if x0 > right_half_start * 0.8 and w > 50 and h > 50:
                print(f"Rect {i}: x={x0:.1f}, y={top:.1f}, w={w:.1f}, h={h:.1f}")
                potential_box_rects.append(rect)
                
                # Try to extract text from this rect
                try:
                    cropped = page.crop((x0, top, x1, bottom))
                    text = cropped.extract_text()
                    print(f"  Text preview: {text[:50]}..." if text else "  No text")
                    
                    # Check density
                    area = w * h
                    char_count = len(text.strip()) if text else 0
                    density = char_count / area if area > 0 else 0
                    print(f"  Density: {density:.5f}")
                except Exception as e:
                    print(f"  Error extracting text: {e}")

if __name__ == "__main__":
    inspect_page_4_rects()

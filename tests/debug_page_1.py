import pdfplumber
import sys

def analyze_page(page_num):
    print(f"--- Analyzing Page {page_num} ---")
    with pdfplumber.open("data/input.pdf") as pdf:
        page = pdf.pages[page_num - 1]
        width, height = float(page.width), float(page.height)
        page_area = width * height
        
        print(f"Page Size: {width}x{height}")
        
        print(f"Rects found: {len(page.rects)}")
        for i, rect in enumerate(page.rects):
            x0, top, x1, bottom = rect['x0'], rect['top'], rect['x1'], rect['bottom']
            w = x1 - x0
            h = bottom - top
            area = w * h
            
            if area < page_area * 0.03:
                continue
                
            print(f"\nRect {i}:")
            print(f"  BBox: ({x0:.1f}, {top:.1f}, {x1:.1f}, {bottom:.1f})")
            print(f"  Size: {w:.1f}x{height:.1f} (Area: {area:.1f})")
            
            # Extract text in this rect
            bbox = (x0, top, x1, bottom)
            try:
                cropped = page.crop(bbox)
                text = cropped.extract_text()
                words = cropped.extract_words()
                
                if text:
                    char_count = len(text)
                    word_count = len(words)
                    lines = text.split('\n')
                    line_count = len(lines)
                    
                    print(f"  Text Length: {char_count} chars")
                    print(f"  Word Count: {word_count}")
                    print(f"  Line Count: {line_count}")
                    print(f"  Text Preview: {text[:100].replace(chr(10), ' ')}...")
                    
                    # Calculate density
                    density = char_count / area if area > 0 else 0
                    print(f"  Density: {density:.6f} chars/pixel")
                    
                    # Check for numbers
                    digit_count = sum(c.isdigit() for c in text)
                    digit_ratio = digit_count / char_count if char_count > 0 else 0
                    print(f"  Digit Ratio: {digit_ratio:.2f}")
                    
                else:
                    print("  No text found.")
            except Exception as e:
                print(f"  Error extracting text: {e}")

if __name__ == "__main__":
    analyze_page(1)
    analyze_page(2)

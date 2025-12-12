import pdfplumber
import re

def inspect_page_4():
    pdf_path = "data/input.pdf"
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 4:
            print("PDF has fewer than 4 pages")
            return
            
        page = pdf.pages[3] # Page 4 (0-indexed is 3)
        print(f"Page 4 size: {page.width}x{page.height}")
        
        words = page.extract_words(extra_attrs=["fontname", "size"])
        
        # Find the words starting with "6" and "employed"
        target_words = []
        for i, word in enumerate(words):
            if word["text"] == "6" and i+1 < len(words) and "employed" in words[i+1]["text"]:
                target_words.append(word)
                target_words.append(words[i+1])
                break
            # Also check if "6" is attached to "employed" or something
            if "6" in word["text"] and "employed" in word["text"]:
                 target_words.append(word)
                 break
        
        if not target_words:
            # Try searching for the string content
            print("Could not find exact match for '6 employed', dumping top elements...")
            for word in words[:20]:
                print(word)
        else:
            print("Found target text:")
            for w in target_words:
                print(f"Text: '{w['text']}', Size: {w['size']}, Top: {w['top']}, Bottom: {w['bottom']}")
                
            # Calculate baseline font size for the page
            all_sizes = [w["size"] for w in words]
            from collections import Counter
            if all_sizes:
                common_size = Counter(all_sizes).most_common(1)[0][0]
                print(f"Page Baseline Font Size: {common_size}")

if __name__ == "__main__":
    inspect_page_4()

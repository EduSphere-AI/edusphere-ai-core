import pdfplumber
import sys

def inspect_page_3():
    pdf_path = "data/input.pdf"
    target_text = "In comparative economic analyses, economic power is generally measured using (price-adjusted) gross value added per"
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) < 3:
            print("PDF has fewer than 3 pages")
            return
            
        page = pdf.pages[2] # Page 3 (0-indexed is 2)
        print(f"Page 3 size: {page.width}x{page.height}")
        
        # Find the element
        words = page.extract_words(extra_attrs=["fontname", "size"])
        
        # Group words into lines/blocks roughly
        # This is just a quick check, so I'll look for the specific text
        
        found = False
        for word in words:
            if "comparative" in word["text"] and "economic" in word["text"]: # heuristic
                 pass
        
        # Let's just print all text with font sizes in the bottom half of the page
        print("\n--- Elements in bottom half of Page 3 ---")
        
        # We can use the same logic as the extractor to get "elements" roughly
        # But simpler: just iterate words and print stats for the target text
        
        # Reconstruct the line for the target text
        target_words = []
        for word in words:
            if word["top"] > page.height * 0.6: # Bottom 40%
                # Check if this word is part of our target string
                if word["text"] in target_text.split():
                    target_words.append(word)
        
        if target_words:
            # Calculate average font size for these words
            sizes = [w["size"] for w in target_words]
            avg_size = sum(sizes) / len(sizes)
            min_top = min(w["top"] for w in target_words)
            max_bottom = max(w["bottom"] for w in target_words)
            
            print(f"Target text found.")
            print(f"Average Font Size: {avg_size}")
            print(f"Position (Top): {min_top}")
            print(f"Relative Y: {min_top / page.height}")
            print(f"Sample word: {target_words[0]}")
            
        # Also calculate baseline font size for the page
        all_sizes = [w["size"] for w in words]
        from collections import Counter
        if all_sizes:
            common_size = Counter(all_sizes).most_common(1)[0][0]
            print(f"Page Baseline Font Size: {common_size}")

if __name__ == "__main__":
    inspect_page_3()

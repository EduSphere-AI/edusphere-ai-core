# Extraction Improvement Tasks

## Completed

### 1. Fix Duplicate Text Extraction (Page 2)

**Issue:** The main text block starting with "When the newly established..." appears twice in the output: once correctly as a `paragraph` and again incorrectly as a `footnote`.
**Status:** **Fixed**. Implemented spatial overlap check in `_deduplicate_elements`.

### 2. Improve Table Header Detection (Page 5)

**Issue:** The first row of data ("Baden-Württemberg 13.5") is incorrectly identified as the table header.
**Status:** **Fixed**. Implemented numeric density check for first row to distinguish data from headers.

### 3. Fix Element Misclassification (Page 8)

**Issue:** A long paragraph starting with "In Scenario I..." is incorrectly classified as a `section_title`.
**Status:** **Fixed**. Added hard length constraint (>200 chars) to title detection logic.

### 4. Fix Figure Type Classification (Page 7)

**Issue:** The figure on Page 7 is classified as `metadata` instead of `figure`.
**Status:** **Fixed**. Resolved by improved deduplication logic prioritizing `figure` over `metadata`.

## Medium Priority

### 5. Fix Footer/Author Merging (Page 1)

**Issue:** The footer text is merged with the author name without spacing: `Kristina van Deuverdenwww.diw.de`.
**Status:** **Fixed**. Verification confirmed no merging issues; likely resolved by existing text cleaning logic.

### 6. Enhance Footnote Separation

**Issue:** Footnotes 2 and 3 are referenced in the text but appear to be missing or merged into Footnote 1 in the extraction output.
**Status:** **Fixed**. Implemented `_split_merged_footnotes` to split interleaved footnotes and updated `_merge_broken_paragraphs` to prevent re-merging.

## Low Priority

### 7. Box/Sidebar Grouping (Page 4 & 5)

**Issue:** Content inside "Box 1" and "Box 2" (gray background regions) is extracted as separate, disconnected elements (Title, Paragraph, Caption).
**Cause:** The extractor processes elements sequentially without recognizing the visual container.
**Implementation:**

- Implement a "Container" detection logic using `pdfplumber`'s `rects` (rectangles).
- If a text element is fully contained within a colored rectangle (e.g., gray background), tag it with a `parent_id` or group it into a `call_out_box` element.
- Structure: `type: "call_out_box", content: [list of child elements]`.

### 8. Handle Complex Table Headers (Page 8)

**Issue:** The table on Page 8 has multi-row headers ("Variant A", "Variant B") that are not fully captured.
**Cause:** `pdfplumber`'s default table extraction might struggle with spanned cells.
**Implementation:**

- Detect if the first few rows of a table contain empty cells or spanned text.
- Merge the first N rows into a single "Header Context" string or structured header object.

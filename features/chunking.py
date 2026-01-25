import json
from typing import List, Dict, Any, Optional
from enum import Enum
import math

# Try to import tokenizer, fallback to simple estimation
try:
    from transformers import AutoTokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


class ChunkingStrategy(Enum):
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    HIERARCHICAL = "hierarchical"


class Chunker:

    def __init__(self,
                 strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
                 max_tokens: int = 512,
                 overlap: int = 50,
                 model_name: str = "bert-base-uncased",
                 use_tokenizer: bool = False):
        self.strategy = strategy
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.tokenizer = None

        if use_tokenizer and HAS_TRANSFORMERS:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            except Exception as e:
                print(f"Warning: Could not load tokenizer {model_name}: {e}")
                self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text, add_special_tokens=False))
        else:
            # Rough estimation: 1 token ~= 4 characters (approx 0.75 words)
            return math.ceil(len(text) / 4)

    def process(self, extraction_result: Dict[str,
                                              Any]) -> List[Dict[str, Any]]:
        """
        Process extraction result and return a list of chunks.
        """
        chunks = []

        # Flatten all elements with their metadata
        all_elements = []
        for page in extraction_result.get('pages', []):
            page_num = page['page_number']
            for elem in page.get('elements', []):
                elem['page_number'] = page_num
                all_elements.append(elem)

        if self.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._semantic_chunking(all_elements)
        else:
            # Default fallback
            chunks = self._fixed_size_chunking(all_elements)

        return chunks

    def _semantic_chunking(
            self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Group elements semantically (e.g. Title + Paragraphs).
        Respects max_tokens.
        """
        chunks = []
        current_chunk = {
            "content": "",
            "elements": [],
            "metadata": {
                "page_numbers": set(),
                "element_types": set()
            },
            "token_count": 0
        }

        for elem in elements:
            content = elem.get('content', '').strip()
            if not content:
                continue

            elem_type = elem.get('type', 'unknown')
            elem_tokens = self.count_tokens(content)

            # Decisions to start a new chunk:
            # 1. If adding this element exceeds max_tokens
            # 2. If this element is a major Section Title (and current chunk is not empty)
            # 3. If element is a Table or Figure (might want standalone chunk)

            is_major_header = elem_type in ['title', 'section_title', 'header']
            is_special = elem_type in ['table', 'figure']
            will_exceed = (current_chunk['token_count'] +
                           elem_tokens) > self.max_tokens

            if (will_exceed or
                (is_major_header and current_chunk['token_count'] > 50)
                    or is_special) and current_chunk['elements']:
                # Finalize current chunk
                self._finalize_chunk(current_chunk, chunks)
                # Reset
                current_chunk = {
                    "content": "",
                    "elements": [],
                    "metadata": {
                        "page_numbers": set(),
                        "element_types": set()
                    },
                    "token_count": 0
                }

            # Add element to current chunk
            if current_chunk['content']:
                current_chunk['content'] += "\n\n"
            current_chunk['content'] += content
            current_chunk['elements'].append(elem)
            current_chunk['metadata']['page_numbers'].add(elem['page_number'])
            current_chunk['metadata']['element_types'].add(elem_type)
            current_chunk['token_count'] += elem_tokens

            # If the element itself is huge (larger than max_tokens), we might need to split it
            # For now, we keep it as one oversized chunk or let the next iteration handle it (it's already added)
            # If it was special (Table/Figure), we force a break immediately after
            if is_special:
                self._finalize_chunk(current_chunk, chunks)
                current_chunk = {
                    "content": "",
                    "elements": [],
                    "metadata": {
                        "page_numbers": set(),
                        "element_types": set()
                    },
                    "token_count": 0
                }

        # Finalize last chunk
        if current_chunk['elements']:
            self._finalize_chunk(current_chunk, chunks)

        return chunks

    def _finalize_chunk(self, chunk: Dict, chunks_list: List):
        # Convert sets to lists for JSON serialization
        chunk['metadata']['page_numbers'] = list(
            chunk['metadata']['page_numbers'])
        chunk['metadata']['element_types'] = list(
            chunk['metadata']['element_types'])
        chunk['id'] = f"chunk_{len(chunks_list)}"
        chunks_list.append(chunk)

    def _fixed_size_chunking(
            self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Simple fixed-size chunking ignoring element boundaries mostly.
        Respects word boundaries to avoid splitting words.
        """
        chunks = []
        full_text = "\n\n".join(
            [e.get('content', '') for e in elements if e.get('content')])

        current_pos = 0
        text_len = len(full_text)
        chunk_char_limit = self.max_tokens * 4  # Approx 4 chars per token

        chunk_idx = 0
        while current_pos < text_len:
            end_pos = min(current_pos + chunk_char_limit, text_len)

            # Optimization: Adjust end_pos to avoid splitting words
            if end_pos < text_len:
                # Look for the last whitespace within the limit
                last_space = full_text.rfind(' ', current_pos, end_pos)
                if last_space != -1:
                    end_pos = last_space + 1  # Include the space

            chunk_text = full_text[current_pos:end_pos]

            chunks.append({
                "id": f"chunk_{chunk_idx}",
                "content": chunk_text,
                "metadata": {
                    "strategy": "fixed_size",
                    "start_char": current_pos,
                    "end_char": end_pos
                },
                "token_count": self.count_tokens(chunk_text)
            })

            # Calculate next position with overlap
            # We also want to ensure the overlap start is at a word boundary if possible
            next_pos = end_pos - (self.overlap * 4)
            if next_pos < current_pos:  # Ensure forward progress
                next_pos = current_pos + 1

            # Adjust next_pos to start at a word boundary
            if next_pos < text_len and next_pos > 0:
                # Find the previous space to start cleanly
                prev_space = full_text.rfind(' ', 0, next_pos)
                if prev_space != -1:
                    next_pos = prev_space + 1

            current_pos = next_pos
            chunk_idx += 1

        return chunks


if __name__ == "__main__":
    # Test stub
    pass

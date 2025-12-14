from typing import Any, Dict, List, Optional, Tuple
import re

from transformers import pipeline

from .config import Config


class NLPProcessor:


    def __init__(self) -> None:
        print("Loading NLP Models (this may take a while)...")

        self.summarizer = None
        self.qg_pipeline = None
        self.models_loaded = False
        self.qg_available = False

        # -----------------------------------------------------
        # SUMMARIZER
        # -----------------------------------------------------
        try:
            self.summarizer = pipeline(
                "summarization",
                model=Config.SUMMARIZER_MODEL,
            )
        except Exception as e:
            print(f"[NLP] Failed to load summarizer: {e}")
            self.summarizer = None

        # -----------------------------------------------------
        # QUESTION GENERATION (QG)
        # -----------------------------------------------------
        try:
            if Config.ENABLE_QG:
                self.qg_pipeline = pipeline(
                    "text2text-generation",
                    model=Config.QG_MODEL,
                )
                self.qg_available = True
            else:
                self.qg_pipeline = None
                self.qg_available = False
        except Exception as e:
            print(f"[NLP] Failed to load QG model: {e}")
            self.qg_pipeline = None
            self.qg_available = False

        self.models_loaded = bool(self.summarizer or self.qg_available)
        print(
            f"[NLP] NLP models loaded "
            f"(summarizer: {self.summarizer is not None}, "
            f"QG: {self.qg_available})."
        )

        # -----------------------------------------------------
        # QUIZ GENERATOR
        # -----------------------------------------------------
        self.quiz_backend: Optional[str] = None
        self.questgen_qg: Any = None

        try:
            enable_quizzes = getattr(Config, "ENABLE_QUIZZES", False)
            quiz_backend = getattr(Config, "QUIZ_BACKEND", "").lower()

            if enable_quizzes and quiz_backend == "questgen":
                from Questgen import main as quest_main  # type: ignore
                self.questgen_qg = quest_main.QGen()
                self.quiz_backend = "questgen"
                print("[NLP] Questgen quiz generator loaded.")
            else:
                if enable_quizzes:
                    print(
                        "[NLP] Quiz generation enabled, but QUIZ_BACKEND is not 'questgen'; "
                        "no external quiz backend initialised (internal fallback will be used)."
                    )
        except Exception as e:
            print(f"[NLP] Failed to initialise Questgen quiz generator: {e}")
            self.questgen_qg = None
            self.quiz_backend = None

        # -----------------------------------------------------
        # GLOBAL BAN LISTS FOR QUESTIONS
        # -----------------------------------------------------
        self._banned_question_substrings = {
            "weekly report",
            "diw weekly",
            "weekly important",
            "at a glance",
            "issn",
            "newsletter",
            "newsletter_en",
            "newsletter_de",
            "kundenservice",
            "customer service",
            "editorial",
            "legal notice",
            "legal information",
            "legal and editorial details",
            "legal and editorial",
            "imprint",
            "reprint and further distribution",
            "further distribution",
            "privacy policy",
            "www.",
            "http://",
            "https://",
            "pdf file",
            "study question",
            "study questions",
            "doi.org",
            "cnn.com",
            "cnncom",
            "cnn",
            "travel snapshots",
            "snapshot",
            "snapshots",
            "photo",
            "photos",
            "gallery",
            "watch video",
            "new jersey",
            "new york",
            "united states",
            "u.s.",
            "u. s.",
            "usa",
        }
        self._banned_question_tokens = {
            "weekly",
            "report",
            "glance",
            "legal",
            "editorial",
            "newsletter",
            "kundenservice",
            "service",
            "imprint",
            "issn",
            "diw",
            "page",
            "media",
            "gmbh",
            "kg",
            "berlin",
            "germany",
            "doi",
            "org",
            "cnn",
            "photo",
            "photos",
            "snapshot",
            "snapshots",
            "gallery",
            "has",
            "is",
            "are",
            "was",
            "were",
            "been",
            "being",
            "presents",
            "present",
            "compared",
            "high",
            "higher",
            "highest",
            "low",
            "lower",
            "lowest",
            "rate",
            "rates",
            "one",
            "two",
            "three",
        }


        self.doc_specific_banned_keywords: set[str] = set()

    def _looks_like_numeric_block(self, text: str) -> bool:

        if not text:
            return False

        tokens = re.findall(r"\S+", text)
        if not tokens:
            return False

        num_tokens = sum(any(ch.isdigit() for ch in tok) for tok in tokens)
        if num_tokens >= 5 and num_tokens >= len(tokens) / 4:
            return True
        return False

    # ------------------------------------------------------------------
    # DOCUMENT-LEVEL
    # ------------------------------------------------------------------
    def register_document_text(self, full_text: str) -> None:

        txt = (full_text or "").lower()
        banned: set[str] = set()


        url_tokens = re.findall(r"(https?://[^\s]+|www\.[^\s]+)", txt)
        for u in url_tokens:
            banned.add(u)
            parts = re.split(r"[./@\-_:]+", u)
            banned.update(p for p in parts if len(p) > 2)

        emails = re.findall(r"[a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+", txt)
        for e in emails:
            parts = re.split(r"[./@\-_:]+", e)
            banned.update(p for p in parts if len(p) > 2)


        name_patterns = re.findall(r"[a-z]{3,}(?:\s+[a-z]{2,}){1,3}", txt)
        for npat in name_patterns:
            if "kristina" in npat or "deuverden" in npat:
                banned.add(npat.strip())

        if "deutsches institut" in txt:
            banned.add("deutsches institut")
            banned.add("diw berlin")
            banned.add("deutsches institut für wirtschaftsforschung")
            banned.add("institut")

        if "hartmann" in txt or "heinz gmbh" in txt:
            banned.add("hartmann")
            banned.add("heinz")
            banned.add("hartmann heinz gmbh")

        for marker in ["newsletter", "newsletter_en", "newsletter_de"]:
            if marker in txt:
                banned.add(marker)

        for marker in ["tel", "fax", "mailto"]:
            if marker in txt:
                banned.add(marker)

        banned = {b for b in banned if len(b) >= 4}

        self.doc_specific_banned_keywords = banned
        if banned:
            print(
                "[NLP] Document-specific banned keywords detected: "
                f"{sorted(self.doc_specific_banned_keywords)}"
            )

    # ------------------------------------------------------------------
    # SUMMARISATION
    # ------------------------------------------------------------------
    def summarize(
        self,
        text: str,
        max_chars: Optional[int] = None,
        max_length: int = 160,
        min_length: int = 60,
        **kwargs,
    ) -> str:
        """
        Summarise text.
        """
        if not self.summarizer or not text:
            return ""

        input_text = (text or "").strip()
        if not input_text:
            return ""

        if max_chars is not None and max_chars > 0:
            input_text = input_text[:max_chars]

        input_text = input_text[:4096]

        try:
            out = self.summarizer(
                input_text,
                max_length=max_length,
                min_length=min_length,
                do_sample=False,
            )
            if out and isinstance(out, list):
                return out[0].get("summary_text", "").strip()
        except Exception as e:
            print(f"[NLP] Summarisation failed: {e}")

        return input_text[:300] + "..."

    def summarize_ocr_items(
        self,
        ocr_items: List[dict],
        max_chars: Optional[int] = None,
        max_length: int = 80,
        min_length: int = 30,
    ) -> str:

        if not ocr_items:
            return ""

        pieces: List[str] = []
        for item in ocr_items:
            t = (item or {}).get("text", "")
            if t and t.strip():
                pieces.append(t.strip())

        text = " ".join(pieces)
        if not text:
            return ""

        return self.summarize(
            text,
            max_chars=max_chars or Config.FIGURE_MAX_CHARS,
            max_length=max_length or Config.FIGURE_SUMMARY_MAX,
            min_length=min_length or Config.FIGURE_SUMMARY_MIN,
        )

    # ------------------------------------------------------------------
    # QUESTION
    # ------------------------------------------------------------------
    def _extract_keywords(self, text: str, max_keywords: int = 25) -> List[str]:

        text = (text or "").lower()
        words = re.findall(r"\b[\w\-]+\b", text)


        stopwords = {
            "the",
            "and",
            "of",
            "to",
            "in",
            "for",
            "on",
            "at",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "by",
            "as",
            "with",
            "from",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
            "be",
            "or",
            "if",
            "but",
            "into",
            "their",
            "they",
            "them",
            "we",
            "our",
            "you",
            "your",
            "can",
            "could",
            "may",
            "might",
            "will",
            "would",
            "should",
            "also",
        }


        header_stopwords = {
            "diw",
            "weekly",
            "report",
            "volume",
            "vol",
            "issue",
            "media",
            "berlin",
            "germany",
            "page",
            "figure",
            "table",
            "section",
            "chapter",
            "subchapter",
            "source",
            "newsletter",
            "newsletter_en",
            "newsletter_de",
            "issn",
            "kg",
            "gmbh",
            "editorial",
            "service",
            "kundenservice",
            "legal",
            "imprint",
            "www",
            "de",
            "en",
            "pdf",
            "https",
            "http",
            "doi",
            "org",
            "slide",
            "slides",
            "result",
            "results",
            "main",
            "commentary",
            "interpretation",
            "relative",
            "variant",
            "development",
            "assumes",
            "assumed",
            "assumptions",
            "introduces",
            "introduction",
        }

        stopwords |= header_stopwords


        banned_tokens = set(self._banned_question_tokens) | {
            "question",
            "questions",
            "study",
            "generated",
            "generate",
            "quiz",
            "quizzes",
            "mcq",
            "mcqs",
        }

        keywords: List[str] = []
        max_kw = max_keywords if max_keywords and max_keywords > 0 else 25

        i = 0
        n = len(words)
        while i < n and len(keywords) < max_kw:
            w = words[i]


            if w.isdigit() or re.fullmatch(r"\d+[.,]?\d*", w):
                i += 1
                continue


            if w in stopwords or w in banned_tokens:
                i += 1
                continue


            if w in self.doc_specific_banned_keywords:
                i += 1
                continue

            bigram_added = False
            raw_bigram = None

            if i + 1 < n:
                w2 = words[i + 1]


                if not (w2.isdigit() or re.fullmatch(r"\d+[.,]?\d*", w2)):
                    if (
                        w2 not in stopwords
                        and w2 not in banned_tokens
                        and w2 not in self.doc_specific_banned_keywords
                    ):
                        raw_bigram = f"{w} {w2}"
                        if (
                            len(raw_bigram.replace(" ", "")) >= Config.QG_KEYWORD_MIN_LEN
                            and raw_bigram not in self.doc_specific_banned_keywords
                        ):
                            if raw_bigram not in keywords:
                                keywords.append(raw_bigram)
                                bigram_added = True


            if not bigram_added:
                if len(w) >= Config.QG_KEYWORD_MIN_LEN and w not in keywords:
                    keywords.append(w)

            i += 1

        return keywords

    def _normalize_question(self, q: str) -> str:
        q = (q or "").strip()
        q = re.sub(r"^(q(uestion)?\s*[:\-]\s*)", "", q, flags=re.IGNORECASE).strip()
        if q and not q.endswith("?"):
            q = q + "?"
        return q

    def _looks_like_boilerplate(self, text: str) -> bool:

        t = (text or "").lower()

        boilerplate_markers = [
            "issn",
            "newsletter_en",
            "newsletter_de",
            "newsletter",
            "reprint and further distribution",
            "further distribution",
            "customer service",
            "kundenservice",
            "imprint",
            "legal notice",
            "legal information",
            "legal and editorial details",
            "legal and editorial",
            "editorial team",
            "editorial office",
            "composition",
            "cover design",
            "satz-rechen-zentrum",
            "hartmann+heinz gmbh",
            "www.diw.de",
            "@diw.de",
            "diw weekly report",
            "diw berlin",
        ]

        hits = sum(1 for m in boilerplate_markers if m in t)
        return hits >= 2

    def _question_is_valid(self, q: str, keywords: List[str]) -> bool:

        if not q:
            return False

        q = " ".join(str(q).split()).strip()
        if not q:
            return False

        tokens = q.split()
        if len(tokens) < Config.QG_MIN_TOKENS:
            return False

        q_lower = q.lower()

        for bad in self._banned_question_substrings:
            if bad in q_lower:
                return False

        if any(bt in q_lower for bt in self._banned_question_tokens):
            return False

        if keywords:
            if not any(kw in q_lower for kw in keywords):

                if not re.search(r"\b(subchapter|section|this page|this part)\b", q_lower):
                    return False
        else:

            return False

        alpha_chars = sum(ch.isalpha() for ch in q)
        total_chars = max(len(q), 1)
        if alpha_chars / total_chars < Config.QG_MIN_ALPHA_FRACTION:
            return False

        return True

    def _generate_generic_page_questions(self, count: int) -> List[str]:

        if count is None or count <= 0:
            count = getattr(Config, "QG_DEFAULT_COUNT", 3)

        templates = [
            "What are the main points discussed on this page?",
            "Which key ideas or messages should you remember from this section?",
            "How does the information on this page relate to the overall topic of the document?",
            "Why might the details on this page be important for readers?",
        ]

        questions: List[str] = []
        for t in templates:
            if len(questions) >= count:
                break
            questions.append(t)

        return questions

    def _generate_heuristic_questions(
        self,
        text: str,
        count: int,
        keywords: Optional[List[str]] = None,
    ) -> List[str]:

        text = (text or "").strip()
        if not text:
            return []

        if count is None or count <= 0:
            count = getattr(Config, "QG_DEFAULT_COUNT", 3)

        if not keywords:
            keywords = self._extract_keywords(text)

        if not keywords:
            return self._generate_generic_page_questions(count)

        questions: List[str] = []
        seen_lower = set()

        domain_concepts = {
            "fiscal capacity",
            "equalization",
            "equalisation",
            "redistribution",
            "tax",
            "taxes",
            "tax revenue",
            "revenue",
            "population",
            "immigration",
            "migration",
            "scenario",
            "variant",
        }

        max_keywords_used = min(len(keywords), 4)

        for kw in keywords[:max_keywords_used]:
            kw_str = str(kw).strip()
            if not kw_str:
                continue

            kw_lower = kw_str.lower()

            if " " in kw_str:
                templates = [
                    "What are the main findings about {kw} in this subchapter?",
                    "Why is {kw} important for the issues discussed in this section?",
                    "How is {kw} expected to develop according to the text?",
                ]
            else:
                templates = [
                    "What does {kw} mean in this context?",
                    "Why is {kw} important in this discussion?",
                ]
                if kw_lower in domain_concepts:
                    templates.append(
                        "Which factors influence {kw} according to the text?"
                    )

            for tmpl in templates:
                q = tmpl.format(kw=kw_str)
                if not q:
                    continue

                if not self._question_is_valid(q, keywords):
                    continue

                q_lowered = q.lower()
                if q_lowered in seen_lower:
                    continue

                seen_lower.add(q_lowered)
                questions.append(q)
                if len(questions) >= count:
                    break

            if len(questions) >= count:
                break

        if not questions:
            return self._generate_generic_page_questions(count)

        return questions

    # ------------------------------------------------------------------
    # QUESTION GENERATION
    # ------------------------------------------------------------------
    def generate_questions(
        self,
        text: str,
        count: Optional[int] = None,
        **kwargs,
    ) -> List[str]:

        if count is None or count <= 0:
            count = getattr(Config, "QG_DEFAULT_COUNT", 3)

        text = (text or "").strip()
        if not text:
            return self._generate_generic_page_questions(count)

        lower = text.lower()


        if self._looks_like_boilerplate(lower):
            return self._generate_generic_page_questions(count)

        source_text = text
        keywords = self._extract_keywords(source_text)
        questions: List[str] = []


        template_candidates = self._generate_template_questions(source_text, lower)
        seen_lower: set[str] = set()

        for q in template_candidates:
            if not q:
                continue
            q_norm = " ".join(str(q).split()).strip()
            if not q_norm:
                continue
            if not q_norm.endswith("?"):
                q_norm = q_norm.rstrip(" ?") + "?"
            q_lower = q_norm.lower()

            if q_lower in seen_lower:
                continue
            if not self._question_is_valid(q_lower, keywords):
                continue

            seen_lower.add(q_lower)
            questions.append(q_norm)
            if len(questions) >= count:
                break


        if len(questions) < count:
            needed = count - len(questions)
            heuristic_qs = self._generate_heuristic_questions(
                source_text,
                count=needed,
                keywords=keywords,
            )
            for q in heuristic_qs:
                if not q:
                    continue
                q_norm = " ".join(str(q).split()).strip()
                if not q_norm:
                    continue
                if not q_norm.endswith("?"):
                    q_norm = q_norm.rstrip(" ?") + "?"
                q_lower = q_norm.lower()

                if q_lower in seen_lower:
                    continue
                if not self._question_is_valid(q_lower, keywords):
                    continue

                seen_lower.add(q_lower)
                questions.append(q_norm)
                if len(questions) >= count:
                    break


        if len(questions) < count:
            needed = count - len(questions)
            generic_qs = self._generate_generic_page_questions(needed)
            for q in generic_qs:
                if not q:
                    continue
                q_norm = " ".join(str(q).split()).strip()
                if not q_norm:
                    continue
                if not q_norm.endswith("?"):
                    q_norm = q_norm.rstrip(" ?") + "?"
                q_lower = q_norm.lower()

                if q_lower in seen_lower:
                    continue
                if not self._question_is_valid(q_lower, keywords):
                    continue

                seen_lower.add(q_lower)
                questions.append(q_norm)
                if len(questions) >= count:
                    break

        if not questions:
            return self._generate_generic_page_questions(count)

        return questions[:count]

    def _generate_template_questions(self, text: str, lower: str) -> List[str]:

        questions: List[str] = []


        has_scenario = "scenario i" in lower or "scenario  i" in lower or "scenario ii" in lower
        has_variant_a = "variant a" in lower
        has_variant_b = "variant b" in lower
        has_variant_c = "variant c" in lower
        has_variants = has_variant_a or has_variant_b or has_variant_c

        has_east = "eastern german" in lower or "east german" in lower or "eastern germany" in lower
        has_west = "western german" in lower or "west german" in lower or "western germany" in lower
        has_east_west = has_east and has_west

        has_population = "population" in lower
        has_immigration = "immigration" in lower or "migration" in lower
        has_fiscal_capacity = "fiscal capacity" in lower
        has_tax_revenue = "tax revenue" in lower or "taxes" in lower or "tax system" in lower
        has_equalization = (
            "equalization" in lower
            or "equalisation" in lower
            or "redistribution" in lower
            or "finanzausgleich" in lower
        )

        has_at_a_glance = "at a glance" in lower
        has_from_authors = "from the authors" in lower

        looks_numeric = self._looks_like_numeric_block(text) or "table" in lower or "figure" in lower


        if has_scenario:
            questions.append(
                "How do Scenario I and Scenario II differ in their assumptions about the development of tax revenue across the federal states?"
            )
            questions.append(
                "In Scenario II, why do disparities in fiscal capacity grow more strongly than in Scenario I?"
            )
            questions.append(
                "Which scenario appears more favourable for convergence between financially strong and weak states, and why?"
            )
            questions.append(
                "What might happen to fiscal disparities if the assumptions of Scenario I were realised instead of Scenario II?"
            )


        if has_variants and has_population:
            questions.append(
                "How do population outcomes differ between Variants A, B, and C, and what role does immigration play in these differences?"
            )
        if has_variants and has_fiscal_capacity:
            questions.append(
                "How do the different immigration variants (A, B, and C) affect the fiscal capacity of the German federal states?"
            )
        if has_variants and (has_population or has_fiscal_capacity):
            questions.append(
                "Which variant seems most favourable for reducing long-term disparities between federal states, and why?"
            )
        if has_variants and has_population and has_fiscal_capacity:
            questions.append(
                "What would change for population and fiscal capacity if the immigration assumptions of Variant B were applied to a state currently following Variant A?"
            )


        if has_east_west and has_fiscal_capacity:
            questions.append(
                "How has the fiscal capacity gap between eastern and western German states changed since unification?"
            )
            questions.append(
                "Why do eastern German states still rely more on equalization payments than many western German states?"
            )
            questions.append(
                "In which areas have eastern German states caught up with financially weak western states, and where do significant gaps remain?"
            )


        if has_fiscal_capacity and has_equalization:
            questions.append(
                "How do equalization payments and federal transfers affect differences in fiscal capacity between the federal states?"
            )
            questions.append(
                "Which mechanisms of the fiscal equalization system are particularly important for financially weak states?"
            )


        if has_population and has_immigration:
            questions.append(
                "Why does the assumed level of immigration matter for long-term population development and fiscal capacity in the federal states?"
            )
            questions.append(
                "Which regions benefit most from higher immigration, and why?"
            )
        if has_population and has_fiscal_capacity:
            questions.append(
                "How do projected population changes influence the need for equalization payments between German federal states?"
            )


        if has_at_a_glance:
            questions.append(
                "Which key results are highlighted in the 'At a glance' section?"
            )
            questions.append(
                "How would you summarise the central findings of the report in one or two sentences?"
            )

        if has_from_authors:
            questions.append(
                "What are the main points the authors emphasise in their commentary?"
            )
            questions.append(
                "How do the authors interpret the implications of their results for future policy?"
            )


        if looks_numeric:
            questions.append(
                "Which patterns or differences can you recognise in the table or figure on this page?"
            )
            questions.append(
                "Which federal states stand out in the table or figure, and for what reasons?"
            )
            questions.append(
                "What does the table or figure suggest about long-term developments across the federal states?"
            )


        questions.append(
            "What is the main message of this subchapter in your own words?"
        )
        questions.append(
            "Which developments or trends described in this subchapter might be particularly important for future policy decisions?"
        )

        return questions

    def _extract_candidate_keywords_for_templates(self, text: str, max_keywords: int = 6) -> List[str]:

        if not text:
            return []


        stopwords = {
            "the",
            "and",
            "or",
            "but",
            "if",
            "then",
            "than",
            "a",
            "an",
            "of",
            "in",
            "on",
            "to",
            "for",
            "with",
            "without",
            "as",
            "by",
            "at",
            "from",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "about",
            "into",
            "over",
            "per",
            "per cent",
            "percent",
            "per-cent",
            "page",
            "figure",
            "table",
            "section",
            "chapter",
            "subchapter",
            "has",
            "have",
            "had",
            "do",
            "does",
            "did",
            "presents",
            "present",
            "compared",
            "compare",
            "compares",
            "high",
            "higher",
            "highest",
            "low",
            "lower",
            "lowest",
            "rate",
            "rates",
            "change",
            "changes",
            "changed",
            "changing",
            "increase",
            "increases",
            "increased",
            "increasing",
            "decrease",
            "decreases",
            "decreased",
            "decreasing",
            "trend",
            "trends",
            "many",
            "some",
            "most",
            "few",
            "several",
            "each",
            "every",
            "other",
            "another",
            "one",
            "two",
            "three",
            "four",
            "five",
            "first",
            "second",
            "third",
            "germany",
            "german",
            "state",
            "states",
            "federal",
            "year",
            "years",
            "main",
            "commentary",
            "interpretation",
            "relative",
            "variant",
            "development",
            "assumes",
            "assumed",
            "assumptions",
            "introduces",
            "introduction",
        }


        domain_prefer = {
            "fiscal",
            "capacity",
            "equalization",
            "equalisation",
            "redistribution",
            "tax",
            "taxes",
            "revenue",
            "population",
            "immigration",
            "migration",
            "scenario",
            "variant",
            "east",
            "west",
            "brandenburg",
            "berlin",
            "saxony",
            "thuringia",
            "bavaria",
            "baden-wuerttemberg",
            "north",
            "rhine",
            "westphalia",
        }

        tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-]+", text)
        counts: Dict[str, int] = {}
        first_form: Dict[str, str] = {}

        for tok in tokens:
            if len(tok) < 4:
                continue
            lower = tok.lower()
            if lower in stopwords:
                continue
            counts[lower] = counts.get(lower, 0) + 1
            if lower not in first_form:
                first_form[lower] = tok

        if not counts:
            return []

        def sort_key(item: Tuple[str, int]) -> Tuple[int, int, str]:
            lower, freq = item
            is_domain = 1 if lower in domain_prefer else 0

            return (-is_domain, -freq, lower)

        sorted_items = sorted(counts.items(), key=sort_key)

        keywords: List[str] = []
        for lower, _freq in sorted_items:
            kw = first_form[lower]
            keywords.append(kw)
            if len(keywords) >= max_keywords:
                break

        return keywords


    def generate_quiz_items(
        self,
        text: str,
        base_questions: Optional[List[str]] = None,
        max_items: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        text = (text or "").strip()
        if not text:
            return []

        if max_items is None or max_items <= 0:
            max_items = getattr(Config, "QUIZ_MAX_ITEMS_PER_SUBCHAPTER", 3)

        quiz_items: List[Dict[str, Any]] = []


        if self.quiz_backend == "questgen" and self.questgen_qg is not None:
            try:
                payload = {"input_text": text}
                out = self.questgen_qg.predict_mcq(payload)  # type: ignore
                for q in (out or {}).get("questions", [])[:max_items]:
                    question_text = (q.get("question_statement") or "").strip()
                    answer = (q.get("answer") or "").strip()
                    options = list(q.get("options") or [])

                    if answer and answer not in options:
                        options.append(answer)
                        correct_index = len(options) - 1
                    else:
                        try:
                            correct_index = options.index(answer) if answer else 0
                        except ValueError:
                            correct_index = 0

                    if not question_text or len(options) < 2:
                        continue

                    quiz_items.append(
                        {
                            "type": "mcq",
                            "question": question_text,
                            "options": options,
                            "correct_index": correct_index,
                            "answer": answer,
                            "context": q.get("context", ""),
                        }
                    )
            except Exception as e:
                print(f"[NLP] Questgen MCQ generation failed, falling back: {e}")
                quiz_items = []


        if not quiz_items:
            if not base_questions:
                base_questions = self.generate_questions(
                    text,
                    count=getattr(Config, "QG_DEFAULT_COUNT", 3),
                )

            for q in (base_questions or [])[:max_items]:
                qs = " ".join(str(q).split()).strip()
                if not qs:
                    continue
                quiz_items.append(
                    {
                        "type": "open",
                        "question": qs,
                    }
                )

        return quiz_items
#!/usr/bin/env python3
"""
Anki Card Generator
Converts lecture PDFs into Anki-importable flashcards (cloze + basic Q&A).

Usage:
    python anki_generator.py lecture.pdf
    python anki_generator.py lecture1.pdf lecture2.pdf -o my_cards -d "Physics Semester 1"
    python anki_generator.py lecture.pdf -k YOUR_API_KEY
"""

import os
import sys
import re
import argparse
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    print("Missing dependency: pip install google-generativeai")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("Missing dependency: pip install pdfplumber")
    sys.exit(1)


SYSTEM_PROMPT = """You are an expert university tutor and Anki flashcard creator.
Your job is to convert lecture content into high-quality Anki flashcards that maximise retention.
You are creating cards for a Science/Maths/Engineering student."""

CARD_PROMPT = """Convert the following lecture content into Anki flashcards.

CARD TYPES TO USE:
- CLOZE (preferred): Sentence with one key concept hidden using {{{{c1::hidden text}}}} syntax
  - Use for: definitions, facts, formulas, named theorems, key terms
  - Multiple blanks in one sentence: use c1, c2, c3: "{{{{c1::Newton's}}}} second law states F = {{{{c2::ma}}}}"
  - The surrounding sentence must give enough context to answer correctly
- BASIC (Q&A): Use for processes, comparisons, multi-step explanations, "why" questions
  - Format: Front question TAB Back answer (on a single line)

OUTPUT FORMAT — strictly follow this:
- Cloze cards: prefix with "CLOZE:" then the full cloze text
- Basic cards: prefix with "BASIC:" then Front[TAB]Back

QUALITY RULES:
- One concept per card
- Every key term, formula, definition, law, and process must have a card
- Cards must be self-contained and unambiguous
- Do not write trivial cards about obvious facts
- For formulas: include units where relevant

LECTURE CONTENT:
{content}

Generate the flashcards:"""


def extract_text(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text.strip() + "\n\n"
    return text


def chunk_text(text: str, max_chars: int = 7000) -> list[str]:
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def generate_cards(model: genai.GenerativeModel, chunk: str) -> tuple[list[str], list[str]]:
    prompt = SYSTEM_PROMPT + "\n\n" + CARD_PROMPT.format(content=chunk)
    response = model.generate_content(prompt)
    raw = response.text
    cloze_cards = []
    basic_cards = []

    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("CLOZE:"):
            card = line[6:].strip()
            if "{{c" in card:
                cloze_cards.append(card)
        elif line.upper().startswith("BASIC:"):
            card = line[6:].strip()
            if "\t" in card:
                basic_cards.append(card)

    return cloze_cards, basic_cards


def deduplicate(cards: list[str]) -> list[str]:
    seen = set()
    result = []
    for card in cards:
        key = re.sub(r'\s+', ' ', card.lower().strip())
        if key not in seen:
            seen.add(key)
            result.append(card)
    return result


def export_cards(
    cloze_cards: list[str],
    basic_cards: list[str],
    output_stem: str,
    deck: str
) -> None:
    output_path = Path(output_stem)

    if cloze_cards:
        cloze_path = output_path.parent / (output_path.stem + "_cloze.txt")
        with open(cloze_path, "w", encoding="utf-8") as f:
            f.write("#separator:tab\n")
            f.write("#html:false\n")
            f.write(f"#deck:{deck}\n")
            f.write("#notetype:Cloze\n")
            f.write("#columns:Text\n")
            for card in cloze_cards:
                f.write(card + "\n")
        print(f"  Cloze file:  {cloze_path}  ({len(cloze_cards)} cards)")

    if basic_cards:
        basic_path = output_path.parent / (output_path.stem + "_basic.txt")
        with open(basic_path, "w", encoding="utf-8") as f:
            f.write("#separator:tab\n")
            f.write("#html:false\n")
            f.write(f"#deck:{deck}\n")
            f.write("#notetype:Basic\n")
            f.write("#columns:Front\tBack\n")
            for card in basic_cards:
                f.write(card + "\n")
        print(f"  Basic file:  {basic_path}  ({len(basic_cards)} cards)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert lecture PDFs into Anki flashcards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("pdfs", nargs="+", help="PDF file(s) to process")
    parser.add_argument("-o", "--output", default="anki_cards",
                        help="Output filename stem (default: anki_cards)")
    parser.add_argument("-d", "--deck", default="Lecture Notes",
                        help="Anki deck name (default: 'Lecture Notes')")
    parser.add_argument("-k", "--api-key",
                        help="Gemini API key (or set GEMINI_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Gemini API key required.")
        print("  Option 1: set GEMINI_API_KEY environment variable")
        print("  Option 2: use -k YOUR_KEY flag")
        print("  Get a free key at: https://aistudio.google.com")
        sys.exit(1)

    genai.configure(api_key=api_key)
    client = genai.GenerativeModel("gemini-2.0-flash")

    all_cloze: list[str] = []
    all_basic: list[str] = []

    for pdf_path in args.pdfs:
        if not Path(pdf_path).exists():
            print(f"Warning: file not found — {pdf_path}")
            continue

        print(f"\nProcessing: {pdf_path}")

        print("  Extracting text from PDF...")
        text = extract_text(pdf_path)
        if not text.strip():
            print("  Warning: no text extracted (PDF may be image-based/scanned)")
            continue
        print(f"  Extracted {len(text):,} characters across {text.count(chr(12)) + 1} pages")

        chunks = chunk_text(text)
        print(f"  Split into {len(chunks)} chunk(s) for processing")

        for i, chunk in enumerate(chunks, 1):
            print(f"  Generating cards — chunk {i}/{len(chunks)}...", end="", flush=True)
            cloze, basic = generate_cards(client, chunk)
            all_cloze.extend(cloze)
            all_basic.extend(basic)
            print(f" {len(cloze)} cloze + {len(basic)} basic")

    if not all_cloze and not all_basic:
        print("\nNo cards generated. Check that your PDFs contain selectable text.")
        sys.exit(1)

    all_cloze = deduplicate(all_cloze)
    all_basic = deduplicate(all_basic)

    print(f"\nTotal (after dedup): {len(all_cloze)} cloze + {len(all_basic)} basic cards")
    print("\nExporting:")
    export_cards(all_cloze, all_basic, args.output, args.deck)

    print("\nDone! To import into Anki:")
    print("  1. Open Anki")
    print("  2. File > Import")
    print("  3. Select the _cloze.txt and/or _basic.txt file")
    print("  4. Make sure the note type matches (Cloze or Basic)")
    print("  5. Import!")


if __name__ == "__main__":
    main()

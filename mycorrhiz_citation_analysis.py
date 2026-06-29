"""
mycorrhiz_citation_analysis.py

Fetches all papers citing Johnson, Graham & Smith (1997) using the OpenAlex API,
then searches title, abstract, and keywords for "mycorrhiz*" (mycorrhiza,
mycorrhizae, mycorrhizal, etc.).

Output: mycorrhiz_citation_results.csv in the same directory as this script.

Requirements:
    pip install requests

Usage:
    python mycorrhiz_citation_analysis.py
"""

import csv
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Please install the requests library first:\n    pip install requests")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# DOI of the seed paper (Johnson, Graham & Smith 1997)
SEED_DOI = "10.1046/j.1469-8137.1997.00729.x"

# Email — OpenAlex uses this to give you better rate limits (polite pool)
EMAIL = "" #Redacted mine but enter yours here.

BASE_URL = "https://api.openalex.org"
HEADERS = {"User-Agent": f"citation-analysis/1.0 (mailto:{EMAIL})"}
PER_PAGE = 200  # OpenAlex max is 200 per page

# Pattern that matches mycorrhiz* (case-insensitive)
MYCORRHIZ_PATTERN = re.compile(r"mycorrhiz", re.IGNORECASE)

OUTPUT_FILE = Path(__file__).parent / "mycorrhiz_citation_results.csv"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_openalex_id(doi: str) -> str:
    """Look up a paper by DOI and return its OpenAlex work ID."""
    url = f"{BASE_URL}/works"
    params = {"filter": f"doi:{doi}", "select": "id,title,cited_by_count"}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        sys.exit(f"Could not find paper with DOI {doi} in OpenAlex.")
    work = results[0]
    print(f"Seed paper found: {work['title']}")
    print(f"OpenAlex ID: {work['id']}")
    print(f"Citation count (OpenAlex): {work.get('cited_by_count', 'unknown')}\n")
    return work["id"]


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Rebuild abstract text from OpenAlex's inverted index format."""
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[i] for i in sorted(positions))


def fetch_citing_papers(openalex_id: str) -> list[dict]:
    """
    Page through all works that cite the seed paper.
    Returns a list of raw OpenAlex work objects.
    """
    # Strip the URL prefix if present (e.g., "https://openalex.org/W123" -> "W123")
    short_id = openalex_id.split("/")[-1]
    filter_str = f"cites:{short_id}"
    select_fields = (
        "id,doi,title,abstract_inverted_index,keywords,"
        "concepts,publication_year,primary_location,authorships"
    )

    all_works = []
    page = 1
    total = None

    while True:
        params = {
            "filter": filter_str,
            "select": select_fields,
            "per-page": PER_PAGE,
            "page": page,
        }
        resp = requests.get(
            f"{BASE_URL}/works", params=params, headers=HEADERS, timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        if total is None:
            total = data["meta"]["count"]
            print(f"Total citing papers found: {total}")

        batch = data.get("results", [])
        if not batch:
            break

        all_works.extend(batch)
        fetched = len(all_works)
        print(f"  Fetched {fetched}/{total} papers...", end="\r")

        if fetched >= total:
            break

        page += 1
        time.sleep(0.1)  # be polite to the API

    print(f"\nDone fetching. Total retrieved: {len(all_works)}\n")
    return all_works


def contains_mycorrhiz(text: str) -> bool:
    return bool(MYCORRHIZ_PATTERN.search(text))


def process_paper(work: dict) -> dict:
    """Extract relevant fields and run the mycorrhiz* search."""
    title = work.get("title") or ""
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    # Keywords: OpenAlex returns a list of {"id": ..., "display_name": ...} dicts
    raw_keywords = work.get("keywords") or []
    keyword_list = [k.get("display_name", "") for k in raw_keywords]
    keywords_str = "; ".join(keyword_list)

    # Concepts (broader topic tags, useful supplement to keywords)
    raw_concepts = work.get("concepts") or []
    concept_list = [c.get("display_name", "") for c in raw_concepts if c.get("score", 0) > 0.3]
    concepts_str = "; ".join(concept_list)

    # Journal / venue
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    journal = source.get("display_name", "")

    # Authors
    authorships = work.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "") for a in authorships[:10]
    )

    # mycorrhiz* search
    in_title = contains_mycorrhiz(title)
    in_abstract = contains_mycorrhiz(abstract)
    in_keywords = contains_mycorrhiz(keywords_str)
    any_match = in_title or in_abstract or in_keywords

    return {
        "openalex_id": work.get("id", ""),
        "doi": work.get("doi", ""),
        "year": work.get("publication_year", ""),
        "journal": journal,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords_str,
        "concepts": concepts_str,
        "mycorrhiz_in_title": in_title,
        "mycorrhiz_in_abstract": in_abstract,
        "mycorrhiz_in_keywords": in_keywords,
        "mycorrhiz_anywhere": any_match,
    }


def write_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        print("No data to write.")
        return
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV written to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Mycorrhiz* Citation Analysis ===\n")
    print(f"Seed paper DOI: {SEED_DOI}\n")

    # 1. Find seed paper
    openalex_id = get_openalex_id(SEED_DOI)

    # 2. Fetch all citing papers
    citing_works = fetch_citing_papers(openalex_id)

    # 3. Process each paper
    print("Processing papers and running mycorrhiz* search...")
    processed = [process_paper(w) for w in citing_works]

    # 4. Summary stats
    n_total = len(processed)
    n_match = sum(1 for p in processed if p["mycorrhiz_anywhere"])
    n_title = sum(1 for p in processed if p["mycorrhiz_in_title"])
    n_abstract = sum(1 for p in processed if p["mycorrhiz_in_abstract"])
    n_keywords = sum(1 for p in processed if p["mycorrhiz_in_keywords"])
    n_no_abstract = sum(1 for p in processed if not p["abstract"])

    print(f"\n=== Results Summary ===")
    print(f"Total citing papers:                  {n_total}")
    print(f"Papers with 'mycorrhiz*' anywhere:    {n_match} ({n_match/n_total*100:.1f}%)")
    print(f"  - in title:                         {n_title}")
    print(f"  - in abstract:                      {n_abstract}")
    print(f"  - in keywords:                      {n_keywords}")
    print(f"Papers with no abstract available:    {n_no_abstract} ({n_no_abstract/n_total*100:.1f}%)")
    print()

    # 5. Write CSV
    write_csv(processed, OUTPUT_FILE)
    print("\nDone.")


if __name__ == "__main__":
    main()

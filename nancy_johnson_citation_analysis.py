"""
nancy_johnson_citation_analysis.py

Fetches all papers citing any work by Nancy Collins Johnson using the
OpenAlex API, then searches title, abstract, and keywords for "mycorrhiz*".

Output: nancy_johnson_citation_results.csv (one row per citing-paper /
cited-work pair, so if paper X cites three of Nancy's papers it appears
three times).

Requirements:
    python -m pip install requests

Usage:
    python nancy_johnson_citation_analysis.py
"""

import csv
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Please install the requests library:\n    python -m pip install requests")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# OpenAlex ID of the known seed paper — used to look up Nancy's author ID
SEED_WORK_ID = "W2119861496"

# Your email for OpenAlex polite pool (better rate limits)
EMAIL = ""  # Enter your email here, e.g. "you@example.com"

BASE_URL = "https://api.openalex.org"
HEADERS = {"User-Agent": f"citation-analysis/1.0 (mailto:{EMAIL})"}
PER_PAGE = 200

MYCORRHIZ_PATTERN = re.compile(r"mycorrhiz", re.IGNORECASE)
OUTPUT_FILE = Path(__file__).parent / "nancy_johnson_citation_results.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def openalex_get(endpoint: str, params: dict) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_author_id(seed_work_id: str) -> tuple[str, str]:
    """
    Pull the first author from the seed paper and return (author_id, author_name).
    We use the seed paper we already know rather than a name search to avoid
    ambiguity.
    """
    data = openalex_get(f"works/{seed_work_id}", {"select": "authorships,title"})
    authorships = data.get("authorships", [])
    if not authorships:
        sys.exit("Could not read authorships from seed paper.")
    first = authorships[0]
    author = first.get("author", {})
    author_id = author.get("id", "").split("/")[-1]  # e.g. "A12345"
    author_name = author.get("display_name", "")
    return author_id, author_name


def get_all_works(author_id: str) -> list[dict]:
    """Fetch all works by the author from OpenAlex."""
    all_works = []
    page = 1
    total = None

    while True:
        params = {
            "filter": f"author.id:{author_id}",
            "select": "id,doi,title,publication_year,cited_by_count",
            "per-page": PER_PAGE,
            "page": page,
        }
        data = openalex_get("works", params)

        if total is None:
            total = data["meta"]["count"]
            print(f"  Total works found: {total}")

        batch = data.get("results", [])
        if not batch:
            break
        all_works.extend(batch)
        if len(all_works) >= total:
            break
        page += 1
        time.sleep(0.1)

    return all_works


def reconstruct_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[i] for i in sorted(positions))


def contains_mycorrhiz(text: str) -> bool:
    return bool(MYCORRHIZ_PATTERN.search(text))


def fetch_citing_papers(work_id: str) -> list[dict]:
    """Page through all citing works for a single paper."""
    short_id = work_id.split("/")[-1]
    select_fields = (
        "id,doi,title,abstract_inverted_index,keywords,"
        "concepts,publication_year,primary_location,authorships"
    )
    all_results = []
    page = 1
    total = None

    while True:
        params = {
            "filter": f"cites:{short_id}",
            "select": select_fields,
            "per-page": PER_PAGE,
            "page": page,
        }
        data = openalex_get("works", params)

        if total is None:
            total = data["meta"]["count"]

        batch = data.get("results", [])
        if not batch:
            break
        all_results.extend(batch)
        if len(all_results) >= total:
            break
        page += 1
        time.sleep(0.1)

    return all_results


def process_citing_paper(work: dict, cited_work: dict) -> dict:
    """Build one CSV row for a (citing paper, cited Nancy-work) pair."""
    title = work.get("title") or ""
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    raw_keywords = work.get("keywords") or []
    keywords_str = "; ".join(k.get("display_name", "") for k in raw_keywords)

    raw_concepts = work.get("concepts") or []
    concepts_str = "; ".join(
        c.get("display_name", "")
        for c in raw_concepts
        if c.get("score", 0) > 0.3
    )

    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    journal = source.get("display_name", "")

    authorships = work.get("authorships") or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "") for a in authorships[:10]
    )

    in_title = contains_mycorrhiz(title)
    in_abstract = contains_mycorrhiz(abstract)
    in_keywords = contains_mycorrhiz(keywords_str)
    any_match = in_title or in_abstract or in_keywords

    return {
        # Which of Nancy's papers was cited
        "cited_work_id": cited_work.get("id", ""),
        "cited_work_doi": cited_work.get("doi", ""),
        "cited_work_year": cited_work.get("publication_year", ""),
        "cited_work_title": cited_work.get("title", ""),
        # The citing paper
        "citing_openalex_id": work.get("id", ""),
        "citing_doi": work.get("doi", ""),
        "citing_year": work.get("publication_year", ""),
        "citing_journal": journal,
        "citing_title": title,
        "citing_authors": authors,
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
    print("=== Nancy Collins Johnson — Full Citation Analysis ===\n")

    # 1. Find author
    print(f"Looking up author from seed paper {SEED_WORK_ID}...")
    author_id, author_name = get_author_id(SEED_WORK_ID)
    print(f"  Author: {author_name}  (OpenAlex ID: {author_id})\n")

    # 2. Get all her works
    print("Fetching all works by this author...")
    all_works = get_all_works(author_id)
    total_works = len(all_works)
    total_cited_by = sum(w.get("cited_by_count", 0) for w in all_works)
    print(f"  Retrieved {total_works} works  (total citation count across all works: {total_cited_by})\n")

    # Sanity-check: show the 10 most-cited works so you can verify the author is correct
    sorted_works = sorted(all_works, key=lambda w: w.get("cited_by_count", 0), reverse=True)
    print("Top 10 most-cited works (verify this is the right author):")
    for w in sorted_works[:10]:
        print(f"  [{w.get('publication_year','')}] ({w.get('cited_by_count',0)} cites) {w.get('title','')[:80]}")
    print()
    confirm = input("Does this look right? Type 'yes' to continue, anything else to abort: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)
    print()

    # 3. Fetch citing papers for each work
    all_rows = []
    for i, work in enumerate(all_works, 1):
        work_title = (work.get("title") or "untitled")[:60]
        n_citing = work.get("cited_by_count", 0)
        print(f"[{i}/{total_works}] {work_title}... ({n_citing} citations)")

        if n_citing == 0:
            continue

        citing = fetch_citing_papers(work.get("id", ""))
        rows = [process_citing_paper(c, work) for c in citing]
        all_rows.extend(rows)
        print(f"         -> {len(citing)} citing papers fetched  (running total rows: {len(all_rows)})")
        time.sleep(0.2)

    print(f"\nTotal rows (citing-paper / cited-work pairs): {len(all_rows)}")

    # 4. Summary
    n_match = sum(1 for r in all_rows if r["mycorrhiz_anywhere"])
    n_no_abstract = sum(1 for r in all_rows if not r["abstract"])
    match_with_abstract    = sum(1 for r in all_rows if r["mycorrhiz_anywhere"] and r["abstract"])
    match_no_abstract      = sum(1 for r in all_rows if r["mycorrhiz_anywhere"] and not r["abstract"])
    no_match_with_abstract = sum(1 for r in all_rows if not r["mycorrhiz_anywhere"] and r["abstract"])
    no_match_no_abstract   = sum(1 for r in all_rows if not r["mycorrhiz_anywhere"] and not r["abstract"])
    n = len(all_rows)

    print(f"\n=== Results Summary ===")
    print(f"Total citing-paper/cited-work pairs:   {n}")
    print(f"mycorrhiz* match anywhere:             {n_match} ({n_match/n*100:.1f}%)")
    print(f"  matched, has abstract:               {match_with_abstract}")
    print(f"  matched via title/keywords only:     {match_no_abstract}")
    print(f"No match, has abstract:                {no_match_with_abstract} ({no_match_with_abstract/n*100:.1f}%)")
    print(f"No match, no abstract (uncertain):     {no_match_no_abstract} ({no_match_no_abstract/n*100:.1f}%)")

    # 5. Write CSV
    write_csv(all_rows, OUTPUT_FILE)
    print("\nDone.")


if __name__ == "__main__":
    main()

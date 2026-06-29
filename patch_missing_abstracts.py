"""
patch_missing_abstracts.py

Reads mycorrhiz_citation_results.csv, finds rows with no abstract,
queries the Semantic Scholar batch API to fill in missing abstracts,
re-runs the mycorrhiz* search, and overwrites the CSV.

Run AFTER mycorrhiz_citation_analysis.py has already produced its CSV.

Requirements:
    python -m pip install requests

Usage:
    python patch_missing_abstracts.py
"""

import csv
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Please install the requests library first:\n    python -m pip install requests")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).parent / "mycorrhiz_citation_results.csv"
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_FIELDS = "abstract"
BATCH_SIZE = 500   # S2 max per request
SLEEP_BETWEEN_BATCHES = 3.0  # seconds — S2 rate limit is generous but be polite

MYCORRHIZ_PATTERN = re.compile(r"mycorrhiz", re.IGNORECASE)


def contains_mycorrhiz(text: str) -> bool:
    return bool(MYCORRHIZ_PATTERN.search(text))


def fetch_s2_abstracts(dois: list[str]) -> dict[str, str]:
    """
    Batch-query Semantic Scholar for abstracts by DOI.
    Returns a dict mapping DOI -> abstract string (or "" if not found).
    """
    doi_to_abstract: dict[str, str] = {}

    for i in range(0, len(dois), BATCH_SIZE):
        batch = dois[i : i + BATCH_SIZE]
        # S2 accepts DOIs prefixed with "DOI:"
        ids = [f"DOI:{doi}" for doi in batch]
        print(f"  Querying Semantic Scholar: papers {i+1}-{min(i+BATCH_SIZE, len(dois))} of {len(dois)}...")

        try:
            resp = requests.post(
                S2_BATCH_URL,
                params={"fields": S2_FIELDS},
                json={"ids": ids},
                timeout=60,
            )
            resp.raise_for_status()
            results = resp.json()
        except requests.RequestException as e:
            print(f"  WARNING: S2 request failed for batch {i}-{i+BATCH_SIZE}: {e}")
            continue

        for doi, item in zip(batch, results):
            if item and isinstance(item, dict):
                abstract = item.get("abstract") or ""
                doi_to_abstract[doi.lower()] = abstract

        if i + BATCH_SIZE < len(dois):
            time.sleep(SLEEP_BETWEEN_BATCHES)

    return doi_to_abstract


def main():
    if not CSV_PATH.exists():
        sys.exit(f"CSV not found: {CSV_PATH}\nRun mycorrhiz_citation_analysis.py first.")

    print(f"Reading {CSV_PATH.name}...")
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total = len(rows)
    missing = [r for r in rows if not r["abstract"] and r["doi"]]
    print(f"Total rows: {total}")
    print(f"Rows with no abstract but with DOI: {len(missing)}\n")

    if not missing:
        print("No missing abstracts to patch. Exiting.")
        return

    # Collect DOIs to look up (strip URL prefix if present)
    def clean_doi(raw: str) -> str:
        return raw.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()

    dois = [clean_doi(r["doi"]) for r in missing]

    print("Fetching abstracts from Semantic Scholar...")
    doi_to_abstract = fetch_s2_abstracts(dois)

    found = sum(1 for v in doi_to_abstract.values() if v)
    print(f"\nAbstracts retrieved: {found} of {len(missing)} queried\n")

    # Patch rows
    patched = 0
    new_mycorrhiz_matches = 0

    for row in rows:
        if row["abstract"] or not row["doi"]:
            continue
        doi_key = clean_doi(row["doi"]).lower()
        new_abstract = doi_to_abstract.get(doi_key, "")
        if not new_abstract:
            continue

        row["abstract"] = new_abstract
        patched += 1

        # Re-run mycorrhiz* search with the new abstract
        was_match = row["mycorrhiz_anywhere"] == "True"
        in_abstract_now = contains_mycorrhiz(new_abstract)
        row["mycorrhiz_in_abstract"] = str(in_abstract_now)

        in_title = row["mycorrhiz_in_title"] == "True"
        in_keywords = row["mycorrhiz_in_keywords"] == "True"
        any_match = in_title or in_abstract_now or in_keywords
        row["mycorrhiz_anywhere"] = str(any_match)

        if any_match and not was_match:
            new_mycorrhiz_matches += 1

    print(f"Abstracts patched into CSV: {patched}")
    print(f"New mycorrhiz* matches discovered: {new_mycorrhiz_matches}")

    # Write updated CSV
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Final summary
    total_match = sum(1 for r in rows if r["mycorrhiz_anywhere"] == "True")
    still_no_abstract = sum(1 for r in rows if not r["abstract"])
    print(f"\n=== Updated Summary ===")
    print(f"Total papers:                        {total}")
    print(f"mycorrhiz* match (updated):          {total_match} ({total_match/total*100:.1f}%)")
    print(f"Still missing abstract:              {still_no_abstract} ({still_no_abstract/total*100:.1f}%)")
    print(f"\nCSV updated: {CSV_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()

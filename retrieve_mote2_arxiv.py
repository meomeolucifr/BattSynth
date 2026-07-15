"""
Retrieve ArXiv records using exactly the phrase query: all:"MoTe2".

Usage:
    python retrieve_mote2_arxiv.py
    python retrieve_mote2_arxiv.py --page-size 200 --max-results 1000 --out mote2_arxiv.json
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def parse_arxiv_feed(xml_text: str) -> List[Dict[str, Any]]:
    """Parse one ArXiv Atom feed page into a list of paper dicts."""
    root = ET.fromstring(xml_text)
    entries: List[Dict[str, Any]] = []

    for entry in root.findall("atom:entry", ARXIV_NS):
        title = (entry.findtext("atom:title", default="", namespaces=ARXIV_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ARXIV_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ARXIV_NS) or "").strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=ARXIV_NS) or "").strip()
        arxiv_id = (entry.findtext("atom:id", default="", namespaces=ARXIV_NS) or "").strip()

        authors = []
        for author in entry.findall("atom:author", ARXIV_NS):
            name = (author.findtext("atom:name", default="", namespaces=ARXIV_NS) or "").strip()
            if name:
                authors.append(name)

        categories = []
        for cat in entry.findall("atom:category", ARXIV_NS):
            term = (cat.attrib.get("term") or "").strip()
            if term:
                categories.append(term)

        entries.append(
            {
                "id": arxiv_id,
                "title": " ".join(title.split()),
                "summary": " ".join(summary.split()),
                "published": published,
                "updated": updated,
                "authors": authors,
                "categories": categories,
            }
        )

    return entries


def fetch_all_mote2(page_size: int, max_results: int) -> List[Dict[str, Any]]:
    """
    Fetch ArXiv results for exactly all:"MoTe2" using pagination.
    """
    query = 'all:"MoTe2"'
    start = 0
    all_records: List[Dict[str, Any]] = []

    try:
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ssl_context = ssl.create_default_context()

    while start < max_results:
        batch_size = min(page_size, max_results - start)
        params = {
            "search_query": query,
            "start": start,
            "max_results": batch_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"

        with urllib.request.urlopen(url, timeout=30, context=ssl_context) as response:
            xml_text = response.read().decode("utf-8", errors="replace")

        page_records = parse_arxiv_feed(xml_text)
        if not page_records:
            break

        all_records.extend(page_records)
        start += len(page_records)

        if len(page_records) < batch_size:
            break

    return all_records


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Retrieve ArXiv results for exactly all:"MoTe2".'
    )
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--max-results", type=int, default=2000)
    parser.add_argument("--out", type=str, default="mote2_arxiv_results.json")
    args = parser.parse_args()

    records = fetch_all_mote2(page_size=args.page_size, max_results=args.max_results)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Query: all:\"MoTe2\"")
    print(f"Retrieved: {len(records)}")
    print(f"Saved to: {args.out}")

    if records:
        print("\nTop 5 titles:")
        for i, rec in enumerate(records[:5], start=1):
            print(f"{i}. {rec['title']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Stage 0: PMC XML Download Pipeline

Downloads PubMed Central (PMC) XML files from NCBI E-utilities API and stores them locally.
Supports downloading by PMC ID list, PubMed search queries, or DOI resolution.

Usage:
    # Download specific PMC IDs
    python download_pipeline.py --pmc-ids PMC123456 PMC234567 --output-dir pmc_xmls

    # Download from a file containing PMC IDs (one per line)
    python download_pipeline.py --pmc-id-file ids.txt --output-dir pmc_xmls

    # Search PubMed and download results
    python download_pipeline.py --search "BRCA1 breast cancer" --max-results 100 --output-dir pmc_xmls

    # Resume interrupted download
    python download_pipeline.py --pmc-id-file ids.txt --output-dir pmc_xmls --skip-existing

NCBI E-utilities Documentation:
    https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import argparse
import time
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
import json

# ============================================================================
# Configuration
# ============================================================================

NCBI_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_ENDPOINT = f"{NCBI_EUTILS_BASE}/efetch.fcgi"
ESEARCH_ENDPOINT = f"{NCBI_EUTILS_BASE}/esearch.fcgi"
ELINK_ENDPOINT = f"{NCBI_EUTILS_BASE}/elink.fcgi"

# NCBI requires rate limiting: max 3 requests/second without API key, 10/second with key
DEFAULT_RATE_LIMIT = 0.34  # seconds between requests (slightly under 3 req/sec)
API_KEY_RATE_LIMIT = 0.11  # seconds between requests with API key (slightly under 10 req/sec)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds


# ============================================================================
# PMC ID Utilities
# ============================================================================


def normalize_pmc_id(pmc_id: str) -> str:
    """
    Normalize PMC ID to standard format.

    Args:
        pmc_id: PMC ID in any format (e.g., "123456", "PMC123456")

    Returns:
        Normalized PMC ID with "PMC" prefix

    Examples:
        >>> normalize_pmc_id("123456")
        'PMC123456'
        >>> normalize_pmc_id("PMC123456")
        'PMC123456'
    """
    pmc_id = pmc_id.strip()
    if not pmc_id.startswith("PMC"):
        pmc_id = f"PMC{pmc_id}"
    return pmc_id


def validate_pmc_id(pmc_id: str) -> bool:
    """
    Validate that a string is a valid PMC ID format.

    Args:
        pmc_id: String to validate

    Returns:
        True if valid PMC ID format
    """
    normalized = normalize_pmc_id(pmc_id)
    # PMC ID should be "PMC" followed by digits
    return normalized.startswith("PMC") and normalized[3:].isdigit()


# ============================================================================
# NCBI E-utilities Functions
# ============================================================================


def search_pubmed(
    query: str,
    max_results: int = 100,
    api_key: Optional[str] = None,
    rate_limit: float = DEFAULT_RATE_LIMIT,
) -> list[str]:
    """
    Search PubMed and return PMC IDs.

    Args:
        query: PubMed search query
        max_results: Maximum number of results to return
        api_key: NCBI API key (optional, increases rate limit)
        rate_limit: Seconds to wait between requests

    Returns:
        List of PMC IDs
    """
    print(f"Searching PubMed for: {query}")

    params = {
        "db": "pmc",  # Search PMC database
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }

    if api_key:
        params["api_key"] = api_key

    url = f"{ESEARCH_ENDPOINT}?{urlencode(params)}"

    try:
        with urlopen(url) as response:
            data = json.loads(response.read().decode())
            id_list = data.get("esearchresult", {}).get("idlist", [])

            # Convert PMCID numbers to PMC format
            pmc_ids = [f"PMC{id}" for id in id_list]

            print(f"  Found {len(pmc_ids)} results")
            time.sleep(rate_limit)
            return pmc_ids

    except HTTPError as e:
        print(f"  Error searching PubMed: {e}")
        return []
    except Exception as e:
        print(f"  Unexpected error: {e}")
        return []


def fetch_pmc_xml(
    pmc_id: str,
    api_key: Optional[str] = None,
    rate_limit: float = DEFAULT_RATE_LIMIT,
    retry_count: int = 0,
) -> Optional[str]:
    """
    Fetch PMC XML from NCBI E-utilities.

    Args:
        pmc_id: PMC ID (e.g., "PMC123456")
        api_key: NCBI API key (optional)
        rate_limit: Seconds to wait between requests
        retry_count: Current retry attempt (for internal use)

    Returns:
        XML content as string, or None if fetch failed
    """
    normalized_id = normalize_pmc_id(pmc_id)

    # Strip "PMC" prefix for NCBI API
    numeric_id = normalized_id[3:]

    params = {
        "db": "pmc",
        "id": numeric_id,
        "retmode": "xml",
    }

    if api_key:
        params["api_key"] = api_key

    url = f"{EFETCH_ENDPOINT}?{urlencode(params)}"

    try:
        with urlopen(url) as response:
            xml_content = response.read().decode("utf-8")
            time.sleep(rate_limit)
            return xml_content

    except HTTPError as e:
        if e.code == 429:  # Too Many Requests
            if retry_count < MAX_RETRIES:
                print(f"  Rate limited, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                return fetch_pmc_xml(pmc_id, api_key, rate_limit, retry_count + 1)
            else:
                print(f"  Max retries exceeded for {normalized_id}")
                return None
        elif e.code == 404:
            print(f"  Not found: {normalized_id}")
            return None
        else:
            print(f"  HTTP error {e.code}: {normalized_id}")
            return None

    except URLError as e:
        if retry_count < MAX_RETRIES:
            print(f"  Network error, retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            return fetch_pmc_xml(pmc_id, api_key, rate_limit, retry_count + 1)
        else:
            print(f"  Network error for {normalized_id}: {e}")
            return None

    except Exception as e:
        print(f"  Unexpected error for {normalized_id}: {e}")
        return None


def save_pmc_xml(pmc_id: str, xml_content: str, output_dir: Path) -> bool:
    """
    Save PMC XML to file.

    Args:
        pmc_id: PMC ID (will be normalized)
        xml_content: XML content to save
        output_dir: Directory to save XML files

    Returns:
        True if saved successfully, False otherwise
    """
    normalized_id = normalize_pmc_id(pmc_id)
    output_path = output_dir / f"{normalized_id}.xml"

    try:
        # Validate XML before saving
        ET.fromstring(xml_content)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        return True

    except ET.ParseError as e:
        print(f"  Invalid XML for {normalized_id}: {e}")
        return False

    except Exception as e:
        print(f"  Error saving {normalized_id}: {e}")
        return False


# ============================================================================
# Batch Download Functions
# ============================================================================


def download_pmc_ids(
    pmc_ids: list[str],
    output_dir: Path,
    api_key: Optional[str] = None,
    skip_existing: bool = False,
) -> tuple[int, int, int]:
    """
    Download multiple PMC XML files.

    Args:
        pmc_ids: List of PMC IDs to download
        output_dir: Directory to save XML files
        api_key: NCBI API key (optional)
        skip_existing: Skip PMC IDs that already have XML files

    Returns:
        Tuple of (successful, failed, skipped) counts
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    rate_limit = API_KEY_RATE_LIMIT if api_key else DEFAULT_RATE_LIMIT

    successful = 0
    failed = 0
    skipped = 0

    total = len(pmc_ids)

    print(f"\nDownloading {total} PMC XML files...")
    print(f"Output directory: {output_dir}")
    print(f"Rate limit: {1 / rate_limit:.1f} requests/second")
    if api_key:
        print("Using NCBI API key for increased rate limit")
    print("-" * 60)

    for i, pmc_id in enumerate(pmc_ids, 1):
        normalized_id = normalize_pmc_id(pmc_id)
        output_path = output_dir / f"{normalized_id}.xml"

        # Skip existing files if requested
        if skip_existing and output_path.exists():
            print(f"[{i}/{total}] Skipping {normalized_id} (already exists)")
            skipped += 1
            continue

        print(f"[{i}/{total}] Downloading {normalized_id}...", end=" ")

        # Fetch XML
        xml_content = fetch_pmc_xml(normalized_id, api_key, rate_limit)

        if xml_content:
            # Save to file
            if save_pmc_xml(normalized_id, xml_content, output_dir):
                print("✓")
                successful += 1
            else:
                print("✗ (save failed)")
                failed += 1
        else:
            print("✗ (fetch failed)")
            failed += 1

    return successful, failed, skipped


def load_pmc_ids_from_file(file_path: Path) -> list[str]:
    """
    Load PMC IDs from a text file (one per line).

    Args:
        file_path: Path to file containing PMC IDs

    Returns:
        List of PMC IDs
    """
    pmc_ids = []

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                if validate_pmc_id(line):
                    pmc_ids.append(normalize_pmc_id(line))
                else:
                    print(f"Warning: Invalid PMC ID format: {line}")

    return pmc_ids


# ============================================================================
# Main Pipeline
# ============================================================================


def main():
    """Main download execution."""
    parser = argparse.ArgumentParser(
        description="Stage 0: PMC XML Download Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download specific PMC IDs
  python download_pipeline.py --pmc-ids PMC123456 PMC234567

  # Download from a file
  python download_pipeline.py --pmc-id-file my_ids.txt

  # Search PubMed and download results
  python download_pipeline.py --search "BRCA1 AND breast cancer"

  # Use NCBI API key for higher rate limit
  python download_pipeline.py --pmc-id-file ids.txt --api-key YOUR_KEY

  # Resume interrupted download
  python download_pipeline.py --pmc-id-file ids.txt --skip-existing
        """,
    )

    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--pmc-ids", nargs="+", help="PMC IDs to download (e.g., PMC123456 PMC234567)")
    input_group.add_argument("--pmc-id-file", type=str, help="File containing PMC IDs (one per line)")
    input_group.add_argument("--search", type=str, help="PubMed search query (downloads matching PMC articles)")

    # Output options
    parser.add_argument("--output-dir", type=str, default="pmc_xmls", help="Output directory for XML files (default: pmc_xmls)")

    # Search options
    parser.add_argument("--max-results", type=int, default=100, help="Maximum search results to download (default: 100)")

    # Download options
    parser.add_argument("--api-key", type=str, default=None, help="NCBI API key (increases rate limit from 3 to 10 req/sec)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip PMC IDs that already have XML files")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Collect PMC IDs from appropriate source
    pmc_ids = []

    if args.pmc_ids:
        # Direct PMC ID list
        pmc_ids = [normalize_pmc_id(id) for id in args.pmc_ids]

    elif args.pmc_id_file:
        # Load from file
        file_path = Path(args.pmc_id_file)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return 1
        pmc_ids = load_pmc_ids_from_file(file_path)
        print(f"Loaded {len(pmc_ids)} PMC IDs from {file_path}")

    elif args.search:
        # Search PubMed
        rate_limit = API_KEY_RATE_LIMIT if args.api_key else DEFAULT_RATE_LIMIT
        pmc_ids = search_pubmed(
            args.search,
            max_results=args.max_results,
            api_key=args.api_key,
            rate_limit=rate_limit,
        )

        if not pmc_ids:
            print("No results found for search query")
            return 0

    # Validate PMC IDs
    valid_ids = [id for id in pmc_ids if validate_pmc_id(id)]
    invalid_count = len(pmc_ids) - len(valid_ids)

    if invalid_count > 0:
        print(f"Warning: Skipped {invalid_count} invalid PMC IDs")

    if not valid_ids:
        print("Error: No valid PMC IDs to download")
        return 1

    # Download PMC XML files
    print("=" * 60)
    print("Stage 0: PMC XML Download Pipeline")
    print("=" * 60)

    successful, failed, skipped = download_pmc_ids(
        valid_ids,
        output_dir,
        api_key=args.api_key,
        skip_existing=args.skip_existing,
    )

    # Print summary
    print()
    print("=" * 60)
    print("Download complete!")
    print("=" * 60)
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    if skipped > 0:
        print(f"Skipped: {skipped}")
    print(f"Total: {len(valid_ids)}")
    print(f"\nXML files saved to: {output_dir}")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())

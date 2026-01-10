#!/usr/bin/env python3
"""
Quick test of the PMC download pipeline.

Tests downloading a single PMC article to verify the pipeline works.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from download_pipeline import (
    fetch_pmc_xml,
    save_pmc_xml,
    normalize_pmc_id,
    validate_pmc_id,
)


def test_single_download():
    """Test downloading a single PMC article."""
    
    # Use a well-known paper about BRCA1
    test_pmc_id = "PMC6462820"
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("Testing PMC Download Pipeline")
    print("=" * 60)
    print()
    
    # Test 1: ID validation
    print("Test 1: PMC ID validation")
    assert validate_pmc_id("123456"), "Should accept numeric ID"
    assert validate_pmc_id("PMC123456"), "Should accept PMC prefix"
    assert normalize_pmc_id("123456") == "PMC123456", "Should normalize to PMC format"
    print("  ✓ ID validation working")
    print()
    
    # Test 2: Fetch XML
    print(f"Test 2: Fetching {test_pmc_id}")
    xml_content = fetch_pmc_xml(test_pmc_id)
    
    if not xml_content:
        print("  ✗ Failed to fetch XML")
        return False
    
    print(f"  ✓ Fetched {len(xml_content)} bytes")
    print()
    
    # Test 3: Save XML
    print("Test 3: Saving XML to file")
    success = save_pmc_xml(test_pmc_id, xml_content, output_dir)
    
    if not success:
        print("  ✗ Failed to save XML")
        return False
    
    output_file = output_dir / f"{test_pmc_id}.xml"
    if not output_file.exists():
        print("  ✗ Output file not created")
        return False
    
    print(f"  ✓ Saved to {output_file}")
    print(f"  ✓ File size: {output_file.stat().st_size} bytes")
    print()
    
    # Test 4: Verify XML structure
    print("Test 4: Verifying XML structure")
    import xml.etree.ElementTree as ET
    
    try:
        tree = ET.parse(output_file)
        root = tree.getroot()
        
        # Check for article element
        article = root.find(".//article")
        if article is None:
            print("  ✗ No <article> element found")
            return False
        
        # Check for title
        title = root.find(".//article-title")
        if title is not None:
            title_text = "".join(title.itertext()).strip()
            print(f"  ✓ Title: {title_text[:60]}...")
        
        print("  ✓ XML structure valid")
        print()
        
    except ET.ParseError as e:
        print(f"  ✗ XML parsing failed: {e}")
        return False
    
    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print(f"\nTest output saved to: {output_dir}")
    print("You can now run the full download pipeline:")
    print(f"  python download_pipeline.py --pmc-ids {test_pmc_id} --output-dir pmc_xmls")
    
    return True


if __name__ == "__main__":
    success = test_single_download()
    sys.exit(0 if success else 1)

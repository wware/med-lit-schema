"""
Tests for PMC XML download pipeline.

Tests the new download_pipeline.py module that downloads PMC articles
from NCBI E-utilities.

Run with: pytest tests/ingest/test_download_pipeline.py -v
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

from med_lit_schema.ingest.download.download_pipeline import (
    normalize_pmc_id,
    validate_pmc_id,
    save_pmc_xml,
    load_pmc_ids_from_file,
    fetch_pmc_xml,
    search_pubmed,
)


class TestPMCIDUtilities:
    """Test PMC ID utility functions."""

    def test_normalize_pmc_id_with_prefix(self):
        """Test normalizing PMC ID that already has prefix."""
        assert normalize_pmc_id("PMC123456") == "PMC123456"

    def test_normalize_pmc_id_without_prefix(self):
        """Test normalizing PMC ID without prefix."""
        assert normalize_pmc_id("123456") == "PMC123456"

    def test_normalize_pmc_id_with_whitespace(self):
        """Test normalizing PMC ID with whitespace."""
        assert normalize_pmc_id("  PMC123456  ") == "PMC123456"
        assert normalize_pmc_id("  123456  ") == "PMC123456"

    def test_validate_pmc_id_valid(self):
        """Test validating valid PMC IDs."""
        assert validate_pmc_id("PMC123456") is True
        assert validate_pmc_id("123456") is True
        assert validate_pmc_id("PMC1") is True

    def test_validate_pmc_id_invalid(self):
        """Test validating invalid PMC IDs."""
        assert validate_pmc_id("PMC") is False
        assert validate_pmc_id("PMCABC") is False
        assert validate_pmc_id("123ABC") is False
        assert validate_pmc_id("") is False

    def test_validate_pmc_id_with_letters(self):
        """Test that PMC IDs with letters in numeric part are invalid."""
        assert validate_pmc_id("PMC123ABC") is False


class TestSavePMCXML:
    """Test saving PMC XML to files."""

    def test_save_valid_xml(self):
        """Test saving valid XML content."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            xml_content = """<?xml version="1.0"?>
<pmc-articleset>
  <article>
    <front>
      <article-meta>
        <article-id pub-id-type="pmcid">PMC123456</article-id>
        <title-group>
          <article-title>Test Article</article-title>
        </title-group>
      </article-meta>
    </front>
  </article>
</pmc-articleset>"""

            result = save_pmc_xml("PMC123456", xml_content, output_dir)

            assert result is True
            assert (output_dir / "PMC123456.xml").exists()

            # Verify content
            with open(output_dir / "PMC123456.xml") as f:
                saved_content = f.read()
                assert "PMC123456" in saved_content

    def test_save_invalid_xml(self):
        """Test that invalid XML is rejected."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Invalid XML
            xml_content = "<not-closed>"

            result = save_pmc_xml("PMC123456", xml_content, output_dir)

            assert result is False
            # File should not be created
            assert not (output_dir / "PMC123456.xml").exists()

    def test_save_normalizes_pmc_id(self):
        """Test that save normalizes PMC ID in filename."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            xml_content = """<?xml version="1.0"?>
<article></article>"""

            # Pass ID without PMC prefix
            save_pmc_xml("123456", xml_content, output_dir)

            # Should create file with normalized name
            assert (output_dir / "PMC123456.xml").exists()


class TestLoadPMCIDsFromFile:
    """Test loading PMC IDs from text files."""

    def test_load_pmc_ids_basic(self):
        """Test loading PMC IDs from file."""
        with TemporaryDirectory() as tmpdir:
            id_file = Path(tmpdir) / "ids.txt"

            # Write test IDs
            with open(id_file, "w") as f:
                f.write("PMC123456\n")
                f.write("PMC234567\n")
                f.write("PMC345678\n")

            ids = load_pmc_ids_from_file(id_file)

            assert len(ids) == 3
            assert "PMC123456" in ids
            assert "PMC234567" in ids
            assert "PMC345678" in ids

    def test_load_pmc_ids_with_comments(self):
        """Test loading PMC IDs with comment lines."""
        with TemporaryDirectory() as tmpdir:
            id_file = Path(tmpdir) / "ids.txt"

            # Write test IDs with comments
            with open(id_file, "w") as f:
                f.write("# This is a comment\n")
                f.write("PMC123456\n")
                f.write("# Another comment\n")
                f.write("PMC234567\n")

            ids = load_pmc_ids_from_file(id_file)

            assert len(ids) == 2
            assert "PMC123456" in ids
            assert "PMC234567" in ids

    def test_load_pmc_ids_with_empty_lines(self):
        """Test loading PMC IDs with empty lines."""
        with TemporaryDirectory() as tmpdir:
            id_file = Path(tmpdir) / "ids.txt"

            with open(id_file, "w") as f:
                f.write("PMC123456\n")
                f.write("\n")
                f.write("PMC234567\n")
                f.write("\n\n")
                f.write("PMC345678\n")

            ids = load_pmc_ids_from_file(id_file)

            assert len(ids) == 3

    def test_load_pmc_ids_normalizes_ids(self):
        """Test that loading normalizes PMC IDs."""
        with TemporaryDirectory() as tmpdir:
            id_file = Path(tmpdir) / "ids.txt"

            # Write IDs without PMC prefix
            with open(id_file, "w") as f:
                f.write("123456\n")
                f.write("234567\n")

            ids = load_pmc_ids_from_file(id_file)

            # Should be normalized
            assert "PMC123456" in ids
            assert "PMC234567" in ids

    def test_load_pmc_ids_skips_invalid(self):
        """Test that loading skips invalid PMC IDs."""
        with TemporaryDirectory() as tmpdir:
            id_file = Path(tmpdir) / "ids.txt"

            with open(id_file, "w") as f:
                f.write("PMC123456\n")
                f.write("INVALID\n")  # Invalid ID
                f.write("PMC234567\n")

            ids = load_pmc_ids_from_file(id_file)

            # Should only have valid IDs
            assert len(ids) == 2
            assert "INVALID" not in ids


class TestFetchPMCXMLWithMock:
    """Test fetch_pmc_xml with mocked urllib."""

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_fetch_pmc_xml_success(self, mock_sleep, mock_urlopen):
        """Test successful PMC XML fetch."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = b"<article>Test</article>"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        result = fetch_pmc_xml("PMC123456")

        assert result == "<article>Test</article>"
        assert mock_urlopen.called

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_fetch_pmc_xml_404(self, mock_sleep, mock_urlopen):
        """Test fetch when PMC article not found."""
        from urllib.error import HTTPError

        # Mock 404 error
        mock_urlopen.side_effect = HTTPError(url="test", code=404, msg="Not Found", hdrs=None, fp=None)

        result = fetch_pmc_xml("PMC999999")

        assert result is None

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_fetch_pmc_xml_rate_limit(self, mock_sleep, mock_urlopen):
        """Test fetch with rate limiting (429 error)."""
        from urllib.error import HTTPError

        # Mock 429 error on first try, success on retry
        mock_response = MagicMock()
        mock_response.read.return_value = b"<article>Test</article>"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        mock_urlopen.side_effect = [HTTPError(url="test", code=429, msg="Too Many Requests", hdrs=None, fp=None), mock_response]

        result = fetch_pmc_xml("PMC123456")

        # Should retry and succeed
        assert result == "<article>Test</article>"
        # Should have slept for retry
        assert mock_sleep.called

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_fetch_pmc_xml_max_retries(self, mock_sleep, mock_urlopen):
        """Test fetch gives up after max retries."""
        from urllib.error import HTTPError

        # Always return 429
        mock_urlopen.side_effect = HTTPError(url="test", code=429, msg="Too Many Requests", hdrs=None, fp=None)

        result = fetch_pmc_xml("PMC123456")

        # Should eventually give up
        assert result is None

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_fetch_pmc_xml_uses_rate_limit(self, mock_sleep, mock_urlopen):
        """Test that fetch respects rate limit parameter."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"<article>Test</article>"
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        rate_limit = 0.5
        fetch_pmc_xml("PMC123456", rate_limit=rate_limit)

        # Should sleep for rate limit duration
        mock_sleep.assert_called_with(rate_limit)


class TestSearchPubMedWithMock:
    """Test search_pubmed with mocked urllib."""

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_search_pubmed_success(self, mock_sleep, mock_urlopen):
        """Test successful PubMed search."""
        # Mock search response
        mock_response = MagicMock()
        search_result = {"esearchresult": {"idlist": ["123456", "234567", "345678"]}}
        import json

        mock_response.read.return_value = json.dumps(search_result).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        results = search_pubmed("breast cancer", max_results=10)

        assert len(results) == 3
        assert "PMC123456" in results
        assert "PMC234567" in results

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_search_pubmed_no_results(self, mock_sleep, mock_urlopen):
        """Test PubMed search with no results."""
        mock_response = MagicMock()
        search_result = {"esearchresult": {"idlist": []}}
        import json

        mock_response.read.return_value = json.dumps(search_result).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        results = search_pubmed("nonexistent query xyz", max_results=10)

        assert len(results) == 0

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_search_pubmed_with_api_key(self, mock_sleep, mock_urlopen):
        """Test that search uses API key when provided."""
        mock_response = MagicMock()
        search_result = {"esearchresult": {"idlist": []}}
        import json

        mock_response.read.return_value = json.dumps(search_result).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        search_pubmed("test query", api_key="test_api_key")

        # Verify API key was included in URL
        call_args = mock_urlopen.call_args
        url = call_args[0][0]
        assert "api_key=test_api_key" in url

    @patch("med_lit_schema.ingest.download.download_pipeline.urlopen")
    @patch("med_lit_schema.ingest.download.download_pipeline.time.sleep")
    def test_search_pubmed_handles_error(self, mock_sleep, mock_urlopen):
        """Test that search handles errors gracefully."""
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(url="test", code=500, msg="Server Error", hdrs=None, fp=None)

        results = search_pubmed("test query")

        # Should return empty list on error
        assert results == []


class TestDownloadPipelineIntegration:
    """Integration-style tests for download pipeline."""

    def test_normalize_and_validate_workflow(self):
        """Test complete workflow of normalizing and validating IDs."""
        test_ids = [
            "PMC123456",
            "234567",
            "  PMC345678  ",
            "INVALID",
            "",
        ]

        valid_ids = []
        for id_str in test_ids:
            if validate_pmc_id(id_str):
                valid_ids.append(normalize_pmc_id(id_str))

        assert len(valid_ids) == 3
        assert all(id.startswith("PMC") for id in valid_ids)

    def test_file_load_and_download_workflow(self):
        """Test workflow of loading IDs from file and preparing for download."""
        with TemporaryDirectory() as tmpdir:
            # Create ID file
            id_file = Path(tmpdir) / "ids.txt"
            with open(id_file, "w") as f:
                f.write("# Test IDs\n")
                f.write("PMC123456\n")
                f.write("234567\n")

            # Load IDs
            ids = load_pmc_ids_from_file(id_file)

            assert len(ids) == 2
            assert all(validate_pmc_id(id) for id in ids)


@pytest.mark.requires_network
class TestDownloadPipelineNetworkTests:
    """
    Network integration tests that hit real NCBI APIs.

    These require network access and should be run sparingly.

    Run with: pytest -m requires_network
    Skip with: pytest -m "not requires_network"
    """

    def test_real_fetch_pmc_xml(self):
        """Test fetching a real PMC article."""
        # Use a well-known paper
        result = fetch_pmc_xml("PMC6462820", rate_limit=1.0)

        if result:
            # Verify it's valid XML
            try:
                tree = ET.fromstring(result)
                assert tree is not None
            except ET.ParseError:
                pytest.fail("Invalid XML returned from NCBI")

    def test_real_search_pubmed(self):
        """Test real PubMed search."""
        results = search_pubmed("breast cancer", max_results=5, rate_limit=1.0)

        # Should get some results
        assert len(results) > 0
        # Results should be PMC IDs
        assert all(id.startswith("PMC") for id in results)

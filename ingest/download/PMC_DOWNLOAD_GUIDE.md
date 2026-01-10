# PMC Download Pipeline - Usage Guide

## Overview

The PMC Download Pipeline (`download_pipeline.py`) is **Stage 0** of the medical literature ingestion process. It downloads PubMed Central (PMC) XML files from NCBI and stores them locally for subsequent processing stages.

## Why a Separate Download Stage?

Having a dedicated download stage provides several benefits:

1. **Separation of Concerns**: Downloading is independent from processing
2. **Resumable**: Can restart processing without re-downloading
3. **Local Archive**: Build a local corpus of papers for offline work
4. **Rate Limiting**: Handles NCBI API rate limits transparently
5. **Error Recovery**: Failed downloads can be retried independently

## Quick Start

### Test the Pipeline

```bash
# Run the test script to verify everything works
python ingest/test_download.py

# This will:
# - Download a single paper (PMC6462820)
# - Validate the XML structure
# - Save it to test_output/
```

### Download Specific Papers

```bash
# Download specific PMC IDs
python ingest/download_pipeline.py \
    --pmc-ids PMC6462820 PMC5961482 PMC5748537 \
    --output-dir pmc_xmls

# Download from a file containing PMC IDs
python ingest/download_pipeline.py \
    --pmc-id-file ingest/sample_pmc_ids.txt \
    --output-dir pmc_xmls
```

### Search and Download

```bash
# Search PubMed and download matching papers
python ingest/download_pipeline.py \
    --search "BRCA1 AND breast cancer AND 2020:2024[pdat]" \
    --max-results 50 \
    --output-dir pmc_xmls
```

## Input Options

### Option 1: Direct PMC IDs

Provide PMC IDs directly on the command line:

```bash
python ingest/download_pipeline.py \
    --pmc-ids PMC123456 PMC234567 PMC345678 \
    --output-dir pmc_xmls
```

PMC IDs can be in either format:
- With prefix: `PMC123456`
- Without prefix: `123456` (will be normalized to `PMC123456`)

### Option 2: PMC ID File

Create a text file with one PMC ID per line:

```text
# my_papers.txt
PMC123456
PMC234567
PMC345678
```

Then download:

```bash
python ingest/download_pipeline.py \
    --pmc-id-file my_papers.txt \
    --output-dir pmc_xmls
```

### Option 3: PubMed Search

Search PubMed and download the results:

```bash
python ingest/download_pipeline.py \
    --search "olaparib AND BRCA1" \
    --max-results 100 \
    --output-dir pmc_xmls
```

**PubMed Search Tips:**
- Use standard PubMed query syntax
- Add date filters: `"breast cancer 2020:2024[pdat]"`
- Combine terms with AND/OR: `"BRCA1 AND (breast OR ovarian)"`
- Filter by article type: `"review[ptyp]"`
- See [PubMed Help](https://pubmed.ncbi.nlm.nih.gov/help/) for query syntax

## Advanced Options

### NCBI API Key

Get an NCBI API key to increase rate limits from 3 to 10 requests/second:

1. Create a free NCBI account: https://www.ncbi.nlm.nih.gov/account/
2. Get your API key from your account settings
3. Use it with the pipeline:

```bash
python ingest/download_pipeline.py \
    --pmc-id-file my_papers.txt \
    --api-key YOUR_API_KEY_HERE \
    --output-dir pmc_xmls
```

### Resume Interrupted Downloads

If a download is interrupted, resume by skipping already-downloaded files:

```bash
python ingest/download_pipeline.py \
    --pmc-id-file my_papers.txt \
    --skip-existing \
    --output-dir pmc_xmls
```

## Output

Downloaded XML files are saved as:
```
pmc_xmls/
├── PMC123456.xml
├── PMC234567.xml
└── PMC345678.xml
```

Each file contains the complete PMC XML for one paper, ready for processing by Stage 1 (NER) and Stage 2 (Provenance).

## Rate Limiting

The pipeline respects NCBI's rate limits:

- **Without API key**: 3 requests/second
- **With API key**: 10 requests/second

Rate limiting is handled automatically. Large downloads will take time:
- 100 papers: ~30 seconds (with API key) or ~90 seconds (without)
- 1000 papers: ~5 minutes (with API key) or ~15 minutes (without)

## Error Handling

The pipeline handles common errors gracefully:

- **404 Not Found**: Paper doesn't exist or isn't in PMC
- **429 Rate Limited**: Automatic retry with backoff
- **Network errors**: Automatic retry (up to 3 attempts)
- **Invalid XML**: Reports error and continues with next paper

Failed downloads are reported in the summary:

```
===========================================================
Download complete!
===========================================================
Successful: 47
Failed: 3
Total: 50

XML files saved to: pmc_xmls
===========================================================
```

## Integration with Pipeline

After downloading, proceed to the next stages:

```bash
# Stage 0: Download papers
python ingest/download_pipeline.py \
    --search "BRCA1 breast cancer" \
    --max-results 50 \
    --output-dir pmc_xmls

# Stage 1: Extract entities
python ingest/ner_pipeline.py \
    --xml-dir pmc_xmls \
    --storage sqlite \
    --output-dir output

# Stage 2: Extract paper metadata
python ingest/provenance_pipeline.py \
    --input-dir pmc_xmls \
    --storage sqlite \
    --output-dir output

# ... continue with other stages
```

## Common Use Cases

### Building a Research Corpus

```bash
# Download all papers on a specific topic
python ingest/download_pipeline.py \
    --search "synthetic lethality AND cancer" \
    --max-results 500 \
    --api-key YOUR_KEY \
    --output-dir corpus/synthetic_lethality
```

### Updating an Existing Corpus

```bash
# Download recent papers and skip existing ones
python ingest/download_pipeline.py \
    --search "PARP inhibitor 2024:2024[pdat]" \
    --skip-existing \
    --output-dir pmc_xmls
```

### Working from a Citation List

If you have a list of papers from a citation manager:

1. Export PMC IDs to a text file (one per line)
2. Download:

```bash
python ingest/download_pipeline.py \
    --pmc-id-file citations.txt \
    --output-dir pmc_xmls
```

## Troubleshooting

### "No results found for search query"

- Check your search syntax in PubMed's web interface first
- Some papers may not be in PMC (use broader search)
- Try removing date filters

### "Rate limited, retrying..."

- This is normal for large downloads
- Get an NCBI API key to increase limits
- Reduce `--max-results` for faster completion

### "Invalid XML for PMC123456"

- Paper may be corrupted on NCBI's end
- Check if it's available on PMC website
- Report to NCBI if consistently failing

### Network Errors

- Check your internet connection
- Some networks block NCBI (use VPN)
- Retry with `--skip-existing` to resume

## Next Steps

After downloading papers, you're ready for:

1. **Stage 1 (NER)**: Extract biomedical entities
2. **Stage 2 (Provenance)**: Extract paper metadata and structure
3. **Stage 3 (Claims)**: Extract relationships
4. **Stage 4 (Evidence)**: Extract quantitative evidence

See the main ingest README for details on subsequent stages.

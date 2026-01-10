# PMC Download Pipeline - Quick Reference

## Installation
No additional dependencies needed beyond the base project requirements.

## Basic Usage

### Test It Works
```bash
./ingest/test_download.py
```

### Download Specific Papers
```bash
python ingest/download_pipeline.py --pmc-ids PMC123456 PMC234567 --output-dir pmc_xmls
```

### Download from File
```bash
python ingest/download_pipeline.py --pmc-id-file my_ids.txt --output-dir pmc_xmls
```

### Search and Download
```bash
python ingest/download_pipeline.py --search "BRCA1 breast cancer" --max-results 50 --output-dir pmc_xmls
```

## Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--pmc-ids` | Space-separated list of PMC IDs | `--pmc-ids PMC123 PMC456` |
| `--pmc-id-file` | File with PMC IDs (one per line) | `--pmc-id-file ids.txt` |
| `--search` | PubMed search query | `--search "cancer therapy"` |
| `--output-dir` | Where to save XML files | `--output-dir pmc_xmls` |
| `--max-results` | Max search results (default: 100) | `--max-results 500` |
| `--api-key` | NCBI API key (optional) | `--api-key YOUR_KEY` |
| `--skip-existing` | Skip already downloaded files | `--skip-existing` |

## PubMed Search Examples

```bash
# Papers from specific years
--search "breast cancer 2020:2024[pdat]"

# Combine terms with AND/OR
--search "BRCA1 AND (breast OR ovarian)"

# Filter by article type
--search "breast cancer review[ptyp]"

# Author search
--search "Smith J[author]"

# Journal search
--search "Nature[journal]"
```

## Rate Limits

| Type | Requests/Second | Time for 100 Papers |
|------|----------------|---------------------|
| Without API key | 3 req/sec | ~90 seconds |
| With API key | 10 req/sec | ~30 seconds |

Get an API key (free): https://www.ncbi.nlm.nih.gov/account/

## Output Structure

```
pmc_xmls/
├── PMC123456.xml
├── PMC234567.xml
└── PMC345678.xml
```

Each file is ready for processing by the next pipeline stages.

## Common Workflows

### 1. Build a Topic-Specific Corpus
```bash
# Download all papers on a specific topic
python ingest/download_pipeline.py \
    --search "synthetic lethality cancer" \
    --max-results 500 \
    --api-key YOUR_KEY \
    --output-dir corpus/synthetic_lethality
```

### 2. Update Existing Corpus
```bash
# Download recent papers, skip existing
python ingest/download_pipeline.py \
    --search "PARP inhibitor 2024:2024[pdat]" \
    --skip-existing \
    --output-dir pmc_xmls
```

### 3. Download from Citation List
```bash
# Create citations.txt with one PMC ID per line
# Then:
python ingest/download_pipeline.py \
    --pmc-id-file citations.txt \
    --output-dir pmc_xmls
```

### 4. Complete Pipeline
```bash
# Use the convenience script
./ingest/run_pipeline.sh
```

## Error Codes

| Error | Meaning | Solution |
|-------|---------|----------|
| 404 | Paper not found | Check PMC ID is correct |
| 429 | Rate limited | Will auto-retry; get API key for faster access |
| Network error | Connection issue | Check internet; will auto-retry |
| Invalid XML | Corrupted paper | Skip or report to NCBI |

## Next Steps

After downloading:

```bash
# Stage 1: Extract entities
python ingest/ner_pipeline.py --xml-dir pmc_xmls --storage sqlite --output-dir output

# Stage 2: Extract metadata
python ingest/provenance_pipeline.py --input-dir pmc_xmls --storage sqlite --output-dir output

# ... etc (see run_pipeline.sh for complete workflow)
```

## Tips

- Start small (5-10 papers) to test your workflow
- Use `--skip-existing` for resumable downloads
- Get an NCBI API key for large downloads (1000+ papers)
- Check PubMed web interface to refine search queries
- Save PMC ID lists for reproducible corpora

## Support

- Full documentation: `ingest/PMC_DOWNLOAD_GUIDE.md`
- NCBI E-utilities docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- PubMed search help: https://pubmed.ncbi.nlm.nih.gov/help/

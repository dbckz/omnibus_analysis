# Digital Omnibus Downloader - Final Working Version

NOTE: This is all made with Claude

Downloads all 512+ PDF responses from the EC's Digital Omnibus consultation.

## Quick Start

```bash
# Install dependencies
pip install requests

# Run the downloader
python download_omnibus_final.py
```

That's it! The script will:
1. Download all feedback submissions (512+)
2. Download all PDF attachments
3. Create CSV files with statistics
4. Show progress as it works

## What You Get

After running, you'll have a folder `20401_digital_omnibus/` containing:

```
20401_digital_omnibus/
├── feedbacks.csv          # Summary of all submissions
├── feedbacks_raw.json     # Complete data in JSON format
├── attachments.csv        # Attachment details and status
├── countries.csv          # Submissions by country
├── user_types.csv         # Submissions by stakeholder type
└── attachments/           # All PDF files (named by ID)
    ├── 27568242_DIGITALEUROPE_feedback....pdf
    ├── 27567021_20251014_Schneider....pdf
    └── ... (all other PDFs)
```

## Understanding the Data

### feedbacks.csv
Each row is one submission with:
- **id**: Unique feedback ID
- **date**: Submission date
- **firstName, surname**: Submitter name (if provided)
- **organization**: Company/org name
- **country**: ISO country code (e.g., "BEL", "DEU")
- **userType**: BUSINESS_ASSOCIATION, EU_CITIZEN, NGO, etc.
- **trNumber**: Transparency Register number (for organizations)
- **feedback_text**: Text content (truncated to 1000 chars in CSV)
- **attachmentCount**: Number of attached PDFs

### attachments.csv
Links PDFs to submissions:
- **feedback_id**: Which submission this belongs to
- **attachment_id**: Unique attachment ID
- **document_id**: EC document reference
- **filename**: The actual PDF filename
- **status**: "downloaded", "exists", or "failed"

### Finding Specific Submissions

**By organization:**
```bash
grep -i "OpenMined\|Mozilla\|GDPR" feedbacks.csv
```

**By country:**
```bash
grep "\"DEU\"" feedbacks.csv  # Germany
grep "\"GBR\"" feedbacks.csv  # UK
```

**By user type:**
```bash
grep "BUSINESS_ASSOCIATION" feedbacks.csv
grep "NGO" feedbacks.csv
```

## Progress Tracking

The script shows real-time progress:
```
[2025-11-17 15:30:00] Fetching feedback submissions...
[2025-11-17 15:30:02]   Fetching page 0...
[2025-11-17 15:30:03]     Found 100 feedbacks, total: 100
[2025-11-17 15:30:03]     Progress: page 1 of 6
...
[2025-11-17 15:35:00] Downloading attachments...
[2025-11-17 15:35:01]   Total attachments to download: 450
[2025-11-17 15:35:02]   [1/450] ✓ Downloaded: 27568242_DIGITALEUROPE....pdf
```

## Resuming Downloads

The script automatically:
- Skips files that already exist
- Can be stopped and restarted
- Won't re-download existing PDFs

Just run it again and it will continue where it left off.

## Troubleshooting

### "No feedbacks found"
- Check your internet connection
- The EC website might be down (try later)
- Run `python diagnose_ec_api.py` to check API status

### "Failed to download attachments"
Some PDFs may fail to download if:
- The EC's attachment server is slow/down
- The file was removed
- Network timeout

Check `attachments.csv` to see which failed, then:
1. Wait a few hours and run again (it will retry failed ones)
2. Or manually download from the EC website using the feedback ID

### Rate Limiting
The script includes delays to be respectful:
- 1 second between API requests
- 0.3 seconds between PDF downloads

If you get rate limited, increase these in the script.

## Technical Details

- **API Endpoint**: `https://ec.europa.eu/info/law/better-regulation/api/allFeedback`
- **Response Format**: Spring Data REST (`content` array)
- **Pagination**: 100 results per page
- **Total Expected**: 512+ submissions
- **Total PDFs**: ~450-500 (not all submissions have attachments)

## Next Steps

Once downloaded, you can:
1. **Analyze the data** using the CSVs
2. **Read specific PDFs** from the attachments/ folder
3. **Search by topic** using grep or text search
4. **Generate statistics** by country, user type, etc.

For your analysis on Privacy Enhancing Technologies, try:
```bash
grep -i "privacy\|PET\|federated\|homomorphic\|differential" feedbacks.csv
```

This will find submissions mentioning PETs!

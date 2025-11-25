#!/usr/bin/env python3
"""
Download all PDF responses from the European Commission's Digital Omnibus consultation.
Final working version based on actual API structure.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
import csv

try:
    import requests
    USE_REQUESTS = True
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    exit(1)

# Configuration
PUBLICATION_ID = "20401"
OUTPUT_DIR = Path(f"{PUBLICATION_ID}_digital_omnibus")
ATTACHMENTS_DIR = OUTPUT_DIR / "attachments"

# API configuration (discovered from diagnostic)
BASE_URL = "https://ec.europa.eu/info/law/better-regulation/"
FEEDBACK_ENDPOINT = "api/allFeedback"
ATTACHMENT_ENDPOINT = "api/downloadAttachment"  # Will try multiple formats

def log_message(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def fetch_json(url, params=None):
    """Fetch JSON from a URL."""
    headers = {
        "Accept": "application/json, */*",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            log_message(f"  HTTP {response.status_code}: {url}")
            return None
    except Exception as e:
        log_message(f"  Error fetching {url}: {e}")
        return None

def download_file(url, filepath):
    """Download a file from URL to filepath."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=60, stream=True)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        return False
    except Exception as e:
        return False

def fetch_all_feedbacks():
    """Fetch all feedback submissions from the API."""
    all_feedbacks = []
    page = 0
    page_size = 100  # Request 100 per page for efficiency
    
    log_message("Fetching feedback submissions...")
    
    while True:
        url = f"{BASE_URL}{FEEDBACK_ENDPOINT}"
        params = {
            "publicationId": PUBLICATION_ID,
            "page": page,
            "size": page_size
        }
        
        log_message(f"  Fetching page {page}...")
        
        data = fetch_json(url, params)
        if not data:
            log_message(f"  Failed to fetch page {page}")
            break
        
        # Extract feedbacks from "content" key (Spring Data REST format)
        feedbacks = data.get("content", [])
        if not feedbacks:
            log_message(f"  No more feedbacks found")
            break
        
        all_feedbacks.extend(feedbacks)
        log_message(f"    Found {len(feedbacks)} feedbacks, total: {len(all_feedbacks)}")
        
        # Check pagination info
        if "totalPages" in data:
            total_pages = data["totalPages"]
            log_message(f"    Progress: page {page + 1} of {total_pages}")
            if page >= total_pages - 1:
                break
        elif "last" in data and data["last"]:
            # Spring Data format: "last" boolean indicates last page
            log_message(f"    Reached last page")
            break
        elif len(feedbacks) < page_size:
            # Got fewer results than requested, must be last page
            log_message(f"    Received {len(feedbacks)} < {page_size}, must be last page")
            break
        
        page += 1
        time.sleep(1)  # Be respectful to the server
        
        # Safety limit
        if page > 100:
            log_message("  Warning: Exceeded 100 pages, stopping")
            break
    
    return all_feedbacks

def download_attachment_file(attachment, feedback_id, index, total):
    """Download a single attachment file."""
    att_id = attachment.get("id")
    doc_id = attachment.get("documentId")
    filename = attachment.get("fileName", f"{att_id}.pdf")
    
    # Clean filename
    filename = str(filename).replace("/", "_").replace("\\", "_")
    
    # Ensure unique filename by prepending ID
    if not filename.startswith(str(att_id)):
        base, ext = os.path.splitext(filename)
        filename = f"{att_id}_{base}{ext}"
    
    filepath = ATTACHMENTS_DIR / filename
    
    # Skip if already exists
    if filepath.exists():
        log_message(f"  [{index}/{total}] ⏭️  Skipping (exists): {filename}")
        return "exists", filename
    
    # Try different download URL patterns
    download_urls = [
        # Pattern 1: Using attachment ID
        f"{BASE_URL}{ATTACHMENT_ENDPOINT}?id={att_id}",
        f"{BASE_URL}api/attachment/{att_id}",
        # Pattern 2: Using document ID
        f"{BASE_URL}{ATTACHMENT_ENDPOINT}?documentId={doc_id}",
        f"{BASE_URL}api/document/{doc_id}",
        # Pattern 3: Legacy patterns
        f"{BASE_URL}brpapi/attachment/{att_id}",
    ]
    
    for url in download_urls:
        if download_file(url, filepath):
            # Verify it's a real file (> 100 bytes)
            if os.path.getsize(filepath) > 100:
                log_message(f"  [{index}/{total}] ✓ Downloaded: {filename}")
                return "downloaded", filename
            else:
                # File too small, probably an error response
                os.remove(filepath)
    
    log_message(f"  [{index}/{total}] ✗ Failed: {filename}")
    return "failed", filename

def download_attachments(feedbacks):
    """Download all attachments from feedbacks."""
    log_message("\nDownloading attachments...")
    
    attachment_records = []
    stats = {"downloaded": 0, "exists": 0, "failed": 0}
    
    # Count total attachments
    total_attachments = sum(len(fb.get("attachments", [])) for fb in feedbacks)
    log_message(f"  Total attachments to download: {total_attachments}")
    
    current = 0
    for feedback in feedbacks:
        feedback_id = feedback.get("id")
        attachments = feedback.get("attachments", [])
        
        for attachment in attachments:
            current += 1
            status, filename = download_attachment_file(
                attachment, feedback_id, current, total_attachments
            )
            
            stats[status] += 1
            
            attachment_records.append({
                "feedback_id": feedback_id,
                "attachment_id": attachment.get("id"),
                "document_id": attachment.get("documentId"),
                "filename": filename,
                "original_filename": attachment.get("fileName"),
                "pages": attachment.get("pages"),
                "size_bytes": attachment.get("size"),
                "status": status
            })
            
            if status == "downloaded":
                time.sleep(0.3)  # Small delay between downloads
    
    return attachment_records, stats

def save_to_csv(data, filepath):
    """Save data to CSV file."""
    if not data:
        return
    
    # Get all unique keys from all records
    all_keys = set()
    for row in data:
        if isinstance(row, dict):
            all_keys.update(row.keys())
    
    fieldnames = sorted(all_keys)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            if isinstance(row, dict):
                # Handle nested objects/lists
                clean_row = {}
                for k, v in row.items():
                    if isinstance(v, (list, dict)):
                        clean_row[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        clean_row[k] = v
                writer.writerow(clean_row)

def main():
    """Main execution function."""
    log_message("=" * 70)
    log_message("Digital Omnibus Responses Downloader")
    log_message(f"Publication ID: {PUBLICATION_ID}")
    log_message(f"Output directory: {OUTPUT_DIR}")
    log_message("=" * 70)
    
    # Create directories
    OUTPUT_DIR.mkdir(exist_ok=True)
    ATTACHMENTS_DIR.mkdir(exist_ok=True)
    
    # Step 1: Fetch all feedbacks
    feedbacks = fetch_all_feedbacks()
    log_message(f"\n✓ Total feedbacks fetched: {len(feedbacks)}")
    
    if not feedbacks:
        log_message("\n❌ No feedbacks found. Check your internet connection.")
        return
    
    # Step 2: Save feedbacks metadata
    log_message("\nSaving feedback metadata...")
    
    # Save complete raw JSON
    with open(OUTPUT_DIR / "feedbacks_raw.json", "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, indent=2, ensure_ascii=False)
    log_message(f"  ✓ Saved raw JSON to feedbacks_raw.json")
    
    # Create flattened CSV version
    flat_feedbacks = []
    for fb in feedbacks:
        flat = {
            "id": fb.get("id"),
            "date": fb.get("dateFeedback", ""),
            "firstName": fb.get("firstName", ""),
            "surname": fb.get("surname", ""),
            "organization": fb.get("organization", ""),
            "country": fb.get("country", ""),
            "userType": fb.get("userType", ""),
            "language": fb.get("language", ""),
            "companySize": fb.get("companySize", ""),
            "trNumber": fb.get("trNumber", ""),  # Transparency Register number
            "status": fb.get("status", ""),
            "feedback_text": fb.get("feedback", "")[:1000],  # Truncate for CSV
            "attachmentCount": len(fb.get("attachments", [])),
            "reference": fb.get("referenceInitiative", "")
        }
        flat_feedbacks.append(flat)
    
    save_to_csv(flat_feedbacks, OUTPUT_DIR / "feedbacks.csv")
    log_message(f"  ✓ Saved {len(flat_feedbacks)} records to feedbacks.csv")
    
    # Step 3: Download attachments
    attachment_records, stats = download_attachments(feedbacks)
    save_to_csv(attachment_records, OUTPUT_DIR / "attachments.csv")
    log_message(f"  ✓ Saved {len(attachment_records)} attachment records to attachments.csv")
    
    # Step 4: Create summary statistics
    log_message("\nGenerating statistics...")
    
    # By country
    country_stats = {}
    for fb in feedbacks:
        country = fb.get("country", "Unknown")
        country_stats[country] = country_stats.get(country, 0) + 1
    
    country_list = [{"country": k, "count": v} for k, v in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)]
    save_to_csv(country_list, OUTPUT_DIR / "countries.csv")
    log_message(f"  ✓ Saved country statistics ({len(country_list)} countries)")
    
    # By user type
    usertype_stats = {}
    for fb in feedbacks:
        utype = fb.get("userType", "Unknown")
        usertype_stats[utype] = usertype_stats.get(utype, 0) + 1
    
    usertype_list = [{"userType": k, "count": v} for k, v in sorted(usertype_stats.items(), key=lambda x: x[1], reverse=True)]
    save_to_csv(usertype_list, OUTPUT_DIR / "user_types.csv")
    log_message(f"  ✓ Saved user type statistics ({len(usertype_list)} types)")
    
    # Summary
    log_message("\n" + "=" * 70)
    log_message("DOWNLOAD COMPLETE!")
    log_message("=" * 70)
    log_message(f"Total feedback submissions: {len(feedbacks)}")
    log_message(f"Total attachments: {len(attachment_records)}")
    log_message(f"  Downloaded: {stats['downloaded']}")
    log_message(f"  Already existed: {stats['exists']}")
    log_message(f"  Failed: {stats['failed']}")
    log_message(f"\nOutput directory: {OUTPUT_DIR.absolute()}")
    log_message("\nFiles created:")
    log_message(f"  📊 feedbacks.csv       - Summary metadata for all {len(feedbacks)} submissions")
    log_message(f"  📄 feedbacks_raw.json  - Complete JSON data")
    log_message(f"  📎 attachments.csv     - Details on all {len(attachment_records)} attachments")
    log_message(f"  🌍 countries.csv       - Submissions by country")
    log_message(f"  👥 user_types.csv      - Submissions by user type")
    log_message(f"  📁 attachments/        - {stats['downloaded'] + stats['exists']} PDF files")
    
    if stats['failed'] > 0:
        log_message(f"\n⚠️  {stats['failed']} attachments failed to download")
        log_message("   Check attachments.csv for details on failed downloads")

if __name__ == "__main__":
    main()

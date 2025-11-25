#!/usr/bin/env python3
"""
Download all responses from the European Commission's Digital Omnibus consultation.
FIXED VERSION - Handles PDF, DOCX, and other file formats correctly.
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

# API configuration
BASE_URL = "https://ec.europa.eu/info/law/better-regulation/"
FEEDBACK_ENDPOINT = "api/allFeedback"
DOWNLOAD_ENDPOINT = "api/download/"

# File type magic bytes for verification
FILE_SIGNATURES = {
    'pdf': b'%PDF',
    'docx': b'PK\x03\x04',  # DOCX is a ZIP file
    'doc': b'\xD0\xCF\x11\xE0',  # Old Word format
    'xlsx': b'PK\x03\x04',  # XLSX is also a ZIP file
    'zip': b'PK\x03\x04',
}

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
        return None
    except Exception as e:
        log_message(f"  Error fetching {url}: {e}")
        return None

def detect_file_type(first_bytes):
    """Detect file type from magic bytes."""
    for file_type, signature in FILE_SIGNATURES.items():
        if first_bytes.startswith(signature):
            return file_type
    return None

def download_file(url, filepath, expected_extension=None):
    """Download a file from URL to filepath and verify it's valid."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "*/*",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=60, stream=True)
        if response.status_code != 200:
            return False, "HTTP error"
        
        # Download to temporary file first
        temp_path = filepath.with_suffix('.tmp')
        first_chunk = None
        
        with open(temp_path, 'wb') as f:
            for i, chunk in enumerate(response.iter_content(chunk_size=8192)):
                if i == 0:
                    first_chunk = chunk
                f.write(chunk)
        
        # Verify file is valid
        if not first_chunk or len(first_chunk) < 4:
            os.remove(temp_path)
            return False, "Empty file"
        
        # Check file signature
        detected_type = detect_file_type(first_chunk)
        
        if detected_type:
            # Valid file detected
            # Check if extension matches
            if expected_extension:
                expected_lower = expected_extension.lower().lstrip('.')
                # Handle DOCX/XLSX (both are ZIP files)
                if detected_type == 'docx' and expected_lower in ['docx', 'xlsx', 'pptx']:
                    detected_type = expected_lower
            
            # Move temp file to final location
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(temp_path, filepath)
            return True, detected_type
        else:
            # Unknown file type - might be HTML error page
            if b'<html' in first_chunk.lower() or b'<!doctype' in first_chunk.lower():
                os.remove(temp_path)
                return False, "HTML page"
            else:
                # Unknown but not HTML - keep it anyway
                os.rename(temp_path, filepath)
                return True, "unknown"
        
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        return False, str(e)

def fetch_all_feedbacks():
    """Fetch all feedback submissions from the API."""
    all_feedbacks = []
    page = 0
    page_size = 100
    
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
            break
        
        feedbacks = data.get("content", [])
        if not feedbacks:
            break
        
        all_feedbacks.extend(feedbacks)
        log_message(f"    Found {len(feedbacks)} feedbacks, total: {len(all_feedbacks)}")
        
        if "totalPages" in data:
            total_pages = data["totalPages"]
            log_message(f"    Progress: page {page + 1} of {total_pages}")
            if page >= total_pages - 1:
                break
        elif "last" in data and data["last"]:
            break
        elif len(feedbacks) < page_size:
            break
        
        page += 1
        time.sleep(1)
        
        if page > 100:
            break
    
    return all_feedbacks

def download_attachment_file(attachment, feedback_id, index, total):
    """Download a single attachment file with correct extension."""
    att_id = attachment.get("id")
    doc_id = attachment.get("documentId")
    original_filename = attachment.get("fileName", f"{att_id}.pdf")
    
    if not doc_id:
        log_message(f"  [{index}/{total}] ✗ No documentId for attachment {att_id}")
        return "failed", original_filename, None
    
    # Preserve original extension
    original_path = Path(original_filename)
    extension = original_path.suffix  # e.g., '.pdf', '.docx'
    base_name = original_path.stem
    
    # Clean filename
    base_name = base_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    
    # Create unique filename with ID
    if not base_name.startswith(str(att_id)):
        filename = f"{att_id}_{base_name}{extension}"
    else:
        filename = f"{base_name}{extension}"
    
    filepath = ATTACHMENTS_DIR / filename
    
    # Check if already exists and is valid
    if filepath.exists():
        file_size = os.path.getsize(filepath)
        if file_size > 1000:  # At least 1KB
            # Verify it's a valid file
            with open(filepath, 'rb') as f:
                first_bytes = f.read(20)
            
            detected = detect_file_type(first_bytes)
            if detected:
                log_message(f"  [{index}/{total}] ⏭️  Skipping (exists, {detected}): {filename}")
                return "exists", filename, detected
            else:
                log_message(f"  [{index}/{total}] 🔄 Re-downloading (corrupted): {filename}")
                os.remove(filepath)
        else:
            log_message(f"  [{index}/{total}] 🔄 Re-downloading (too small): {filename}")
            os.remove(filepath)
    
    # Download using documentId
    download_url = f"{BASE_URL}{DOWNLOAD_ENDPOINT}{doc_id}"
    
    success, result = download_file(download_url, filepath, extension)
    
    if success:
        file_size = os.path.getsize(filepath)
        if file_size > 1000:
            log_message(f"  [{index}/{total}] ✓ Downloaded: {filename} ({result}, {file_size:,} bytes)")
            return "downloaded", filename, result
        else:
            log_message(f"  [{index}/{total}] ✗ File too small: {filename} ({file_size} bytes)")
            if os.path.exists(filepath):
                os.remove(filepath)
            return "failed", filename, "too_small"
    
    log_message(f"  [{index}/{total}] ✗ Failed: {filename} ({result})")
    return "failed", filename, result

def download_attachments(feedbacks):
    """Download all attachments from feedbacks."""
    log_message("\nDownloading attachments...")
    
    attachment_records = []
    stats = {"downloaded": 0, "exists": 0, "failed": 0}
    file_type_counts = {}
    
    total_attachments = sum(len(fb.get("attachments", [])) for fb in feedbacks)
    log_message(f"  Total attachments to download: {total_attachments}")
    
    current = 0
    for feedback in feedbacks:
        feedback_id = feedback.get("id")
        attachments = feedback.get("attachments", [])
        
        for attachment in attachments:
            current += 1
            status, filename, file_type = download_attachment_file(
                attachment, feedback_id, current, total_attachments
            )
            
            stats[status] += 1
            
            if file_type and file_type != "too_small":
                file_type_counts[file_type] = file_type_counts.get(file_type, 0) + 1
            
            attachment_records.append({
                "feedback_id": feedback_id,
                "attachment_id": attachment.get("id"),
                "document_id": attachment.get("documentId"),
                "filename": filename,
                "original_filename": attachment.get("fileName"),
                "detected_type": file_type,
                "pages": attachment.get("pages"),
                "size_bytes": attachment.get("size"),
                "status": status
            })
            
            if status == "downloaded":
                time.sleep(0.5)
    
    return attachment_records, stats, file_type_counts

def save_to_csv(data, filepath):
    """Save data to CSV file."""
    if not data:
        return
    
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
    log_message("Digital Omnibus Downloader - FIXED VERSION")
    log_message("Handles PDF, DOCX, and other file formats")
    log_message(f"Publication ID: {PUBLICATION_ID}")
    log_message(f"Output directory: {OUTPUT_DIR}")
    log_message("=" * 70)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    ATTACHMENTS_DIR.mkdir(exist_ok=True)
    
    # Fetch all feedbacks
    feedbacks = fetch_all_feedbacks()
    log_message(f"\n✓ Total feedbacks fetched: {len(feedbacks)}")
    
    if not feedbacks:
        log_message("\n❌ No feedbacks found.")
        return
    
    # Save metadata
    log_message("\nSaving feedback metadata...")
    
    with open(OUTPUT_DIR / "feedbacks_raw.json", "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, indent=2, ensure_ascii=False)
    log_message(f"  ✓ Saved raw JSON")
    
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
            "trNumber": fb.get("trNumber", ""),
            "status": fb.get("status", ""),
            "feedback_text": fb.get("feedback", "")[:1000],
            "attachmentCount": len(fb.get("attachments", [])),
            "reference": fb.get("referenceInitiative", "")
        }
        flat_feedbacks.append(flat)
    
    save_to_csv(flat_feedbacks, OUTPUT_DIR / "feedbacks.csv")
    log_message(f"  ✓ Saved feedbacks.csv")
    
    # Download attachments
    attachment_records, stats, file_types = download_attachments(feedbacks)
    save_to_csv(attachment_records, OUTPUT_DIR / "attachments.csv")
    log_message(f"  ✓ Saved attachments.csv")
    
    # Generate statistics
    log_message("\nGenerating statistics...")
    
    country_stats = {}
    for fb in feedbacks:
        country = fb.get("country", "Unknown")
        country_stats[country] = country_stats.get(country, 0) + 1
    
    country_list = [{"country": k, "count": v} for k, v in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)]
    save_to_csv(country_list, OUTPUT_DIR / "countries.csv")
    log_message(f"  ✓ Country statistics")
    
    usertype_stats = {}
    for fb in feedbacks:
        utype = fb.get("userType", "Unknown")
        usertype_stats[utype] = usertype_stats.get(utype, 0) + 1
    
    usertype_list = [{"userType": k, "count": v} for k, v in sorted(usertype_stats.items(), key=lambda x: x[1], reverse=True)]
    save_to_csv(usertype_list, OUTPUT_DIR / "user_types.csv")
    log_message(f"  ✓ User type statistics")
    
    # Summary
    log_message("\n" + "=" * 70)
    log_message("DOWNLOAD COMPLETE!")
    log_message("=" * 70)
    log_message(f"Total feedback submissions: {len(feedbacks)}")
    log_message(f"Total attachments: {len(attachment_records)}")
    log_message(f"  Downloaded: {stats['downloaded']}")
    log_message(f"  Already existed: {stats['exists']}")
    log_message(f"  Failed: {stats['failed']}")
    
    log_message(f"\nFile types:")
    for ftype, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        log_message(f"  {ftype.upper()}: {count}")
    
    log_message(f"\nOutput directory: {OUTPUT_DIR.absolute()}")
    log_message("\nFiles created:")
    log_message(f"  📊 feedbacks.csv       - {len(feedbacks)} submissions")
    log_message(f"  📄 feedbacks_raw.json  - Complete JSON data")
    log_message(f"  📎 attachments.csv     - {len(attachment_records)} attachments")
    log_message(f"  🌍 countries.csv       - By country")
    log_message(f"  👥 user_types.csv      - By stakeholder type")
    log_message(f"  📁 attachments/        - {stats['downloaded'] + stats['exists']} files")
    
    if stats['failed'] > 0:
        log_message(f"\n⚠️  {stats['failed']} attachments failed")
        log_message("   Check attachments.csv for details")
    
    log_message("\n✨ All files should now work correctly (PDF, DOCX, etc.)!")

if __name__ == "__main__":
    main()

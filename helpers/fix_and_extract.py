#!/usr/bin/env python3
"""
Fix files that have wrong extensions (e.g., PDFs saved as .docx)
and re-extract text from them.
"""

import os
import re
import json
import csv
from pathlib import Path
from datetime import datetime

# Install deps if needed
try:
    import pdfplumber
    from docx import Document
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber", "python-docx", "-q"])
    import pdfplumber
    from docx import Document

DATA_DIR = Path("20401_digital_omnibus")
ATTACHMENTS_DIR = DATA_DIR / "attachments"
FEEDBACKS_CSV = DATA_DIR / "feedbacks.csv"
OUTPUT_FILE = DATA_DIR / "extracted_texts.json"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_actual_type(filepath):
    """Get actual file type from magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
        
        if header[:4] == b'PK\x03\x04':
            return "docx"
        elif header[:4] == b'\xD0\xCF\x11\xE0':
            return "doc"
        elif header[:5] == b'%PDF-':
            return "pdf"
        elif b'<' in header[:5]:
            return "html"
        return "unknown"
    except:
        return "unknown"

def extract_pdf(filepath):
    """Extract text from PDF."""
    try:
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text.strip()
    except Exception as e:
        return ""

def extract_docx(filepath):
    """Extract text from DOCX."""
    try:
        doc = Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except:
        return ""

def main():
    log("=" * 60)
    log("FIX MISNAMED FILES & RE-EXTRACT")
    log("=" * 60)
    
    # Step 1: Find and fix misnamed files
    log("\nStep 1: Checking for misnamed files...")
    
    fixed_count = 0
    rename_map = {}  # old_name -> new_name
    
    for filepath in ATTACHMENTS_DIR.iterdir():
        if not filepath.is_file():
            continue
        
        ext = filepath.suffix.lower()
        actual_type = get_actual_type(filepath)
        
        # Check for mismatch
        needs_fix = False
        new_ext = ext
        
        if actual_type == "pdf" and ext != ".pdf":
            needs_fix = True
            new_ext = ".pdf"
        elif actual_type == "docx" and ext not in [".docx", ".xlsx"]:
            needs_fix = True
            new_ext = ".docx"
        elif actual_type == "doc" and ext != ".doc":
            needs_fix = True
            new_ext = ".doc"
        
        if needs_fix:
            new_name = filepath.stem + new_ext
            new_path = filepath.parent / new_name
            
            # Rename
            log(f"  Renaming: {filepath.name} -> {new_name}")
            filepath.rename(new_path)
            rename_map[filepath.name] = new_name
            fixed_count += 1
    
    log(f"\n✓ Fixed {fixed_count} misnamed files")
    
    # Step 2: Re-extract all texts
    log("\nStep 2: Re-extracting all texts...")
    
    # Load feedbacks
    feedbacks = []
    with open(FEEDBACKS_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            feedbacks.append(row)
    log(f"  Loaded {len(feedbacks)} feedbacks")
    
    # Build attachment map (with updated names)
    attachment_map = {}
    for f in ATTACHMENTS_DIR.iterdir():
        if f.is_file():
            match = re.match(r'^(\d+)_', f.name)
            if match:
                fid = match.group(1)
                if fid not in attachment_map:
                    attachment_map[fid] = []
                attachment_map[fid].append(f.name)
    
    log(f"  Found attachments for {len(attachment_map)} feedbacks")
    
    # Extract texts
    log("\nExtracting texts...")
    results = []
    stats = {'pdf': 0, 'docx': 0, 'csv_only': 0, 'failed': 0}
    
    for i, fb in enumerate(feedbacks, 1):
        if i % 100 == 0:
            log(f"  Processing {i}/{len(feedbacks)}...")
        
        fid = str(fb.get('id', ''))
        text_parts = []
        sources = []
        
        # CSV feedback text
        feedback_text = fb.get('feedback_text', '').strip()
        if feedback_text:
            text_parts.append(feedback_text)
            sources.append("csv")
        
        # Attachment texts
        for filename in attachment_map.get(fid, []):
            filepath = ATTACHMENTS_DIR / filename
            if not filepath.exists():
                continue
            
            actual_type = get_actual_type(filepath)
            text = ""
            
            if actual_type == "pdf":
                text = extract_pdf(filepath)
                if text:
                    stats['pdf'] += 1
            elif actual_type == "docx":
                text = extract_docx(filepath)
                if text:
                    stats['docx'] += 1
            
            if text:
                text_parts.append(text)
                sources.append(f"{filename} ({actual_type})")
            else:
                stats['failed'] += 1
        
        if sources == ["csv"]:
            stats['csv_only'] += 1
        
        combined = "\n\n".join(text_parts)
        
        results.append({
            'id': fid,
            'organization': fb.get('organization', ''),
            'country': fb.get('country', ''),
            'userType': fb.get('userType', ''),
            'firstName': fb.get('firstName', ''),
            'surname': fb.get('surname', ''),
            'language': fb.get('language', ''),
            'date': fb.get('date', ''),
            'sources': sources,
            'text': combined,
            'text_length': len(combined),
            'has_attachment': any(s != 'csv' for s in sources)
        })
    
    # Stats
    log("\n" + "=" * 60)
    log("EXTRACTION COMPLETE")
    log("=" * 60)
    
    with_text = sum(1 for r in results if r['text'])
    log(f"✓ Extracted text from {with_text}/{len(results)} responses")
    log(f"  - PDFs: {stats['pdf']}")
    log(f"  - DOCXs: {stats['docx']}")
    log(f"  - CSV text only: {stats['csv_only']}")
    log(f"  - Failed: {stats['failed']}")
    
    # Save
    log(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    log(f"✓ Saved! File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    
    log("\n" + "=" * 60)
    log("Now re-run: python semantic_analysis.py")
    log("(It will use the pre-extracted texts automatically)")
    log("=" * 60)

if __name__ == "__main__":
    main()

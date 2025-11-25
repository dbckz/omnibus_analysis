#!/usr/bin/env python3
"""
Step 1: Extract text from all Digital Omnibus consultation responses.

This script extracts text from PDFs, DOCXs, and the feedback_text column,
saving everything to a JSON file for subsequent analysis.

Run this first, then run semantic_analysis.py
"""

import os
import sys
import json
import csv
import re
from pathlib import Path
from datetime import datetime

# Install dependencies if needed
def check_deps():
    try:
        import pdfplumber
        from docx import Document
    except ImportError:
        print("Installing required packages...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                             "pdfplumber", "python-docx", "-q"])
        print("✓ Done")

check_deps()

import pdfplumber
from docx import Document

# Configuration
DATA_DIR = Path("20401_digital_omnibus")
ATTACHMENTS_DIR = DATA_DIR / "attachments"
FEEDBACKS_CSV = DATA_DIR / "feedbacks.csv"
OUTPUT_FILE = DATA_DIR / "extracted_texts.json"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

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
    log("TEXT EXTRACTION FOR DIGITAL OMNIBUS RESPONSES")
    log("=" * 60)
    
    if not FEEDBACKS_CSV.exists():
        log(f"❌ {FEEDBACKS_CSV} not found. Run the download script first.")
        return
    
    # Load feedbacks
    log("Loading feedbacks.csv...")
    feedbacks = []
    with open(FEEDBACKS_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            feedbacks.append(row)
    log(f"  Found {len(feedbacks)} entries")
    
    # Build attachment map
    log("Scanning attachments...")
    attachment_map = {}
    if ATTACHMENTS_DIR.exists():
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
    log("Extracting text from all responses...")
    results = []
    
    for i, fb in enumerate(feedbacks, 1):
        if i % 50 == 0:
            log(f"  Processing {i}/{len(feedbacks)}...")
        
        fid = str(fb.get('id', ''))
        
        # Start with feedback text from CSV
        text_parts = []
        feedback_text = fb.get('feedback_text', '').strip()
        if feedback_text:
            text_parts.append(("csv", feedback_text))
        
        # Extract from attachments
        for filename in attachment_map.get(fid, []):
            filepath = ATTACHMENTS_DIR / filename
            if filepath.exists():
                ext = filepath.suffix.lower()
                if ext == '.pdf':
                    t = extract_pdf(filepath)
                elif ext in ['.docx', '.doc']:
                    t = extract_docx(filepath)
                else:
                    try:
                        t = filepath.read_text(errors='ignore')
                    except:
                        t = ""
                
                if t:
                    text_parts.append((filename, t))
        
        # Combine
        combined = "\n\n".join([t for _, t in text_parts])
        
        results.append({
            'id': fid,
            'organization': fb.get('organization', ''),
            'country': fb.get('country', ''),
            'userType': fb.get('userType', ''),
            'firstName': fb.get('firstName', ''),
            'surname': fb.get('surname', ''),
            'language': fb.get('language', ''),
            'date': fb.get('date', ''),
            'sources': [s for s, _ in text_parts],
            'text': combined,
            'text_length': len(combined),
            'has_attachment': any(s != 'csv' for s, _ in text_parts)
        })
    
    # Stats
    with_text = sum(1 for r in results if r['text'])
    with_attachments = sum(1 for r in results if r['has_attachment'])
    text_only = sum(1 for r in results if r['text'] and not r['has_attachment'])
    
    log(f"  ✓ Extracted text from {with_text} responses")
    log(f"    - From attachments: {with_attachments}")
    log(f"    - Text-only (no attachment): {text_only}")
    
    # Save
    log(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    log(f"✓ Done! Extracted texts saved to {OUTPUT_FILE}")
    log(f"  File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    
    # Preview
    log("\nSample entries:")
    for r in results[:3]:
        org = r['organization'] or f"{r['firstName']} {r['surname']}"
        log(f"  - {org}: {r['text_length']} chars from {len(r['sources'])} source(s)")

if __name__ == "__main__":
    main()

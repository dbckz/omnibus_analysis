#!/usr/bin/env python3
"""
Check what's actually in the downloaded "PDF" files to see why they're corrupted.
"""

from pathlib import Path

# Check the attachments directory
attachments_dir = Path("20401_digital_omnibus/attachments")

if not attachments_dir.exists():
    print(f"Directory not found: {attachments_dir}")
    print("Please run this from the directory containing '20401_digital_omnibus/'")
    exit(1)

pdf_files = list(attachments_dir.glob("*.pdf"))

if not pdf_files:
    print("No PDF files found")
    exit(1)

print(f"Found {len(pdf_files)} PDF files")
print("\nChecking first 5 files...\n")

for pdf_file in pdf_files[:5]:
    print("="*70)
    print(f"File: {pdf_file.name}")
    print(f"Size: {pdf_file.stat().st_size} bytes")
    print("-"*70)
    
    with open(pdf_file, 'rb') as f:
        first_bytes = f.read(500)
    
    # Check if it's a real PDF
    if first_bytes.startswith(b'%PDF'):
        print("✓ Valid PDF file (starts with %PDF)")
    else:
        print("✗ NOT a PDF file!")
        print("\nFirst 500 bytes:")
        try:
            # Try to decode as text
            content = first_bytes.decode('utf-8', errors='replace')
            print(content)
            
            # Check if it's HTML
            if '<html' in content.lower() or '<!doctype' in content.lower():
                print("\n⚠️  This is an HTML page, not a PDF!")
                print("   The download URL is returning a web page instead of the file.")
        except:
            # Binary data that's not UTF-8
            print(first_bytes[:200])
    
    print()

print("="*70)
print("\nRECOMMENDATION:")
print("Run: python diagnose_pdf_downloads.py")
print("This will test different download URLs to find the correct one.")

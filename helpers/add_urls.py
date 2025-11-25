#!/usr/bin/env python3
"""
Add a URL column to feedbacks.csv for easy access to each feedback on the EC website.
"""

import csv
from pathlib import Path

INPUT_FILE = Path("20401_digital_omnibus/feedbacks.csv")
OUTPUT_FILE = Path("20401_digital_omnibus/feedbacks_with_urls.csv")

BASE_URL = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/F"
URL_SUFFIX = "_en"

def main():
    print("=" * 70)
    print("Adding URL column to feedbacks.csv")
    print("=" * 70)
    
    if not INPUT_FILE.exists():
        print(f"\n❌ Error: {INPUT_FILE} not found!")
        print("Please run the download script first.")
        return
    
    # Read the CSV
    print(f"\nReading {INPUT_FILE}...")
    rows = []
    fieldnames = []
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            # Add URL column
            feedback_id = row.get('id', '')
            if feedback_id:
                row['url'] = f"{BASE_URL}{feedback_id}{URL_SUFFIX}"
            else:
                row['url'] = ""
            
            rows.append(row)
    
    print(f"  ✓ Read {len(rows)} feedback submissions")
    
    # Add 'url' to fieldnames if not already there
    if 'url' not in fieldnames:
        fieldnames = list(fieldnames) + ['url']
    
    # Write the new CSV
    print(f"\nWriting to {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  ✓ Saved {len(rows)} rows with URL column")
    
    # Show some examples
    print("\n" + "=" * 70)
    print("Sample URLs (first 5 entries):")
    print("=" * 70)
    
    for i, row in enumerate(rows[:5], 1):
        org = row.get('organization', 'N/A')
        url = row.get('url', 'N/A')
        print(f"\n{i}. {org}")
        print(f"   {url}")
    
    print("\n" + "=" * 70)
    print("✅ DONE!")
    print("=" * 70)
    print(f"\nOutput file: {OUTPUT_FILE.absolute()}")
    print("\nYou can now:")
    print("  1. Open the CSV in Excel/Numbers/Google Sheets")
    print("  2. Search for any organization")
    print("  3. Click the URL to view their feedback on the EC website")
    print("\nExample URL format:")
    print("  https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/F33089115_en")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Diagnose the DOCX files that failed to extract.
Check if they're actually .doc (binary), corrupted, or HTML error pages.
"""

import os
from pathlib import Path

DATA_DIR = Path("20401_digital_omnibus")
ATTACHMENTS_DIR = DATA_DIR / "attachments"

# Files that failed (from the error output)
FAILED_FILES = [
    "27567020_Aanbevelingen voor AI Kapitein – Risicoscenario's en gedrag.docx",
    "27566983_Nordic positionpaper and proposals GDPR .docx",
    "27566974_WindEurope's resposne to the Digital Omnibus Consultation.docx",
    "27566961_EE proposals on simplification.docx",
    "27566959_Final version of Policy Brief - for submission v2.docx",
    "27566936_20251014 - Key messages Afep - Digital Omnibus.docx",
    "27566933_Advocacy Memo DORA & Data Act.docx",
    "27566891_Euroconsumers_Digital Omnibus Submission_Cookie fatigue.docx",
    "27566856_NBs-MDRIVDR-Call-For-Evidence-DG-Connect-20251013-rev.docx",
    "27566750_20251310_ EFAMRO_Final_Digital Omnibus _vF.docx",
    "27566722_EFAMA Response_CfE Digital Omnibus.docx",
    "27566698_20251009_Digital Omnibus_Have your say EAPB comments.docx",
    "27566676_Confindustria proposta di rinvio Regolamento macchine e CRA 14 10 2025.docx",
    "27566632_MML Lausunto kannanottopyyntöön digitaalialan koontipaketista (digitaalialan yksinkertaistamispaketti).docx",
    "27566629_20251014 FFE digital package call for evidence.docx",
    "27566576_20251014_digital_omnibus_consultation.docx",
    "27566419_Digital_Omnibus_Response.docx",
    "27566376_NFU Reply on Call for Evidence_Digital Omnibus.docx",
    "27566375_Begeleidende Brief.docx",
    "27566370_VNG Contribution - Call for evidence Digital Omnibus.docx",
    "27566347_Response to Digital Omnibus- ENCIRCLE.docx",
    "27566136_Submission to Digital Omnibus_Oct25.docx",
    "27565985_Simplification Proposal.docx",
    "27563960_FiCom on digital omnibus .docx",
]

def get_file_type(filepath):
    """Determine actual file type by examining magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(20)
        
        # Check for various file signatures
        if header[:4] == b'PK\x03\x04':
            return "ZIP/DOCX (valid)"
        elif header[:4] == b'\xD0\xCF\x11\xE0':
            return "OLE/DOC (old Word format)"
        elif header[:5] == b'%PDF-':
            return "PDF"
        elif header[:5] == b'<!DOC' or header[:5] == b'<html' or header[:5] == b'<HTML':
            return "HTML (error page?)"
        elif header[:4] == b'{\rtf':
            return "RTF"
        elif b'<' in header[:10]:
            return "XML/HTML (likely error page)"
        else:
            return f"Unknown: {header[:10]}"
    except Exception as e:
        return f"Error reading: {e}"

def main():
    print("=" * 70)
    print("DOCX FILE DIAGNOSTIC")
    print("=" * 70)
    print()
    
    results = {
        "ZIP/DOCX (valid)": [],
        "OLE/DOC (old Word format)": [],
        "HTML (error page?)": [],
        "XML/HTML (likely error page)": [],
        "Other": []
    }
    
    for filename in FAILED_FILES:
        filepath = ATTACHMENTS_DIR / filename
        
        if not filepath.exists():
            print(f"❌ Not found: {filename}")
            continue
        
        file_type = get_file_type(filepath)
        size = filepath.stat().st_size
        
        print(f"\n📄 {filename}")
        print(f"   Size: {size:,} bytes ({size/1024:.1f} KB)")
        print(f"   Type: {file_type}")
        
        # Show first few bytes as text if it looks like HTML
        if "HTML" in file_type or "XML" in file_type:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    preview = f.read(200)
                print(f"   Preview: {preview[:100]}...")
            except:
                pass
        
        # Categorize
        if "DOC (old" in file_type:
            results["OLE/DOC (old Word format)"].append(filename)
        elif "HTML" in file_type or "XML" in file_type:
            results["HTML (error page?)"].append(filename)
        elif "ZIP/DOCX" in file_type:
            results["ZIP/DOCX (valid)"].append(filename)
        else:
            results["Other"].append(filename)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for category, files in results.items():
        if files:
            print(f"\n{category}: {len(files)} files")
            for f in files[:5]:
                print(f"  - {f[:60]}...")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")
    
    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if results["OLE/DOC (old Word format)"]:
        print(f"\n✓ {len(results['OLE/DOC (old Word format)'])} files are old .doc format")
        print("  → Can extract with 'antiword' or 'textract' library")
    
    if results["HTML (error page?)"] or results["XML/HTML (likely error page)"]:
        n = len(results["HTML (error page?)"]) + len(results["XML/HTML (likely error page)"])
        print(f"\n⚠ {n} files appear to be HTML error pages")
        print("  → These may need to be re-downloaded from the EC website")

if __name__ == "__main__":
    main()

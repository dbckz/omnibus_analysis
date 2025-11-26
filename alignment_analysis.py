#!/usr/bin/env python3
"""
LLM-Based Alignment Analysis

Compares each response's positions to OpenMined's positions using Claude.
Much more meaningful than semantic similarity - actually understands policy alignment.
"""

import json
import os
import subprocess
import sys
import time
import re
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("20401_digital_omnibus")
EXTRACTED_TEXTS = DATA_DIR / "extracted_texts.json"
LLM_ANALYSIS_DIR = DATA_DIR / "llm_analysis"
OUTPUT_DIR = DATA_DIR / "alignment_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)

# OpenMined's feedback ID
OPENMINED_ID = "33089115"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def call_claude(prompt, max_retries=3, timeout=180):
    """Call Claude Code CLI with a prompt."""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ['claude', '-p', prompt, '--output-format', 'text'],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, 'NO_COLOR': '1'}
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None
                
        except subprocess.TimeoutExpired:
            log(f"  Warning: Timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
            return None
        except Exception as e:
            log(f"  Warning: Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None
    
    return None

def get_display_name(item):
    """Get display name."""
    org = item.get('organization', '')
    if org:
        return org
    first = item.get('firstName', '')
    last = item.get('surname', '')
    name = f"{first} {last}".strip()
    return name if name else "Anonymous"

def extract_openmined_positions(openmined_text):
    """Use Claude to extract OpenMined's key positions."""
    log("Extracting OpenMined's key positions...")
    
    prompt = f"""Analyse this consultation response from OpenMined and extract their KEY POLICY POSITIONS.

OpenMined's Response:
{openmined_text[:12000]}

---

Identify OpenMined's specific positions on:
1. GDPR and data protection safeguards
2. Privacy-enhancing technologies (PETs)
3. Legitimate interest provisions
4. Pseudonymisation / de-identification
5. AI Act and AI governance
6. Any other key policy positions

Return JSON:
{{
  "core_positions": [
    {{
      "topic": "Topic name",
      "position": "Clear statement of OpenMined's position",
      "key_quote": "Supporting quote from their text"
    }}
  ],
  "overall_stance": "Brief summary of OpenMined's overall approach"
}}

Return ONLY JSON."""

    response = call_claude(prompt, timeout=120)
    
    if response:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
    
    return None

def evaluate_alignment(response_text, response_name, openmined_positions):
    """Evaluate how aligned a response is with OpenMined's positions."""
    
    positions_summary = "\n".join([
        f"- {p['topic']}: {p['position']}" 
        for p in openmined_positions.get('core_positions', [])
    ])
    
    prompt = f"""Compare this consultation response to OpenMined's positions.

OPENMINED'S KEY POSITIONS:
{positions_summary}

RESPONSE FROM: {response_name}
{response_text[:8000]}

---

Evaluate alignment with OpenMined on each topic. Return JSON:
{{
  "overall_alignment": "strongly_aligned" | "mostly_aligned" | "partially_aligned" | "neutral" | "partially_opposed" | "mostly_opposed" | "strongly_opposed",
  "alignment_score": 1-10 (10 = perfectly aligned with OpenMined),
  "alignment_summary": "2-3 sentences explaining the alignment or differences",
  "topic_alignments": [
    {{
      "topic": "Topic name",
      "alignment": "aligned" | "neutral" | "opposed" | "not_mentioned",
      "explanation": "Brief explanation",
      "quote": "Supporting quote if available"
    }}
  ],
  "key_agreements": ["List of positions where they agree with OpenMined"],
  "key_disagreements": ["List of positions where they disagree with OpenMined"]
}}

Return ONLY JSON."""

    response = call_claude(prompt, timeout=120)
    
    if response:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
    
    return None

def load_progress():
    """Load previously analysed IDs."""
    progress_file = OUTPUT_DIR / "progress.json"
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return set(json.load(f))
    return set()

def save_progress(analysed_ids):
    """Save progress."""
    progress_file = OUTPUT_DIR / "progress.json"
    with open(progress_file, 'w') as f:
        json.dump(list(analysed_ids), f)

def save_results(results):
    """Save results."""
    results_file = OUTPUT_DIR / "alignment_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def generate_report(results, openmined_positions):
    """Generate alignment report."""
    
    # Sort by alignment score
    sorted_results = sorted(results, key=lambda x: x.get('alignment_score', 0), reverse=True)
    
    lines = []
    lines.append("# Alignment with OpenMined's Positions")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nResponses analysed: {len(results)}")
    lines.append("")
    
    # OpenMined's positions summary
    lines.append("## OpenMined's Key Positions")
    lines.append("")
    for p in openmined_positions.get('core_positions', []):
        lines.append(f"### {p.get('topic', 'Unknown')}")
        lines.append(f"{p.get('position', 'N/A')}")
        if p.get('key_quote'):
            lines.append(f"> \"{p['key_quote']}\"")
        lines.append("")
    
    # Most aligned
    lines.append("---")
    lines.append("## Most Aligned with OpenMined")
    lines.append("")
    
    for r in sorted_results[:25]:
        score = r.get('alignment_score', 0)
        lines.append(f"### {r['display_name']} ({r.get('country', '')}) - Score: {score}/10")
        lines.append(f"*{r.get('overall_alignment', 'unknown')}*")
        lines.append(f"[View submission]({r.get('url', '')})")
        lines.append("")
        lines.append(f"{r.get('alignment_summary', 'N/A')}")
        lines.append("")
        
        agreements = r.get('key_agreements', [])
        if agreements:
            lines.append("**Agrees with OpenMined on:**")
            for a in agreements[:3]:
                lines.append(f"- {a}")
            lines.append("")
    
    # Least aligned / opposed
    lines.append("---")
    lines.append("## Least Aligned / Opposed to OpenMined")
    lines.append("")
    
    for r in sorted_results[-25:]:
        score = r.get('alignment_score', 0)
        if score >= 5:  # Skip if not actually opposed
            continue
        lines.append(f"### {r['display_name']} ({r.get('country', '')}) - Score: {score}/10")
        lines.append(f"*{r.get('overall_alignment', 'unknown')}*")
        lines.append(f"[View submission]({r.get('url', '')})")
        lines.append("")
        lines.append(f"{r.get('alignment_summary', 'N/A')}")
        lines.append("")
        
        disagreements = r.get('key_disagreements', [])
        if disagreements:
            lines.append("**Disagrees with OpenMined on:**")
            for d in disagreements[:3]:
                lines.append(f"- {d}")
            lines.append("")
    
    # By alignment category
    lines.append("---")
    lines.append("## Summary by Alignment Category")
    lines.append("")
    
    categories = {}
    for r in results:
        cat = r.get('overall_alignment', 'unknown')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r['display_name'])
    
    for cat in ['strongly_aligned', 'mostly_aligned', 'partially_aligned', 'neutral', 
                'partially_opposed', 'mostly_opposed', 'strongly_opposed']:
        if cat in categories:
            lines.append(f"### {cat.replace('_', ' ').title()} ({len(categories[cat])})")
            for name in categories[cat][:10]:
                lines.append(f"- {name}")
            if len(categories[cat]) > 10:
                lines.append(f"- ...and {len(categories[cat]) - 10} more")
            lines.append("")
    
    return "\n".join(lines)

def main():
    log("=" * 70)
    log("LLM-BASED ALIGNMENT ANALYSIS")
    log("=" * 70)
    
    # Load extracted texts
    log("\nLoading extracted texts...")
    with open(EXTRACTED_TEXTS, 'r', encoding='utf-8') as f:
        all_texts = json.load(f)
    
    # Create lookup
    texts_by_id = {str(item['id']): item for item in all_texts}
    
    # Find OpenMined's response
    if OPENMINED_ID not in texts_by_id:
        log(f"ERROR: OpenMined response (ID {OPENMINED_ID}) not found")
        return
    
    openmined_data = texts_by_id[OPENMINED_ID]
    openmined_text = openmined_data.get('text', '')
    log(f"  Found OpenMined response: {len(openmined_text)} chars")
    
    # Extract OpenMined's positions
    positions_file = OUTPUT_DIR / "openmined_positions.json"
    if positions_file.exists():
        log("  Loading cached OpenMined positions...")
        with open(positions_file, 'r') as f:
            openmined_positions = json.load(f)
    else:
        openmined_positions = extract_openmined_positions(openmined_text)
        if openmined_positions:
            with open(positions_file, 'w', encoding='utf-8') as f:
                json.dump(openmined_positions, f, indent=2, ensure_ascii=False)
            log("  ✓ Extracted and cached OpenMined positions")
        else:
            log("  ✗ Failed to extract OpenMined positions")
            return
    
    # Show OpenMined's positions
    log("\nOpenMined's key positions:")
    for p in openmined_positions.get('core_positions', [])[:5]:
        log(f"  - {p.get('topic', 'Unknown')}: {p.get('position', 'N/A')[:80]}...")
    
    # Load progress
    analysed_ids = load_progress()
    
    # Load existing results
    results_file = OUTPUT_DIR / "alignment_results.json"
    if results_file.exists():
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    else:
        results = []
    
    # Filter responses to analyse (exclude OpenMined, require substantial text)
    to_analyse = [
        item for item in all_texts 
        if str(item['id']) != OPENMINED_ID 
        and len(item.get('text', '')) > 200
        and str(item['id']) not in analysed_ids
    ]
    
    log(f"\nResponses to analyse: {len(to_analyse)}")
    log(f"Previously analysed: {len(analysed_ids)}")
    
    if not to_analyse:
        log("\nAll responses already analysed!")
    else:
        log("\nAnalysing alignment...")
        log("(Progress saved every 5 responses - safe to interrupt)")
        log("")
    
    for i, item in enumerate(to_analyse, 1):
        display_name = get_display_name(item)
        log(f"[{i}/{len(to_analyse)}] {display_name[:50]}...")
        
        alignment = evaluate_alignment(
            item.get('text', ''),
            display_name,
            openmined_positions
        )
        
        if alignment:
            alignment['id'] = item['id']
            alignment['display_name'] = display_name
            alignment['country'] = item.get('country', '')
            alignment['userType'] = item.get('userType', '')
            alignment['url'] = f"https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/F{item['id']}_en"
            
            results.append(alignment)
            analysed_ids.add(str(item['id']))
            
            score = alignment.get('alignment_score', '?')
            overall = alignment.get('overall_alignment', 'unknown')
            log(f"  ✓ Score: {score}/10 ({overall})")
            
            # Save progress
            if i % 5 == 0:
                save_progress(analysed_ids)
                save_results(results)
                log(f"  Progress saved ({len(results)} total)")
        else:
            log(f"  ✗ Failed")
        
        time.sleep(2)  # Rate limiting
    
    # Final save
    save_progress(analysed_ids)
    save_results(results)
    
    # Generate report
    log("\nGenerating report...")
    report = generate_report(results, openmined_positions)
    report_file = OUTPUT_DIR / "alignment_report.md"
    report_file.write_text(report)
    log(f"  Saved to {report_file}")
    
    # Summary
    log("\n" + "=" * 70)
    log("ALIGNMENT ANALYSIS COMPLETE")
    log("=" * 70)
    
    if results:
        sorted_results = sorted(results, key=lambda x: x.get('alignment_score', 0), reverse=True)
        
        log("\nTop 5 most aligned with OpenMined:")
        for r in sorted_results[:5]:
            log(f"  {r.get('alignment_score', '?')}/10 - {r['display_name']}")
        
        log("\nTop 5 least aligned with OpenMined:")
        for r in sorted_results[-5:]:
            log(f"  {r.get('alignment_score', '?')}/10 - {r['display_name']}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Theme Aggregation Analysis

After running llm_analysis.py, this script:
1. Loads all individual analyses
2. Uses Claude to identify common themes and arguments across responses
3. Generates a report grouping similar arguments with attribution
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

DATA_DIR = Path("20401_digital_omnibus")
OUTPUT_DIR = DATA_DIR / "llm_analysis"
RESULTS_FILE = OUTPUT_DIR / "analysis_results.json"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def call_claude(prompt, max_retries=3):
    """Call Claude Code CLI with a prompt."""
    import time
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ['claude', '-p', prompt, '--output-format', 'text'],
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout for longer analysis
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                log(f"  Warning: Claude CLI error: {result.stderr[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None
                
        except subprocess.TimeoutExpired:
            log(f"  Warning: Timeout (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None
        except Exception as e:
            log(f"  Warning: Error: {e}")
            return None
    
    return None

def chunk_list(lst, chunk_size):
    """Split a list into chunks."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def main():
    log("=" * 70)
    log("THEME AGGREGATION ANALYSIS")
    log("=" * 70)
    
    if not RESULTS_FILE.exists():
        log(f"ERROR: {RESULTS_FILE} not found")
        log("Please run llm_analysis.py first")
        return
    
    # Load results
    log("\nLoading analysis results...")
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        results = json.load(f)
    log(f"  Loaded {len(results)} analysed responses")
    
    # Collect all arguments with attribution
    log("\nCollecting all arguments...")
    all_arguments = []
    for r in results:
        args = r.get('key_arguments', [])
        for arg in args:
            if arg and len(arg) > 10:
                all_arguments.append({
                    'argument': arg,
                    'org': r.get('display_name', 'Unknown'),
                    'country': r.get('country', ''),
                    'stance': r.get('privacy_stance', 'unknown')
                })
    
    log(f"  Found {len(all_arguments)} individual arguments")
    
    # Collect notable quotes by topic
    log("\nCollecting quotes by topic...")
    quotes_by_topic = defaultdict(list)
    for r in results:
        quotes = r.get('notable_quotes', [])
        for q in quotes:
            if q.get('topic') and q.get('quote'):
                quotes_by_topic[q['topic'].lower()].append({
                    'quote': q['quote'],
                    'org': r.get('display_name', 'Unknown'),
                    'country': r.get('country', '')
                })
    
    log(f"  Found quotes on {len(quotes_by_topic)} topics")
    
    # Use Claude to identify common themes
    log("\nIdentifying common themes across arguments...")
    
    # Prepare a summary of arguments for theme analysis
    # Group by stance first
    pro_protection_args = [a for a in all_arguments if a['stance'] == 'pro_protection']
    pro_simplification_args = [a for a in all_arguments if a['stance'] == 'pro_simplification']
    
    # Analyse pro-protection themes
    log("\n  Analysing pro-protection themes...")
    if pro_protection_args:
        args_text = "\n".join([f"- {a['argument']} ({a['org']}, {a['country']})" 
                               for a in pro_protection_args[:100]])  # Limit to avoid token limits
        
        prompt = f"""Here are arguments from consultation responses that DEFEND privacy safeguards:

{args_text}

Identify the 5-10 most common THEMES or ARGUMENT TYPES across these responses. 
For each theme, provide:
1. A clear theme name
2. A summary of the argument
3. List which organisations made this argument

Return as JSON:
{{
  "themes": [
    {{
      "theme_name": "Name of theme",
      "summary": "What these respondents are arguing",
      "organisations": ["Org 1", "Org 2", "Org 3"]
    }}
  ]
}}

Return ONLY the JSON."""

        response = call_claude(prompt)
        if response:
            try:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    pro_protection_themes = json.loads(json_match.group())
                else:
                    pro_protection_themes = {"themes": []}
            except:
                pro_protection_themes = {"themes": []}
        else:
            pro_protection_themes = {"themes": []}
    else:
        pro_protection_themes = {"themes": []}
    
    # Analyse pro-simplification themes
    log("  Analysing pro-simplification themes...")
    if pro_simplification_args:
        args_text = "\n".join([f"- {a['argument']} ({a['org']}, {a['country']})" 
                               for a in pro_simplification_args[:100]])
        
        prompt = f"""Here are arguments from consultation responses that support LOOSENING/SIMPLIFYING privacy rules:

{args_text}

Identify the 5-10 most common THEMES or ARGUMENT TYPES across these responses.
For each theme, provide:
1. A clear theme name
2. A summary of the argument
3. List which organisations made this argument

Return as JSON:
{{
  "themes": [
    {{
      "theme_name": "Name of theme",
      "summary": "What these respondents are arguing",
      "organisations": ["Org 1", "Org 2", "Org 3"]
    }}
  ]
}}

Return ONLY the JSON."""

        response = call_claude(prompt)
        if response:
            try:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    pro_simplification_themes = json.loads(json_match.group())
                else:
                    pro_simplification_themes = {"themes": []}
            except:
                pro_simplification_themes = {"themes": []}
        else:
            pro_simplification_themes = {"themes": []}
    else:
        pro_simplification_themes = {"themes": []}
    
    # Generate comprehensive report
    log("\nGenerating theme report...")
    
    lines = []
    lines.append("# Digital Omnibus - Common Themes Analysis")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nBased on {len(results)} analysed responses")
    lines.append("")
    
    # Summary stats
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"- Total responses analysed: {len(results)}")
    lines.append(f"- Pro-protection responses: {len([r for r in results if r.get('privacy_stance') == 'pro_protection'])}")
    lines.append(f"- Pro-simplification responses: {len([r for r in results if r.get('privacy_stance') == 'pro_simplification'])}")
    lines.append(f"- Responses mentioning PETs: {len([r for r in results if r.get('mentions_pets')])}")
    lines.append(f"- Responses discussing pseudonymisation issues: {len([r for r in results if r.get('mentions_pseudonymisation_problems')])}")
    lines.append(f"- Responses discussing legitimate interest: {len([r for r in results if r.get('mentions_legitimate_interest')])}")
    lines.append("")
    
    # Pro-protection themes
    lines.append("---")
    lines.append("## Common Themes: DEFENDING Privacy Safeguards")
    lines.append("")
    
    if pro_protection_themes.get('themes'):
        for i, theme in enumerate(pro_protection_themes['themes'], 1):
            lines.append(f"### {i}. {theme.get('theme_name', 'Unknown Theme')}")
            lines.append("")
            lines.append(f"**Summary**: {theme.get('summary', 'N/A')}")
            lines.append("")
            orgs = theme.get('organisations', [])
            if orgs:
                lines.append(f"**Organisations making this argument** ({len(orgs)}):")
                for org in orgs[:10]:
                    lines.append(f"- {org}")
                if len(orgs) > 10:
                    lines.append(f"- ...and {len(orgs) - 10} more")
            lines.append("")
    else:
        lines.append("*No themes identified*")
    
    # Pro-simplification themes
    lines.append("---")
    lines.append("## Common Themes: SUPPORTING Simplification/Loosening")
    lines.append("")
    
    if pro_simplification_themes.get('themes'):
        for i, theme in enumerate(pro_simplification_themes['themes'], 1):
            lines.append(f"### {i}. {theme.get('theme_name', 'Unknown Theme')}")
            lines.append("")
            lines.append(f"**Summary**: {theme.get('summary', 'N/A')}")
            lines.append("")
            orgs = theme.get('organisations', [])
            if orgs:
                lines.append(f"**Organisations making this argument** ({len(orgs)}):")
                for org in orgs[:10]:
                    lines.append(f"- {org}")
                if len(orgs) > 10:
                    lines.append(f"- ...and {len(orgs) - 10} more")
            lines.append("")
    else:
        lines.append("*No themes identified*")
    
    # PETs section with full detail
    lines.append("---")
    lines.append("## Detailed: Privacy-Enhancing Technologies Mentions")
    lines.append("")
    
    pet_responses = [r for r in results if r.get('mentions_pets')]
    for r in pet_responses:
        lines.append(f"### {r.get('display_name', 'Unknown')} ({r.get('country', '')})")
        lines.append(f"[View submission]({r.get('url', '')})")
        lines.append("")
        if r.get('pet_details'):
            lines.append(f"{r['pet_details']}")
            lines.append("")
        if r.get('pet_quote'):
            lines.append(f"> \"{r['pet_quote']}\"")
            lines.append("")
    
    # Pseudonymisation section
    lines.append("---")
    lines.append("## Detailed: Pseudonymisation/De-identification Concerns")
    lines.append("")
    
    pseudo_responses = [r for r in results if r.get('mentions_pseudonymisation_problems')]
    for r in pseudo_responses:
        lines.append(f"### {r.get('display_name', 'Unknown')} ({r.get('country', '')})")
        lines.append(f"[View submission]({r.get('url', '')})")
        lines.append("")
        if r.get('pseudonymisation_details'):
            lines.append(f"{r['pseudonymisation_details']}")
            lines.append("")
        if r.get('pseudonymisation_quote'):
            lines.append(f"> \"{r['pseudonymisation_quote']}\"")
            lines.append("")
    
    # Save report
    report_file = OUTPUT_DIR / "themes_report.md"
    report_file.write_text("\n".join(lines))
    log(f"\n✓ Saved theme report to {report_file}")
    
    # Save raw theme data
    themes_data = {
        'pro_protection_themes': pro_protection_themes,
        'pro_simplification_themes': pro_simplification_themes,
        'quotes_by_topic': dict(quotes_by_topic)
    }
    themes_json = OUTPUT_DIR / "themes_data.json"
    with open(themes_json, 'w', encoding='utf-8') as f:
        json.dump(themes_data, f, indent=2, ensure_ascii=False)
    log(f"✓ Saved theme data to {themes_json}")
    
    # Print summary
    log("\n" + "=" * 70)
    log("THEME ANALYSIS COMPLETE")
    log("=" * 70)
    
    if pro_protection_themes.get('themes'):
        log("\nPro-protection themes found:")
        for t in pro_protection_themes['themes'][:5]:
            log(f"  - {t.get('theme_name', 'Unknown')}")
    
    if pro_simplification_themes.get('themes'):
        log("\nPro-simplification themes found:")
        for t in pro_simplification_themes['themes'][:5]:
            log(f"  - {t.get('theme_name', 'Unknown')}")

if __name__ == "__main__":
    main()

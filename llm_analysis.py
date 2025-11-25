#!/usr/bin/env python3
"""
LLM-Based Content Analysis for Digital Omnibus Responses
Uses Claude Code CLI as the backend (works with Max subscription)

This script analyses each response for:
1. Stance on privacy safeguards (pro-protection vs pro-loosening)
2. Mentions of PETs, federation, pseudonymisation
3. Key arguments and recommendations
4. Extracts relevant quotes with attribution
"""

import json
import subprocess
import sys
import time
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = Path("20401_digital_omnibus")
EXTRACTED_TEXTS = DATA_DIR / "extracted_texts.json"
OUTPUT_DIR = DATA_DIR / "llm_analysis"
OUTPUT_DIR.mkdir(exist_ok=True)

# Analysis configuration
BATCH_SIZE = 1  # Analyse one at a time for accuracy
MAX_TEXT_LENGTH = 8000  # Truncate very long texts (reduced to avoid timeouts)
DELAY_BETWEEN_CALLS = 2  # Seconds between API calls

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_display_name(item):
    """Get display name (org or individual name)."""
    org = item.get('organization', '')
    if org:
        return org
    first = item.get('firstName', '')
    last = item.get('surname', '')
    name = f"{first} {last}".strip()
    return name if name else "Anonymous"

def call_claude(prompt, max_retries=3, timeout=180):
    """Call Claude Code CLI with a prompt and return the response."""
    for attempt in range(max_retries):
        try:
            # Use claude CLI with -p flag to just get the response
            result = subprocess.run(
                ['claude', '-p', prompt, '--output-format', 'text'],
                capture_output=True,
                text=True,
                timeout=timeout  # 3 minute timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                log(f"  Warning: Claude CLI returned error: {result.stderr[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return None
                
        except subprocess.TimeoutExpired:
            log(f"  Warning: Claude CLI timed out after {timeout}s (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(10)  # Longer wait between retries
                continue
            return None
        except FileNotFoundError:
            log("ERROR: 'claude' command not found. Please install Claude Code:")
            log("  npm install -g @anthropic-ai/claude-code")
            log("  claude  # to authenticate")
            sys.exit(1)
        except Exception as e:
            log(f"  Warning: Error calling Claude: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None
    
    return None

def analyse_response(item, use_short_prompt=False):
    """Analyse a single response using Claude."""
    display_name = get_display_name(item)
    country = item.get('country', '')
    user_type = item.get('userType', '')
    
    # Use shorter text for short prompt mode
    text_limit = 4000 if use_short_prompt else MAX_TEXT_LENGTH
    text = item.get('text', '')[:text_limit]
    
    if not text or len(text) < 100:
        return None
    
    if use_short_prompt:
        # Simpler, faster prompt
        prompt = f"""Briefly analyse this EU Digital Omnibus consultation response.

RESPONDENT: {display_name} ({country}, {user_type})

TEXT (truncated):
{text}

---

Return JSON only:
{{
  "privacy_stance": "pro_protection" | "pro_simplification" | "neutral" | "mixed",
  "privacy_stance_summary": "One sentence on their privacy position",
  "mentions_pets": true | false,
  "pet_quote": "Quote if they mention privacy-enhancing tech, otherwise null",
  "key_arguments": ["Main", "arguments"],
  "summary": "Brief summary"
}}"""
    else:
        prompt = f"""Analyse this consultation response to the EU Digital Omnibus package. 

RESPONDENT: {display_name}
COUNTRY: {country}
TYPE: {user_type}

RESPONSE TEXT:
{text}

---

Provide a JSON analysis with these exact fields:

{{
  "privacy_stance": "pro_protection" | "pro_simplification" | "neutral" | "mixed",
  "privacy_stance_confidence": "high" | "medium" | "low",
  "privacy_stance_summary": "One sentence explaining their position on privacy/data protection safeguards",
  
  "mentions_pets": true | false,
  "pet_details": "If they mention privacy-enhancing technologies, federation, secure computation, etc., explain what they say. Otherwise null.",
  "pet_quote": "Direct quote about PETs if available, otherwise null",
  
  "mentions_pseudonymisation_problems": true | false,
  "pseudonymisation_details": "If they discuss problems with de-identification or pseudonymisation, explain. Otherwise null.",
  "pseudonymisation_quote": "Direct quote if available, otherwise null",
  
  "mentions_legitimate_interest": true | false,
  "legitimate_interest_position": "If they discuss legitimate interest, what's their position? Otherwise null.",
  "legitimate_interest_quote": "Direct quote if available, otherwise null",
  
  "key_arguments": ["List", "of", "main", "arguments", "or", "recommendations"],
  
  "notable_quotes": [
    {{"topic": "topic name", "quote": "relevant direct quote from the text"}}
  ],
  
  "summary": "2-3 sentence summary of their overall position and key asks"
}}

Return ONLY the JSON object, no other text."""

    response = call_claude(prompt, timeout=180 if not use_short_prompt else 60)
    
    # If full prompt timed out, try short version
    if not response and not use_short_prompt:
        log(f"    Retrying with shorter prompt...")
        return analyse_response(item, use_short_prompt=True)
    
    if not response:
        return None
    
    # Try to parse JSON from response
    try:
        # Find JSON in response (claude might add some preamble)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            analysis = json.loads(json_match.group())
            analysis['id'] = item['id']
            analysis['display_name'] = display_name
            analysis['country'] = country
            analysis['userType'] = user_type
            analysis['url'] = f"https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/F{item['id']}_en"
            analysis['used_short_prompt'] = use_short_prompt
            return analysis
    except json.JSONDecodeError as e:
        log(f"  Warning: Could not parse JSON for {display_name}: {e}")
        # Save raw response for debugging
        debug_file = OUTPUT_DIR / f"debug_{item['id']}.txt"
        debug_file.write_text(response)
    
    return None

def load_progress():
    """Load previously analysed IDs to allow resuming."""
    progress_file = OUTPUT_DIR / "progress.json"
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return set(json.load(f))
    return set()

def save_progress(analysed_ids):
    """Save progress for resuming."""
    progress_file = OUTPUT_DIR / "progress.json"
    with open(progress_file, 'w') as f:
        json.dump(list(analysed_ids), f)

def save_results(results):
    """Save analysis results."""
    results_file = OUTPUT_DIR / "analysis_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def generate_report(results):
    """Generate a markdown report from the analysis results."""
    
    # Categorise by stance
    pro_protection = [r for r in results if r.get('privacy_stance') == 'pro_protection']
    pro_simplification = [r for r in results if r.get('privacy_stance') == 'pro_simplification']
    mixed = [r for r in results if r.get('privacy_stance') in ['mixed', 'neutral']]
    
    # Find PET mentions
    pet_mentions = [r for r in results if r.get('mentions_pets')]
    
    # Find pseudonymisation discussions
    pseudo_mentions = [r for r in results if r.get('mentions_pseudonymisation_problems')]
    
    # Find legitimate interest discussions
    legit_interest = [r for r in results if r.get('mentions_legitimate_interest')]
    
    lines = []
    
    lines.append("# Digital Omnibus Consultation - LLM Analysis Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"\nTotal responses analysed: {len(results)}")
    lines.append("")
    
    # Overview
    lines.append("## Overview of Privacy Stances")
    lines.append("")
    lines.append(f"- **Pro-protection** (defend current safeguards): {len(pro_protection)} responses")
    lines.append(f"- **Pro-simplification** (loosen safeguards): {len(pro_simplification)} responses")
    lines.append(f"- **Mixed/Neutral**: {len(mixed)} responses")
    lines.append("")
    
    # Pro-protection section
    lines.append("---")
    lines.append("## Responses DEFENDING Privacy Safeguards")
    lines.append("")
    for r in sorted(pro_protection, key=lambda x: x.get('privacy_stance_confidence', '') == 'high', reverse=True)[:20]:
        lines.append(f"### {r['display_name']} ({r['country']}, {r['userType']})")
        lines.append(f"[View submission]({r['url']})")
        lines.append("")
        lines.append(f"**Position**: {r.get('privacy_stance_summary', 'N/A')}")
        lines.append("")
        if r.get('notable_quotes'):
            for q in r['notable_quotes'][:2]:
                lines.append(f"> \"{q.get('quote', '')}\"")
                lines.append("")
        lines.append("")
    
    # Pro-simplification section
    lines.append("---")
    lines.append("## Responses Supporting LOOSENING Privacy Safeguards")
    lines.append("")
    for r in sorted(pro_simplification, key=lambda x: x.get('privacy_stance_confidence', '') == 'high', reverse=True)[:20]:
        lines.append(f"### {r['display_name']} ({r['country']}, {r['userType']})")
        lines.append(f"[View submission]({r['url']})")
        lines.append("")
        lines.append(f"**Position**: {r.get('privacy_stance_summary', 'N/A')}")
        lines.append("")
        if r.get('notable_quotes'):
            for q in r['notable_quotes'][:2]:
                lines.append(f"> \"{q.get('quote', '')}\"")
                lines.append("")
        lines.append("")
    
    # PETs section
    lines.append("---")
    lines.append("## Responses Mentioning Privacy-Enhancing Technologies")
    lines.append("")
    lines.append(f"Found {len(pet_mentions)} responses discussing PETs, federation, or similar technologies.")
    lines.append("")
    for r in pet_mentions:
        lines.append(f"### {r['display_name']} ({r['country']})")
        lines.append(f"[View submission]({r['url']})")
        lines.append("")
        if r.get('pet_details'):
            lines.append(f"**Details**: {r['pet_details']}")
            lines.append("")
        if r.get('pet_quote'):
            lines.append(f"> \"{r['pet_quote']}\"")
            lines.append("")
        lines.append("")
    
    # Pseudonymisation section
    lines.append("---")
    lines.append("## Responses Discussing Problems with De-identification/Pseudonymisation")
    lines.append("")
    lines.append(f"Found {len(pseudo_mentions)} responses discussing limitations of pseudonymisation.")
    lines.append("")
    for r in pseudo_mentions:
        lines.append(f"### {r['display_name']} ({r['country']})")
        lines.append(f"[View submission]({r['url']})")
        lines.append("")
        if r.get('pseudonymisation_details'):
            lines.append(f"**Details**: {r['pseudonymisation_details']}")
            lines.append("")
        if r.get('pseudonymisation_quote'):
            lines.append(f"> \"{r['pseudonymisation_quote']}\"")
            lines.append("")
        lines.append("")
    
    # Legitimate interest section
    lines.append("---")
    lines.append("## Responses Discussing Legitimate Interest")
    lines.append("")
    lines.append(f"Found {len(legit_interest)} responses discussing legitimate interest provisions.")
    lines.append("")
    for r in legit_interest:
        lines.append(f"### {r['display_name']} ({r['country']})")
        lines.append(f"[View submission]({r['url']})")
        lines.append("")
        if r.get('legitimate_interest_position'):
            lines.append(f"**Position**: {r['legitimate_interest_position']}")
            lines.append("")
        if r.get('legitimate_interest_quote'):
            lines.append(f"> \"{r['legitimate_interest_quote']}\"")
            lines.append("")
        lines.append("")
    
    # Common arguments section
    lines.append("---")
    lines.append("## Common Arguments and Themes")
    lines.append("")
    
    # Aggregate arguments
    all_arguments = []
    for r in results:
        args = r.get('key_arguments', [])
        if args:
            for arg in args:
                all_arguments.append((arg, r['display_name']))
    
    # Simple frequency analysis of argument keywords
    lines.append("*Note: A more sophisticated theme analysis would require processing all arguments together.*")
    lines.append("")
    lines.append(f"Total arguments extracted: {len(all_arguments)}")
    lines.append("")
    
    return "\n".join(lines)

def main():
    log("=" * 70)
    log("LLM-BASED CONTENT ANALYSIS (via Claude Code)")
    log("=" * 70)
    
    # Check Claude Code is available
    log("\nChecking Claude Code availability...")
    try:
        result = subprocess.run(['claude', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            log(f"  ✓ Claude Code version: {result.stdout.strip()}")
        else:
            log("  ✗ Claude Code not responding correctly")
            log("    Please run 'claude' to authenticate first")
            return
    except FileNotFoundError:
        log("  ✗ 'claude' command not found")
        log("    Install with: npm install -g @anthropic-ai/claude-code")
        return
    except Exception as e:
        log(f"  ✗ Error checking Claude Code: {e}")
        return
    
    # Quick test to make sure Claude is responding
    log("\nTesting Claude Code connection...")
    test_response = call_claude("Reply with just the word 'OK'", timeout=30)
    if test_response:
        log(f"  ✓ Claude responded: {test_response[:50]}")
    else:
        log("  ✗ Claude Code is not responding")
        log("    Try running 'claude' in your terminal to check authentication")
        return
    
    # Load data
    log("\nLoading extracted texts...")
    with open(EXTRACTED_TEXTS, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Filter to responses with substantial text
    data = [item for item in data if len(item.get('text', '')) > 200]
    log(f"  Found {len(data)} responses with substantial text")
    
    # Load progress (for resuming)
    analysed_ids = load_progress()
    log(f"  Previously analysed: {len(analysed_ids)} responses")
    
    # Load existing results
    results_file = OUTPUT_DIR / "analysis_results.json"
    if results_file.exists():
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    else:
        results = []
    
    # Filter to remaining items
    remaining = [item for item in data if item['id'] not in analysed_ids]
    log(f"  Remaining to analyse: {len(remaining)} responses")
    
    if not remaining:
        log("\nAll responses already analysed!")
    else:
        log(f"\nAnalysing {len(remaining)} responses...")
        log("(This will take a while - progress is saved, you can interrupt and resume)")
        log("")
    
    # Analyse each response
    for i, item in enumerate(remaining, 1):
        display_name = get_display_name(item)
        text_len = len(item.get('text', ''))
        log(f"[{i}/{len(remaining)}] Analysing: {display_name[:50]}... ({text_len} chars)")
        
        analysis = analyse_response(item, use_short_prompt=False)
        
        if analysis:
            results.append(analysis)
            analysed_ids.add(item['id'])
            short_flag = " (short)" if analysis.get('used_short_prompt') else ""
            log(f"  ✓ Done{short_flag}: stance={analysis.get('privacy_stance', 'unknown')}")
            
            # Save progress periodically
            if i % 5 == 0:
                save_progress(analysed_ids)
                save_results(results)
                log(f"  Progress saved ({len(results)} total)")
        else:
            log(f"  ✗ Failed to analyse")
        
        # Rate limiting
        time.sleep(DELAY_BETWEEN_CALLS)
    
    # Final save
    save_progress(analysed_ids)
    save_results(results)
    
    # Generate report
    log("\nGenerating report...")
    report = generate_report(results)
    report_file = OUTPUT_DIR / "analysis_report.md"
    report_file.write_text(report)
    log(f"  Saved to {report_file}")
    
    # Summary stats
    log("\n" + "=" * 70)
    log("ANALYSIS COMPLETE")
    log("=" * 70)
    log(f"\nTotal analysed: {len(results)}")
    
    pro_protection = len([r for r in results if r.get('privacy_stance') == 'pro_protection'])
    pro_simplification = len([r for r in results if r.get('privacy_stance') == 'pro_simplification'])
    pet_mentions = len([r for r in results if r.get('mentions_pets')])
    
    log(f"  Pro-protection: {pro_protection}")
    log(f"  Pro-simplification: {pro_simplification}")
    log(f"  Mentions PETs: {pet_mentions}")
    
    log(f"\nOutput files in: {OUTPUT_DIR}")
    log("  - analysis_results.json (raw data)")
    log("  - analysis_report.md (formatted report)")

if __name__ == "__main__":
    main()

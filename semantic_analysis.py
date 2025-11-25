#!/usr/bin/env python3
"""
Semantic Analysis Pipeline for Digital Omnibus Consultation Responses

This script:
1. Extracts text from all PDFs and DOCXs
2. Combines with feedback_text from CSV (for responses without attachments)
3. Creates embeddings for similarity analysis
4. Clusters responses to find themes
5. Calculates alignment with OpenMined's response
6. Generates a comprehensive analysis report
"""

import os
import sys
import json
import csv
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Check and install required packages
def check_dependencies():
    """Check and install required packages."""
    required = {
        'pdfplumber': 'pdfplumber',
        'docx': 'python-docx',
        'sentence_transformers': 'sentence-transformers',
        'sklearn': 'scikit-learn',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'umap': 'umap-learn',
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["-q"])
        print("✓ Packages installed")

print("Checking dependencies...")
check_dependencies()

import numpy as np
import pandas as pd
import pdfplumber
from docx import Document
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

# Configuration
DATA_DIR = Path("20401_digital_omnibus")
ATTACHMENTS_DIR = DATA_DIR / "attachments"
FEEDBACKS_CSV = DATA_DIR / "feedbacks.csv"
EXTRACTED_TEXTS_FILE = DATA_DIR / "extracted_texts.json"
OUTPUT_DIR = DATA_DIR / "analysis"
OPENMINED_FILE = "27566996_Omnibus Comments (5).pdf"

# Create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def load_preextracted_texts():
    """Load texts from pre-extracted JSON file if available."""
    if EXTRACTED_TEXTS_FILE.exists():
        log(f"Found pre-extracted texts at {EXTRACTED_TEXTS_FILE}")
        log("  Loading pre-extracted data (faster)...")
        
        with open(EXTRACTED_TEXTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        texts = {}
        metadata = {}
        
        for item in data:
            fid = str(item['id'])
            if item['text']:
                texts[fid] = item['text']
                metadata[fid] = {
                    'id': fid,
                    'organization': item.get('organization', ''),
                    'country': item.get('country', ''),
                    'userType': item.get('userType', ''),
                    'firstName': item.get('firstName', ''),
                    'surname': item.get('surname', ''),
                    'language': item.get('language', ''),
                    'date': item.get('date', ''),
                    'text_length': item.get('text_length', len(item['text'])),
                    'has_attachment': item.get('has_attachment', False)
                }
        
        log(f"  ✓ Loaded {len(texts)} texts from pre-extracted file")
        return texts, metadata
    
    return None, None

def extract_text_from_pdf(filepath):
    """Extract text from a PDF file."""
    try:
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        log(f"  Warning: Could not extract text from {filepath.name}: {e}")
        return ""

def extract_text_from_docx(filepath):
    """Extract text from a DOCX file."""
    try:
        doc = Document(filepath)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    except Exception as e:
        log(f"  Warning: Could not extract text from {filepath.name}: {e}")
        return ""

def extract_text_from_file(filepath):
    """Extract text from a file based on its extension."""
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    
    if ext == '.pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ['.docx', '.doc']:
        return extract_text_from_docx(filepath)
    else:
        # Try reading as plain text
        try:
            return filepath.read_text(encoding='utf-8', errors='ignore')
        except:
            return ""

def load_feedbacks():
    """Load feedbacks from CSV."""
    log("Loading feedbacks from CSV...")
    
    feedbacks = []
    with open(FEEDBACKS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            feedbacks.append(row)
    
    log(f"  Loaded {len(feedbacks)} feedback entries")
    return feedbacks

def build_attachment_index():
    """Build an index mapping feedback IDs to their attachment files."""
    log("Building attachment index...")
    
    # Load attachments.csv if it exists
    attachments_csv = DATA_DIR / "attachments.csv"
    attachment_map = defaultdict(list)
    
    if attachments_csv.exists():
        with open(attachments_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                feedback_id = row.get('feedback_id', '')
                filename = row.get('filename', '')
                status = row.get('status', '')
                
                if feedback_id and filename and status in ['downloaded', 'exists']:
                    attachment_map[str(feedback_id)].append(filename)
    
    # Also scan the attachments directory directly
    if ATTACHMENTS_DIR.exists():
        for filepath in ATTACHMENTS_DIR.iterdir():
            if filepath.is_file():
                # Extract feedback ID from filename (format: ID_name.ext)
                match = re.match(r'^(\d+)_', filepath.name)
                if match:
                    feedback_id = match.group(1)
                    if filepath.name not in attachment_map[feedback_id]:
                        attachment_map[feedback_id].append(filepath.name)
    
    log(f"  Found attachments for {len(attachment_map)} feedbacks")
    return attachment_map

def extract_all_texts(feedbacks, attachment_map):
    """Extract text from all responses (attachments + feedback_text)."""
    log("Extracting text from all responses...")
    
    texts = {}
    metadata = {}
    
    total = len(feedbacks)
    extracted = 0
    from_attachment = 0
    from_text_only = 0
    
    for i, fb in enumerate(feedbacks, 1):
        feedback_id = str(fb.get('id', ''))
        
        if i % 50 == 0:
            log(f"  Processing {i}/{total}...")
        
        # Start with feedback_text from CSV
        text_parts = []
        feedback_text = fb.get('feedback_text', '').strip()
        if feedback_text:
            text_parts.append(feedback_text)
        
        # Get text from attachments
        attachment_files = attachment_map.get(feedback_id, [])
        for filename in attachment_files:
            filepath = ATTACHMENTS_DIR / filename
            if filepath.exists():
                attachment_text = extract_text_from_file(filepath)
                if attachment_text:
                    text_parts.append(attachment_text)
                    from_attachment += 1
        
        # Combine all text
        combined_text = "\n\n".join(text_parts).strip()
        
        if combined_text:
            texts[feedback_id] = combined_text
            metadata[feedback_id] = {
                'id': feedback_id,
                'organization': fb.get('organization', ''),
                'country': fb.get('country', ''),
                'userType': fb.get('userType', ''),
                'firstName': fb.get('firstName', ''),
                'surname': fb.get('surname', ''),
                'language': fb.get('language', ''),
                'date': fb.get('date', ''),
                'text_length': len(combined_text),
                'has_attachment': len(attachment_files) > 0
            }
            extracted += 1
            
            if not attachment_files and feedback_text:
                from_text_only += 1
    
    log(f"  ✓ Extracted text from {extracted} responses")
    log(f"    - From attachments: {from_attachment}")
    log(f"    - Text-only (no attachment): {from_text_only}")
    
    return texts, metadata

def create_embeddings(texts, metadata):
    """Create embeddings for all texts using sentence-transformers."""
    log("Creating embeddings...")
    
    # Use a multilingual model since responses may be in different languages
    log("  Loading multilingual model (this may take a minute)...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # Prepare texts for embedding
    ids = list(texts.keys())
    text_list = [texts[id] for id in ids]
    
    # Truncate very long texts (model has max token limit)
    max_chars = 10000  # Roughly 2500 tokens
    truncated_texts = [t[:max_chars] if len(t) > max_chars else t for t in text_list]
    
    log(f"  Encoding {len(truncated_texts)} texts...")
    embeddings = model.encode(truncated_texts, show_progress_bar=True, batch_size=16)
    
    log(f"  ✓ Created {len(embeddings)} embeddings of dimension {embeddings.shape[1]}")
    
    return ids, embeddings, model

def find_openmined_response(texts, metadata):
    """Find OpenMined's response in the dataset."""
    log("Finding OpenMined's response...")
    
    # Look for OpenMined in organization names
    for feedback_id, meta in metadata.items():
        org = meta.get('organization', '').lower()
        if 'openmined' in org:
            log(f"  ✓ Found OpenMined response: ID {feedback_id}")
            return feedback_id
    
    # Also check if the specific file was processed
    for feedback_id in texts.keys():
        if feedback_id in OPENMINED_FILE:
            log(f"  ✓ Found OpenMined response via filename: ID {feedback_id}")
            return feedback_id
    
    # Try to find by attachment filename
    log(f"  Looking for file: {OPENMINED_FILE}")
    openmined_id = OPENMINED_FILE.split('_')[0]
    if openmined_id in texts:
        log(f"  ✓ Found OpenMined response: ID {openmined_id}")
        return openmined_id
    
    log("  ⚠ Could not find OpenMined response automatically")
    return None

def calculate_similarities(ids, embeddings, reference_id):
    """Calculate similarity of all responses to the reference (OpenMined)."""
    log("Calculating similarities to OpenMined's response...")
    
    if reference_id not in ids:
        log(f"  ⚠ Reference ID {reference_id} not in embeddings")
        return {}
    
    ref_idx = ids.index(reference_id)
    ref_embedding = embeddings[ref_idx].reshape(1, -1)
    
    similarities = cosine_similarity(ref_embedding, embeddings)[0]
    
    similarity_scores = {}
    for i, id in enumerate(ids):
        similarity_scores[id] = float(similarities[i])
    
    log(f"  ✓ Calculated {len(similarity_scores)} similarity scores")
    return similarity_scores

def cluster_responses(ids, embeddings, n_clusters=10):
    """Cluster responses to find themes."""
    log(f"Clustering responses into {n_clusters} groups...")
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings)
    
    clusters = defaultdict(list)
    for i, id in enumerate(ids):
        clusters[int(cluster_labels[i])].append(id)
    
    log(f"  ✓ Created {len(clusters)} clusters")
    for cluster_id, members in sorted(clusters.items()):
        log(f"    Cluster {cluster_id}: {len(members)} responses")
    
    return dict(clusters), cluster_labels

def extract_cluster_themes(texts, clusters, metadata, n_keywords=10):
    """Extract key themes/keywords for each cluster using TF-IDF."""
    log("Extracting cluster themes...")
    
    cluster_themes = {}
    
    for cluster_id, member_ids in clusters.items():
        # Combine texts from this cluster
        cluster_texts = [texts[id] for id in member_ids if id in texts]
        combined_text = " ".join(cluster_texts)
        
        # Get sample organizations in this cluster
        sample_orgs = []
        for id in member_ids[:5]:
            if id in metadata:
                org = metadata[id].get('organization', '')
                if org:
                    sample_orgs.append(org)
        
        cluster_themes[cluster_id] = {
            'size': len(member_ids),
            'sample_organizations': sample_orgs,
            'member_ids': member_ids
        }
    
    # Use TF-IDF to find distinctive terms for each cluster
    all_cluster_texts = []
    cluster_order = sorted(clusters.keys())
    
    for cluster_id in cluster_order:
        member_ids = clusters[cluster_id]
        cluster_text = " ".join([texts[id] for id in member_ids if id in texts])
        all_cluster_texts.append(cluster_text)
    
    if all_cluster_texts:
        vectorizer = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(all_cluster_texts)
        feature_names = vectorizer.get_feature_names_out()
        
        for i, cluster_id in enumerate(cluster_order):
            # Get top terms for this cluster
            scores = tfidf_matrix[i].toarray()[0]
            top_indices = scores.argsort()[-n_keywords:][::-1]
            top_terms = [feature_names[idx] for idx in top_indices if scores[idx] > 0]
            cluster_themes[cluster_id]['keywords'] = top_terms
    
    log(f"  ✓ Extracted themes for {len(cluster_themes)} clusters")
    return cluster_themes

def find_disagreements(texts, metadata, embeddings, ids):
    """Find pairs of responses that are most different from each other."""
    log("Analyzing disagreements...")
    
    # Calculate pairwise similarities
    similarity_matrix = cosine_similarity(embeddings)
    
    # Find most dissimilar pairs
    disagreements = []
    n = len(ids)
    
    for i in range(n):
        for j in range(i + 1, n):
            sim = similarity_matrix[i][j]
            if sim < 0.3:  # Threshold for "disagreement"
                id1, id2 = ids[i], ids[j]
                org1 = metadata.get(id1, {}).get('organization', 'Unknown')
                org2 = metadata.get(id2, {}).get('organization', 'Unknown')
                
                if org1 and org2:  # Only include if both have organizations
                    disagreements.append({
                        'id1': id1,
                        'id2': id2,
                        'org1': org1,
                        'org2': org2,
                        'similarity': float(sim)
                    })
    
    # Sort by lowest similarity
    disagreements.sort(key=lambda x: x['similarity'])
    
    log(f"  ✓ Found {len(disagreements)} potential disagreement pairs")
    return disagreements[:50]  # Top 50 most different

def analyze_by_stakeholder_type(metadata, similarity_scores):
    """Analyze patterns by stakeholder type."""
    log("Analyzing by stakeholder type...")
    
    by_type = defaultdict(list)
    
    for id, meta in metadata.items():
        user_type = meta.get('userType', 'Unknown')
        sim = similarity_scores.get(id, 0)
        by_type[user_type].append({
            'id': id,
            'organization': meta.get('organization', ''),
            'similarity': sim
        })
    
    type_stats = {}
    for user_type, items in by_type.items():
        sims = [item['similarity'] for item in items]
        type_stats[user_type] = {
            'count': len(items),
            'avg_similarity_to_openmined': float(np.mean(sims)) if sims else 0,
            'std_similarity': float(np.std(sims)) if sims else 0,
            'most_aligned': sorted(items, key=lambda x: x['similarity'], reverse=True)[:3],
            'least_aligned': sorted(items, key=lambda x: x['similarity'])[:3]
        }
    
    log(f"  ✓ Analyzed {len(type_stats)} stakeholder types")
    return type_stats

def generate_report(texts, metadata, similarity_scores, clusters, cluster_themes, 
                   disagreements, type_stats, openmined_id):
    """Generate a comprehensive analysis report."""
    log("Generating analysis report...")
    
    report_lines = []
    
    def add(line=""):
        report_lines.append(line)
    
    add("=" * 80)
    add("DIGITAL OMNIBUS CONSULTATION - SEMANTIC ANALYSIS REPORT")
    add("=" * 80)
    add(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"Total responses analyzed: {len(texts)}")
    add()
    
    # Summary statistics
    add("## SUMMARY STATISTICS")
    add("-" * 40)
    
    # By country
    countries = defaultdict(int)
    for meta in metadata.values():
        countries[meta.get('country', 'Unknown')] += 1
    
    add(f"Responses by country (top 10):")
    for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]:
        add(f"  {country}: {count}")
    add()
    
    # By stakeholder type
    add(f"Responses by stakeholder type:")
    for user_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True):
        add(f"  {user_type}: {stats['count']}")
    add()
    
    # OpenMined alignment
    add("=" * 80)
    add("## ALIGNMENT WITH OPENMINED")
    add("-" * 40)
    
    if openmined_id and similarity_scores:
        # Most aligned
        sorted_by_sim = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        
        add("Most aligned with OpenMined (excluding self):")
        rank = 1
        for id, sim in sorted_by_sim:
            if id == openmined_id:
                continue
            if rank > 15:
                break
            meta = metadata.get(id, {})
            org = meta.get('organization', '')
            # Fall back to individual name if no organization
            if not org:
                first = meta.get('firstName', '')
                last = meta.get('surname', '')
                org = f"{first} {last}".strip() or "Anonymous"
            country = meta.get('country', '')
            user_type = meta.get('userType', '')
            add(f"  {rank}. {org} ({country}, {user_type})")
            add(f"     Similarity: {sim:.3f}")
            rank += 1
        add()
        
        # Least aligned
        add("Least aligned with OpenMined:")
        rank = 1
        for id, sim in reversed(sorted_by_sim):
            if id == openmined_id:
                continue
            if rank > 15:
                break
            meta = metadata.get(id, {})
            org = meta.get('organization', '')
            # Fall back to individual name if no organization
            if not org:
                first = meta.get('firstName', '')
                last = meta.get('surname', '')
                org = f"{first} {last}".strip() or "Anonymous"
            country = meta.get('country', '')
            user_type = meta.get('userType', '')
            add(f"  {rank}. {org} ({country}, {user_type})")
            add(f"     Similarity: {sim:.3f}")
            rank += 1
        add()
        
        # Alignment by stakeholder type
        add("Average alignment with OpenMined by stakeholder type:")
        for user_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['avg_similarity_to_openmined'], reverse=True):
            add(f"  {user_type}: {stats['avg_similarity_to_openmined']:.3f} (n={stats['count']})")
        add()
    
    # Clusters / Themes
    add("=" * 80)
    add("## RESPONSE CLUSTERS (THEMES)")
    add("-" * 40)
    
    for cluster_id, theme in sorted(cluster_themes.items(), key=lambda x: x[1]['size'], reverse=True):
        add(f"\nCluster {cluster_id} ({theme['size']} responses):")
        
        if theme.get('keywords'):
            add(f"  Keywords: {', '.join(theme['keywords'][:8])}")
        
        if theme.get('sample_organizations'):
            add(f"  Sample organizations:")
            for org in theme['sample_organizations'][:5]:
                add(f"    - {org}")
    add()
    
    # Disagreements
    add("=" * 80)
    add("## POTENTIAL DISAGREEMENTS")
    add("-" * 40)
    add("Pairs of responses with lowest semantic similarity:")
    add()
    
    for i, d in enumerate(disagreements[:20], 1):
        add(f"{i}. {d['org1']} vs {d['org2']}")
        add(f"   Similarity: {d['similarity']:.3f}")
    add()
    
    # Save report
    report_text = "\n".join(report_lines)
    
    report_path = OUTPUT_DIR / "analysis_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    log(f"  ✓ Report saved to {report_path}")
    
    return report_text

def save_analysis_data(ids, metadata, similarity_scores, cluster_labels, clusters, 
                       cluster_themes, disagreements, type_stats):
    """Save analysis data to files for further exploration."""
    log("Saving analysis data...")
    
    # Save similarity scores with metadata
    similarity_data = []
    for id in ids:
        meta = metadata.get(id, {})
        org = meta.get('organization', '')
        # Create display name that falls back to individual name
        if org:
            display_name = org
        else:
            first = meta.get('firstName', '')
            last = meta.get('surname', '')
            display_name = f"{first} {last}".strip() or "Anonymous"
        
        similarity_data.append({
            'feedback_id': id,
            'display_name': display_name,
            'organization': meta.get('organization', ''),
            'firstName': meta.get('firstName', ''),
            'surname': meta.get('surname', ''),
            'country': meta.get('country', ''),
            'userType': meta.get('userType', ''),
            'similarity_to_openmined': similarity_scores.get(id, 0),
            'cluster': int(cluster_labels[ids.index(id)]) if id in ids else -1,
            'text_length': meta.get('text_length', 0),
            'url': f"https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/F{id}_en"
        })
    
    # Sort by similarity
    similarity_data.sort(key=lambda x: x['similarity_to_openmined'], reverse=True)
    
    # Save to CSV
    df = pd.DataFrame(similarity_data)
    csv_path = OUTPUT_DIR / "similarity_analysis.csv"
    df.to_csv(csv_path, index=False)
    log(f"  ✓ Saved {csv_path}")
    
    # Save cluster themes as JSON
    themes_path = OUTPUT_DIR / "cluster_themes.json"
    with open(themes_path, 'w', encoding='utf-8') as f:
        json.dump(cluster_themes, f, indent=2, ensure_ascii=False)
    log(f"  ✓ Saved {themes_path}")
    
    # Save disagreements
    disagreements_path = OUTPUT_DIR / "disagreements.json"
    with open(disagreements_path, 'w', encoding='utf-8') as f:
        json.dump(disagreements, f, indent=2, ensure_ascii=False)
    log(f"  ✓ Saved {disagreements_path}")
    
    # Save type stats
    type_stats_path = OUTPUT_DIR / "stakeholder_type_analysis.json"
    # Convert to serializable format
    serializable_stats = {}
    for k, v in type_stats.items():
        serializable_stats[k] = {
            'count': v['count'],
            'avg_similarity_to_openmined': v['avg_similarity_to_openmined'],
            'std_similarity': v['std_similarity'],
            'most_aligned': v['most_aligned'],
            'least_aligned': v['least_aligned']
        }
    with open(type_stats_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_stats, f, indent=2, ensure_ascii=False)
    log(f"  ✓ Saved {type_stats_path}")

def main():
    """Main execution function."""
    print("=" * 70)
    print("DIGITAL OMNIBUS SEMANTIC ANALYSIS PIPELINE")
    print("=" * 70)
    print()
    
    # Check if data directory exists
    if not DATA_DIR.exists():
        log(f"❌ Data directory not found: {DATA_DIR}")
        log("Please run the download script first.")
        return
    
    # Try to load pre-extracted texts first (faster)
    texts, metadata = load_preextracted_texts()
    
    if texts is None:
        # Fall back to extracting from scratch
        log("No pre-extracted texts found, extracting from source files...")
        log("(Tip: Run extract_texts.py first for faster subsequent runs)")
        
        # Step 1: Load feedbacks
        feedbacks = load_feedbacks()
        
        # Step 2: Build attachment index
        attachment_map = build_attachment_index()
        
        # Step 3: Extract all texts
        texts, metadata = extract_all_texts(feedbacks, attachment_map)
    
    if len(texts) < 10:
        log("❌ Not enough texts extracted. Check your data.")
        return
    
    # Step 4: Create embeddings
    ids, embeddings, model = create_embeddings(texts, metadata)
    
    # Step 5: Find OpenMined's response
    openmined_id = find_openmined_response(texts, metadata)
    
    # Step 6: Calculate similarities to OpenMined
    similarity_scores = {}
    if openmined_id:
        similarity_scores = calculate_similarities(ids, embeddings, openmined_id)
    
    # Step 7: Cluster responses
    n_clusters = min(15, len(texts) // 20)  # Adaptive cluster count
    n_clusters = max(5, n_clusters)
    clusters, cluster_labels = cluster_responses(ids, embeddings, n_clusters)
    
    # Step 8: Extract cluster themes
    cluster_themes = extract_cluster_themes(texts, clusters, metadata)
    
    # Step 9: Find disagreements
    disagreements = find_disagreements(texts, metadata, embeddings, ids)
    
    # Step 10: Analyze by stakeholder type
    type_stats = analyze_by_stakeholder_type(metadata, similarity_scores)
    
    # Step 11: Generate report
    report = generate_report(
        texts, metadata, similarity_scores, clusters, cluster_themes,
        disagreements, type_stats, openmined_id
    )
    
    # Step 12: Save all data
    save_analysis_data(
        ids, metadata, similarity_scores, cluster_labels, clusters,
        cluster_themes, disagreements, type_stats
    )
    
    # Print summary
    print()
    print("=" * 70)
    print("ANALYSIS COMPLETE!")
    print("=" * 70)
    print()
    print("Output files created in:", OUTPUT_DIR.absolute())
    print()
    print("  📊 analysis_report.txt      - Human-readable analysis report")
    print("  📊 similarity_analysis.csv  - All responses ranked by similarity to OpenMined")
    print("  📊 cluster_themes.json      - Cluster keywords and members")
    print("  📊 disagreements.json       - Most dissimilar response pairs")
    print("  📊 stakeholder_type_analysis.json - Analysis by stakeholder type")
    print()
    print("=" * 70)
    print()
    
    # Print key findings preview
    print("KEY FINDINGS PREVIEW:")
    print("-" * 40)
    
    if similarity_scores and openmined_id:
        sorted_sims = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        print("\nTop 5 most aligned with OpenMined:")
        rank = 1
        for id, sim in sorted_sims:
            if id == openmined_id:
                continue
            if rank > 5:
                break
            meta = metadata.get(id, {})
            org = meta.get('organization', '')
            if not org:
                first = meta.get('firstName', '')
                last = meta.get('surname', '')
                org = f"{first} {last}".strip() or "Anonymous"
            print(f"  {rank}. {org} (similarity: {sim:.3f})")
            rank += 1
        
        print("\nTop 5 least aligned with OpenMined:")
        rank = 1
        for id, sim in reversed(sorted_sims):
            if id == openmined_id:
                continue
            if rank > 5:
                break
            meta = metadata.get(id, {})
            org = meta.get('organization', '')
            if not org:
                first = meta.get('firstName', '')
                last = meta.get('surname', '')
                org = f"{first} {last}".strip() or "Anonymous"
            print(f"  {rank}. {org} (similarity: {sim:.3f})")
            rank += 1

if __name__ == "__main__":
    main()

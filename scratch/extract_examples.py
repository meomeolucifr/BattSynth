import json
import os
import glob
import random

# Fixed random seed for reproducible sampling
random.seed(42)

def main():
    search_path = os.path.join('dataset', 'human_reviews', '**', 'Human_Review_*.json')
    files = glob.glob(search_path, recursive=True)
    
    buckets = {
        'correct': [],
        'hallucination': [],
        'wrong_amount': [],
        'semantic_mismatch': [],
        'other': [],
        'partially_correct': [],
        'missing_data': []
    }
    
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
                
            title = data.get('title', '')
            paper_id = data.get('paper_id', '')
            
            for review in data.get('entity_reviews', []):
                verdict = review.get('human_verdict')
                error_cat = review.get('error_category')
                
                # Derive entity type from entity_path or entity_id
                entity_path = review.get('entity_path', '')
                entity_type = entity_path.split('[')[0] if entity_path else review.get('entity_id', '')
                
                # Try to find a context snippet
                context = review.get('human_notes', '')
                if not context:
                    context = review.get('llm_reasoning', '')
                    
                entry = {
                    'paper_title': title,
                    'paper_id': paper_id,
                    'entity_type': entity_type,
                    'extracted_value': review.get('extracted_value', ''),
                    'source_context_snippet': context[:200] + '...' if len(context) > 200 else context,
                    'assigned_label': verdict,
                    'error_category': error_cat if verdict == 'incorrect' else None
                }
                
                if verdict == 'correct':
                    buckets['correct'].append(entry)
                elif verdict == 'partially_correct':
                    buckets['partially_correct'].append(entry)
                elif verdict == 'missing_data':
                    buckets['missing_data'].append(entry)
                elif verdict == 'incorrect':
                    if error_cat == 'hallucination':
                        buckets['hallucination'].append(entry)
                    elif error_cat == 'wrong_amount':
                        buckets['wrong_amount'].append(entry)
                    elif error_cat == 'semantic_mismatch':
                        buckets['semantic_mismatch'].append(entry)
                    elif error_cat == 'other':
                        buckets['other'].append(entry)

    # Now select the required number of examples
    selected = {
        'correct': random.sample(buckets['correct'], min(2, len(buckets['correct']))),
        'hallucination': random.sample(buckets['hallucination'], min(3, len(buckets['hallucination']))),
        'wrong_amount': buckets['wrong_amount'], # Take all available (should be 1)
        'semantic_mismatch': buckets['semantic_mismatch'], # Take all available (should be 1)
        'other': random.sample(buckets['other'], min(3, len(buckets['other']))),
        'partially_correct': [],
        'missing_data': random.sample(buckets['missing_data'], min(3, len(buckets['missing_data'])))
    }
    
    # For partially correct, try to find one with rounding/truncation
    pc_rounded = [e for e in buckets['partially_correct'] if 'round' in e['source_context_snippet'].lower() or 'trunc' in e['source_context_snippet'].lower()]
    pc_others = [e for e in buckets['partially_correct'] if e not in pc_rounded]
    
    if pc_rounded:
        selected['partially_correct'].append(pc_rounded[0])
        selected['partially_correct'].extend(random.sample(pc_others, min(2, len(pc_others))))
    else:
        selected['partially_correct'] = random.sample(buckets['partially_correct'], min(3, len(buckets['partially_correct'])))
        
    # Output counts for validation
    print(f"Bucket 'wrong_amount' count: {len(buckets['wrong_amount'])}")
    print(f"Bucket 'semantic_mismatch' count: {len(buckets['semantic_mismatch'])}")
    
    output_path = os.path.join('dataset', 'analysis', 'codebook_worked_examples.json')
    with open(output_path, 'w', encoding='utf-8') as out_f:
        json.dump(selected, out_f, indent=2, ensure_ascii=False)
        
    print(f"Saved extracted examples to {output_path}")

if __name__ == '__main__':
    main()

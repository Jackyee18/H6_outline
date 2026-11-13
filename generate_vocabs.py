import json
import os
import pandas as pd

CSV_PATH = 'my_chinese/chinese_dict.csv'

def has_any_tag(tags_str, target_tags):
    if not isinstance(tags_str, str):
        return False
    parts = [p.strip().lower() for p in tags_str.split(',')]
    return any(t.lower() in parts for t in target_tags)

print(f"Loading {CSV_PATH}...")
df = pd.read_csv(CSV_PATH)
print(f"Total rows in dictionary: {len(df)}")

# 1. vocab_h5.json: tags contain h1, h2, h3, h4, or h5
h1_5_tags = ['h1', 'h2', 'h3', 'h4', 'h5']
mask_h5 = df['tags'].apply(lambda t: has_any_tag(t, h1_5_tags))
df_h5 = df[mask_h5]
records_h5 = df_h5.to_dict(orient='records')
print(f"vocab_h5: {len(records_h5)} words selected")

output_h5 = 'vocab_h5.json'
with open(output_h5, 'w', encoding='utf-8') as f:
    json.dump(records_h5, f, ensure_ascii=False, indent=2)
print(f"Written {output_h5} ({os.path.getsize(output_h5):,} bytes)")

# 2. vocab_h6.json: tags contain h6 only (HSK 6 level)
h6_tag = ['h6']
mask_h6 = df['tags'].apply(lambda t: has_any_tag(t, h6_tag))
df_h6 = df[mask_h6]
records_h6 = df_h6.to_dict(orient='records')
print(f"vocab_h6: {len(records_h6)} words selected")

output_h6 = 'vocab_h6.json'
with open(output_h6, 'w', encoding='utf-8') as f:
    json.dump(records_h6, f, ensure_ascii=False, indent=2)
print(f"Written {output_h6} ({os.path.getsize(output_h6):,} bytes)")

print("Generation complete!")


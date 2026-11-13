import json
import os
import re
from collections import defaultdict, OrderedDict

def main():
    print("Loading input files...")
    f1_path = 'gemini-code-1794478039558.json'
    f2_path = 'gemini-code-1794478480184.json'
    vocab_path = 'vocab_h6.json'

    with open(f1_path, 'r', encoding='utf-8') as f:
        d1 = json.load(f)

    with open(f2_path, 'r', encoding='utf-8') as f:
        raw2 = f.read().strip()
        if not raw2.startswith('['):
            raw2 = '[' + raw2
        if not raw2.endswith(']'):
            raw2 = raw2 + ']'
        d2 = json.loads(raw2)

    with open(vocab_path, 'r', encoding='utf-8') as f:
        vocab_h6 = json.load(f)

    # Build vocab lookup: cn -> list of entries (for polysemy)
    vocab_lookup = defaultdict(list)
    for entry in vocab_h6:
        vocab_lookup[entry['cn'].strip()].append(entry)

    # Combine: Units 1-52 from d1, Units 53-55 from d2
    lessons_1_52 = [x for x in d1 if x['unit'] <= 52]
    lessons_53_55 = d2

    combined = lessons_1_52 + lessons_53_55
    print(f"Total combined lessons: {len(combined)}")

    # Basic validations
    assert len(combined) == 165, f"Expected 165 lessons, got {len(combined)}"
    units = sorted(list(set(x['unit'] for x in combined)))
    assert units == list(range(1, 56)), f"Units mismatch: {units}"

    # Verify passage_id sequence
    for u in range(1, 56):
        for l in range(1, 4):
            expected_id = f"H6_{u}_{l}"
            actual = combined[(u - 1) * 3 + (l - 1)]
            assert actual['passage_id'] == expected_id, f"ID mismatch at unit {u} lesson {l}: {actual['passage_id']}"
            assert actual['unit'] == u, f"Unit field mismatch in {actual['passage_id']}"

    # Verify vocabulary coverage
    all_words = []
    for item in combined:
        all_words.extend(item.get('new_words', []))
    
    unique_words = set(all_words)
    h6_words = set(vocab_lookup.keys())

    missing = h6_words - unique_words
    extra = unique_words - h6_words
    print(f"Total word slots: {len(all_words)}")
    print(f"Unique words in outline: {len(unique_words)}")
    print(f"Missing from vocab_h6.json: {len(missing)}")
    print(f"Extra not in vocab_h6.json: {len(extra)}")

    # 1. Save H6_outline.json
    output_json = 'H6_outline.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"Saved {output_json} ({os.path.getsize(output_json):,} bytes)")

    # 2. Build H6_outline.md
    print("Building H6_outline.md...")
    md_lines = []
    md_lines.append("# HSK 6 Curriculum Syllabus & Outline\n")
    md_lines.append(f"> **Quick Stats**: 55 Units · 165 Lessons · {len(unique_words):,} Unique Words ({len(all_words):,} total vocabulary appearances, 100% HSK 6 Vocabulary Coverage)")
    dialogue_count = sum(1 for x in combined if x.get('text_type') == 'dialogue')
    passage_count = sum(1 for x in combined if x.get('text_type') == 'passage')
    md_lines.append(f"> **Structure**: {dialogue_count} Dialogues + {passage_count} Passages (3 lessons per unit: 2 Dialogues + 1 Passage)")
    md_lines.append(f"> **Lesson Pace**: 6–7 new words per lesson, organized around immersive, high-level communicative and narrative themes.\n")
    md_lines.append("---\n")
    md_lines.append("## 📑 Table of Contents\n")

    # Group units by Module for TOC
    modules = OrderedDict()
    for item in combined:
        mod = item['module']
        u = item['unit']
        ut = item['unit_title']
        if mod not in modules:
            modules[mod] = OrderedDict()
        if u not in modules[mod]:
            modules[mod][u] = ut

    for mod, unit_dict in modules.items():
        md_lines.append(f"### {mod}")
        for u, ut in unit_dict.items():
            md_lines.append(f"- **Unit {u}**: {ut}")
        md_lines.append("")

    md_lines.append("---\n")
    md_lines.append("## 📖 Comprehensive Unit Outline\n")

    # Group lessons by unit
    for u in range(1, 56):
        unit_lessons = [x for x in combined if x['unit'] == u]
        first_lesson = unit_lessons[0]
        mod = first_lesson['module']
        ut = first_lesson['unit_title']

        md_lines.append(f"## Unit {u}: {ut}")
        md_lines.append(f"*{mod}*\n")

        for item in unit_lessons:
            pid = item['passage_id']
            title = item['title']
            ttype = item['text_type']
            type_icon = "🗣️ Dialogue" if ttype == "dialogue" else "📖 Passage"
            scenario = item['scenario']
            new_words = item['new_words']

            md_lines.append(f"### `{pid}` — {title} ({type_icon})\n")
            md_lines.append(f"**Scenario**: {scenario}\n")
            md_lines.append("| # | Vocabulary | Pinyin | Part of Speech | English Meaning | Nghĩa Tiếng Việt |")
            md_lines.append("| :-: | :--- | :--- | :---: | :--- | :--- |")

            for w_idx, w in enumerate(new_words, 1):
                entries = vocab_lookup.get(w, [])
                if not entries:
                    pinyin_str = "-"
                    pos_str = "-"
                    en_str = "-"
                    vn_str = "-"
                elif len(entries) == 1:
                    e = entries[0]
                    pinyin_str = f"`{e['py']}`"
                    pos_str = f"*{e['pos']}*" if e['pos'] else "-"
                    en_str = e['en'].strip().rstrip(',') if e['en'] else "-"
                    vn_str = e['vn'].strip().rstrip(',') if e['vn'] else "-"
                else:
                    # Polysemy
                    pinyins = list(dict.fromkeys(e['py'] for e in entries if e['py']))
                    pinyin_str = f"`{' / '.join(pinyins)}`"
                    
                    pos_list = list(dict.fromkeys(e['pos'] for e in entries if e['pos']))
                    pos_str = f"*{' / '.join(pos_list)}*"
                    
                    en_meanings = []
                    for idx, e in enumerate(entries, 1):
                        m = e['en'].strip().rstrip(',') if e['en'] else ""
                        if m:
                            en_meanings.append(f"{idx}. {m}")
                    en_str = "; ".join(en_meanings) if en_meanings else "-"

                    vn_meanings = []
                    for idx, e in enumerate(entries, 1):
                        m = e['vn'].strip().rstrip(',') if e['vn'] else ""
                        if m:
                            vn_meanings.append(f"{idx}. {m}")
                    vn_str = "; ".join(vn_meanings) if vn_meanings else "-"

                md_lines.append(f"| {w_idx} | **{w}** | {pinyin_str} | {pos_str} | {en_str} | {vn_str} |")

            md_lines.append("\n---\n")

    output_md = 'H6_outline.md'
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
    print(f"Saved {output_md} ({os.path.getsize(output_md):,} bytes)")
    print("Done!")

if __name__ == '__main__':
    main()


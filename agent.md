# HSK 6 Interactive Textbook & Curriculum Builder (`agent.md`)

## 1. Project Mission & Full-Lifecycle Overview

This project is an end-to-end curriculum engineering and interactive textbook data pipeline for **HSK 6**. Building directly upon the proven architecture, tooling, and pedagogical standards established in **HSK 4** (`H4.json`) and **HSK 5** (`H5.json`), this system transforms the complete **HSK 6 vocabulary database (1,237 dictionary entries $\to$ 1,117 unique words)** into a complete, pedagogically sound, and audio-synchronized interactive textbook dataset (`H6.json`) and human-readable curriculum reader (`H6_content.md`).

### Source Data & Repositories
- **Raw Dictionary Source**: [Jackyee18/my_chinese](https://github.com/Jackyee18/my_chinese) (`chinese_dict.csv` — 51,165 entries)
- **Predecessor Golden Standards**:
  - HSK 4: 36 units, 144 lessons, 1,003 word slots (`H4.json`)
  - HSK 5: 39 units, 156 lessons, 1,060 word slots (`H5.json` on [Jackyee18/HSK5_outline](https://github.com/Jackyee18/HSK5_outline))
- **Tracked Deliverables**:
  - `vocab_h5.json`: Base cumulative vocabulary whitelist (4,553 words covering HSK 1–5).
  - `vocab_h6.json`: Target HSK 6 vocabulary pool (1,237 entries, 1,117 unique words).
  - `H6_outline.json`: Master syllabus data (55 units, 165 lessons, 1,117 unique words, 1,149 word slots).
  - `H6_outline.md`: Master human-readable curriculum outline tables with definitions, POS, pinyin, and bilingual translations (en/vi).
  - `H6.json`: Production interactive textbook dataset (165 lessons with tokens, pinyin, en/vi translations, audio keys).
  - `H6_content.md`: Clean Chinese reader containing all 165 lesson dialogues and passages.

---

## 2. Target Production JSON Specification (`H6.json`)

The final output file (`H6.json`) consumed by the web and mobile frontend application strictly adheres to the data architecture of `H5.json` and `H4.json`. It is a root JSON array of **165 Passage Objects** (55 units $\times$ 3 lessons/unit).

### 2.1 Complete JSON Schema & Sample

```json
[
  {
    "passage_id": "H6_1_1",
    "text_type": "dialogue",
    "new_words": [
      "厨师",
      "家常",
      "品尝",
      "烧",
      "嫩",
      "香",
      "可口"
    ],
    "lines": [
      {
        "line_id": 1,
        "speaker": "李伟",
        "content": "张厨师，听说您做的家常豆腐特别地道，今天特意来向您请教做法。",
        "pinyin": "Zhāng chúshī ， tīngshuō nín zuò de jiācháng dòufu tèbié dìdao ， jīntiān tèyì lái xiàng nín qǐngjiào zuòfǎ 。",
        "audio_key": "H6_1_1_1",
        "translations": {
          "en": "Chef Zhang, I heard your home-style tofu is exceptionally authentic. I came today specially to ask for your recipe.",
          "vi": "Đầu bếp Trương, nghe nói món đậu phụ gia đình của bác làm rất chuẩn vị, hôm nay cháu đặc biệt đến xin bác chỉ giáo cách làm ạ."
        },
        "tokens": [
          "张",
          "厨师",
          "，",
          "听说",
          "您",
          "做",
          "的",
          "家常",
          "豆腐",
          "特别",
          "地道",
          "，",
          "今天",
          "特意",
          "来",
          "向",
          "您",
          "请教",
          "做法",
          "。"
        ]
      }
    ]
  }
]
```

### 2.2 Field Definitions & Data Architecture

#### Top-Level Passage Object (`Passage`)
| Field | Type | Description | Constraints & Invariants |
| :--- | :---: | :--- | :--- |
| `passage_id` | `string` | Unique lesson identifier | Format: `H6_{unit}_{lesson_in_unit}`, e.g., `H6_1_1` to `H6_55_3`. Exactly 165 objects (55 Units $\times$ 3). |
| `text_type` | `string` | Structural genre of the lesson | Either `"dialogue"` (interpersonal spoken interaction) or `"passage"` (continuous narrative / exposition). |
| `new_words` | `string[]` | Ordered target HSK 6 vocabulary | Exactly matches `new_words` defined in `H6_outline.json` (6–7 words/lesson, covering all 1,117 unique words across the curriculum). |
| `lines` | `object[]` | Array of ordered sentence / turn objects | Length $\le \text{len}(new\_words) + 2$. Strictly sequential `line_id` starting at `1`. |

#### Line Item Object (`Line`)
| Field | Type | Description | Constraints & Invariants |
| :--- | :---: | :--- | :--- |
| `line_id` | `integer` | 1-based index within the passage | Increments sequentially from `1` to `N` without gaps. |
| `speaker` | `string` | Character name speaking the line | **Dialogues**: Exactly 2 alternating speakers (1 Male + 1 Female). No consecutive turns by the same speaker.<br>**Passages**: Consistent named narrator (e.g. `李老师`, `张老师`, `王记者`). |
| `content` | `string` | Full Chinese sentence text | Natural Chinese punctuation marks (`，。？！“”`). Zero out-of-syllabus words. Natural flow without robotic vocatives. |
| `tokens` | `string[]` | Word-segmented token array | Lossless concatenation: `"".join(tokens) == content`. Every punctuation mark and numeral is an isolated token. |
| `pinyin` | `string` | Space-separated tone-marked pinyin | **Strict 1-to-1 token alignment**: `len(pinyin.split(' ')) == len(tokens)`. Punctuation tokens carry matching punctuation marks in pinyin. Tone sandhi applied (`一`, `不`). |
| `audio_key` | `string` | Unique audio segment key | Format: `{passage_id}_{line_id}`, e.g., `H6_1_1_1`. Strictly matches line index. |
| `translations` | `object` | Contextual bilingual translations | `{"en": "...", "vi": "..."}`. Natural, professional English and Vietnamese translations accurately conveying nuances. |

### 2.3 The 5 Mandatory Data Invariants (Zero-Tolerance Verification)
Every lesson and sentence in `H6.json` must satisfy all 5 invariants:
1. **Lossless Token Concatenation Invariant**:
   $$\text{content} \equiv \sum_{t \in \text{tokens}} t \quad \left(\text{i.e. } \texttt{"".join(tokens) == content}\right)$$
2. **Strict Token-Pinyin Alignment Invariant**:
   $$\text{len}(\text{pinyin.split}(' ')) \equiv \text{len}(\text{tokens})$$
3. **Sequential Line ID & Audio Key Invariant**:
   $$\text{audio\_key}_i \equiv \text{passage\_id} + \texttt{"\_"} + \text{str}(i) \quad \text{for } i \in \{1, \dots, N\}$$
4. **Complete Bilingual Coverage Invariant**:
   $$\forall \text{line}: \quad \text{translations.en} \ne \varnothing \quad \land \quad \text{translations.vi} \ne \varnothing$$
5. **Alternating Speaker Discipline (Dialogues)**:
   $$\text{speaker}_i \ne \text{speaker}_{i-1} \quad \forall i \ge 2, \quad \text{with } |\text{distinct}(\text{speakers})| \equiv 2$$

---

## 3. Curriculum Architecture & Pedagogical Whitelist Rules

### 3.1 Course Structure
- **Units**: **55 Units** grouped into **9 Comprehensive Modules**:
  1. Module 1: Home, Culinary Arts & Family Life *(Units 1–6)*
  2. Module 2: Health, Medicine, Body & Psychology *(Units 7–12)*
  3. Module 3: Education, Academic Growth & Language Learning *(Units 13–15)*
  4. Module 4: Workplace, Business & Financial Management *(Units 16–21)*
  5. Module 5: Science, Technology, Media & Arts *(Units 22–26)*
  6. Module 6: Sports, Leisure, Travel & Transportation *(Units 27–31)*
  7. Module 7: Nature, Geography, Urban-Rural & Environment *(Units 32–35)*
  8. Module 8: Law, Public Security, Governance & History *(Units 36–40)*
  9. Module 9: Actions, Spatial-Temporal & Advanced Discourse *(Units 41–55)*
- **Lesson Rhythm**: Exactly **3 Lessons per Unit**:
  - `_1`: 🗣️ Dialogue (Interpersonal spoken interaction)
  - `_2`: 🗣️ Dialogue (Deepened scenario / communicative conflict)
  - `_3`: 📖 Passage (Expository, descriptive, or narrative synthesis)
- **Total Lessons**: **165 Lessons** (110 Dialogues + 55 Passages).
- **Pacing**: 6–7 target words per lesson (Units 1–53: 7 words/lesson; Units 54–55: 6–7 words/lesson).

### 3.2 Cumulative Whitelist Invariant ($i+1$)
Students must never encounter untaught vocabulary. Content generation enforces strict cumulative gating:
$$\text{Tokens}(\text{Lesson } k) \subseteq V_{\text{base}} \cup \left( \bigcup_{j=1}^{k} \text{new\_words}_j \right)$$
Where:
- $V_{\text{base}}$: All **4,553 words** from `vocab_h5.json` (HSK 1–5, plus standard de-erhua forms like `玩儿` $\to$ `玩`, `一点儿` $\to$ `一点`) + approved proper names (`李伟`, `王芳`, `小王`, `小李`, `大卫`, `丽丽`, `小明`, `李老师`, `王老师`, `张老师`, `王经理`, `张大爷`, `王大妈`) + basic grammatical particles/prepositions (`把`, `往`, `嗯`, `啊`, `呀`, `吧`, `呢`, `哦`). *(Note: `另`, `啦`, `嘛` are target words in `vocab_h6.json` and remain strictly gated until their assigned lesson.)*
- $\text{new\_words}_j$: The target words introduced up to and including lesson $j$.

### 3.3 Natural Spoken Interaction Rules
- **No Formulaic Vocatives**: Ban robotic line openers where characters repeatedly shout the other person's name at turn beginnings.
- **Natural Discourse Markers**: Use realistic spoken markers (`其实`, `既然`, `话说回来`, `依我看`, `坦白说`) suitable for advanced HSK 6 proficiency.
- **Polysemy Reinforcement**: Units 54 and 55 systematically reinforce 32 high-value polysemous words (e.g., `除`, `服`, `扣`, `聊`, `扎`, `两手`, `同行`, `利`, `集`, `打发`) with their secondary and abstract senses.

---

## 4. End-to-End Execution Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Vocabulary Extraction & Cleaning                   │
│ - Source: chinese_dict.csv (Jackyee18/my_chinese)           │
│ - generate_vocabs.py -> vocab_h5.json (4,553 H1-H5 words)   │
│                      -> vocab_h6.json (1,237 H6 records)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Master Curriculum Outline & Syllabus               │
│ - gemini-code-1794478039558.json (Units 1-52)               │
│ - gemini-code-1794478480184.json (Units 53-55)              │
│ - build_h6_outline.py -> H6_outline.json (165 lessons)      │
│                       -> H6_outline.md (full syllabus)      │
│ - 100% vocabulary coverage verification (1,117 unique words)│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Content Generation with Cumulative Whitelist       │
│ - Lesson drafting using LLM with strict context constraints │
│ - Enforcement of alternating speakers & line length bounds  │
│ - verify_h6_content.py -> Invariant & whitelist auditor    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Production Pipeline & Multilingual Alignment       │
│ - build_h6_json.py (Skeleton -> Translations -> Pinyin)     │
│ - H6.json: 165 lessons, lossless tokens, pinyin, en/vi      │
│ - H6_content.md: Clean Chinese textbook reader              │
│ - Automated verification of all 5 invariants                │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Master File Inventory

| File | Status | Description |
| :--- | :---: | :--- |
| **`H6_outline.json`** | **Master Deliverable** | 55-Unit, 165-Lesson master syllabus JSON with scenario metadata and target words. |
| **`H6_outline.md`** | **Master Deliverable** | Human-readable comprehensive syllabus table with Hanzi, Pinyin, POS, English, and Vietnamese. |
| **`vocab_h6.json`** | **Source Database** | Target HSK 6 vocabulary pool (1,237 entries, 1,117 unique words). |
| **`vocab_h5.json`** | **Reference Database** | Cumulative base whitelist (4,553 words covering HSK 1 through HSK 5). |
| `hsk6_curriculum_outline.json` | Alternative Outline | 60-Unit, 180-Lesson alternative outline structure (1,117 words, 0 duplicates). |
| `build_h6_outline.py` | Pipeline Script | Reproducible consolidation engine that combined slices into `H6_outline.json` & `H6_outline.md`. |
| `generate_vocabs.py` | Data ETL Script | Extracts `vocab_h5.json` and `vocab_h6.json` from `my_chinese/chinese_dict.csv`. |
| `H6.json` | Target Deliverable | Final interactive textbook JSON dataset (165 lessons, aligned pinyin, en/vi). |
| `H6_content.md` | Target Deliverable | Human-readable reader markdown containing all 165 lesson dialogues and passages. |
| `agent.md` | Active Specification | Master project specification, architecture documentation, and lifecycle tracker. |

---

## 6. Verification & Audit Scripts

### 6.1 Vocabulary Coverage Audit
```powershell
python -c "
import json
with open('H6_outline.json', encoding='utf-8') as f:
    outline = json.load(f)
with open('vocab_h6.json', encoding='utf-8') as f:
    vocab = json.load(f)
vocab_set = set(x['cn'].strip() for x in vocab)
outline_set = set(w.strip() for l in outline for w in l.get('new_words', []))
missing = vocab_set - outline_set
extra = outline_set - vocab_set
assert len(missing) == 0, f'Missing words: {missing}'
assert len(extra) == 0, f'Extra words: {extra}'
print(f'100% Coverage Verified! All {len(vocab_set)} unique HSK 6 words covered across {len(outline)} lessons.')
"
```

### 6.2 Target Production Invariants Verification (`H6.json`)
```powershell
python -c "
import json
data = json.load(open('H6.json', encoding='utf-8'))
assert len(data) == 165, f'Expected 165 lessons, got {len(data)}'
total_lines = 0
for p in data:
    assert 'passage_id' in p and 'text_type' in p and 'new_words' in p and 'lines' in p
    for l in p['lines']:
        total_lines += 1
        assert ''.join(l['tokens']) == l['content'], f'Lossless token error in {l[\"audio_key\"]}'
        assert len(l['pinyin'].split(' ')) == len(l['tokens']), f'Pinyin alignment error in {l[\"audio_key\"]}'
        assert l['audio_key'] == f'{p[\"passage_id\"]}_{l[\"line_id\"]}', f'Audio key mismatch in {l[\"audio_key\"]}'
        assert l['translations']['en'] and l['translations']['vi'], f'Missing translation in {l[\"audio_key\"]}'
print(f'H6.json: All 5 invariants 100% Verified across {len(data)} lessons ({total_lines} lines)!')
"
```

---

## 7. Content Generation Execution Plan (`H6_lesson_contents.json` $\to$ `H6.json`)

> **Status**: Draft Plan — awaiting final sign-off on Section 7.5 decisions before generating scripts or lesson content.

### 7.1 Phase 1: Deterministic Whitelist & Validator Engine (`verify_h6_content.py`)
Modeled on `HSK5 builder/verify_h5_content.py`, enforce zero-tolerance cumulative checks before any full-scale generation:
1. **Cumulative Vocabulary Builder ($V_k$)**:
   - Load all **4,553** HSK 1–5 words from `vocab_h5.json` (plus standard de-erhua forms and approved speaker names/extras).
   - For lesson index $k \in [0, 164]$, union $V_{\text{HSK 1–5}}$ with $\bigcup_{j=0}^{k} \text{new\_words}(j)$ from `H6_outline.json`.
   - Map every HSK 6 word in `vocab_h6.json` to its **first-appearance** lesson index (`h6_word_to_idx`) so words are unlocked only from their introduction lesson onward.
2. **Two-Pass Segmentation & Leak Audit**:
   - **Pass 1 (Forward Max-Match Leak Detection)**: Scans each sentence against `vocab_k | future_h6` to catch any future HSK 6 compound ($j > k$) that might otherwise split into single HSK 1–5 characters.
   - **Pass 2 (Exact DP Segmentation over $V_k$)**: Confirms 100% of every sentence segments into valid tokens from $V_k$ plus punctuation/digits, reporting the exact lesson ID and offending span on any OOV or leak.
3. **Structural & Coverage Checks**:
   - `passage_id`, `text_type`, and `new_words` match `H6_outline.json` 100%.
   - Line count is in `[4, len(new_words) + 2]` (**6–9 lines** per lesson).
   - **Dialogues (110 lessons)**: Exactly 2 speakers alternating every turn (`speaker[i] != speaker[i-1]`).
   - **Passages (55 lessons)**: 1 consistent narrator across all sentences.
   - 100% of `new_words` appear intact in the lesson text.

### 7.2 Phase 2: Pedagogical & Writing Standards
1. **Scenario-Anchored Micro-Plots**: Every lesson follows the `title` and `scenario` in `H6_outline.json` with a natural 3-step arc: **Context/Opening $\to$ Development/Contrast $\to$ Resolution/Takeaway**.
2. **Pacing & Density**: **6–8 lines** per lesson ($\le \text{len}(\text{new\_words}) + 2$), introducing **1 target word (at most 2)** per line so sentences stay conversational and digestible.
3. **Polysemy Handling**: Units 1–53 use each word's primary contextual sense; **Units 54–55** explicitly showcase the secondary/abstract senses of the 32 reinforced polysemous words.
4. **Approved Speaker Pool**: `{"李伟", "王芳", "小王", "小李", "大卫", "丽丽", "小明", "李老师", "王老师", "张老师", "王经理", "张大爷", "王大妈"}`.

### 7.3 Phase 3: Batch Generation & Self-Correction Loop
Generate and verify all **165 lessons** in **6 batches** across the 55 units:
- **Batch 1**: Units 1–9 (`H6_1_1` – `H6_9_3`, 27 lessons — Modules 1–2)
- **Batch 2**: Units 10–18 (`H6_10_1` – `H6_18_3`, 27 lessons — Modules 2–4)
- **Batch 3**: Units 19–27 (`H6_19_1` – `H6_27_3`, 27 lessons — Modules 4–6)
- **Batch 4**: Units 28–36 (`H6_28_1` – `H6_36_3`, 27 lessons — Modules 6–8)
- **Batch 5**: Units 37–45 (`H6_37_1` – `H6_45_3`, 27 lessons — Modules 8–9)
- **Batch 6**: Units 46–55 (`H6_46_1` – `H6_55_3`, 30 lessons — Module 9 & Polysemy Review)

Workflow per batch:
1. Draft batch JSON (`batch_N.json`) using only $V_k$.
2. Run `python verify_h6_content.py batch_N.json` and rewrite any flagged line until **0 errors**.
3. Merge all verified batches into `H6_lesson_contents.json` and render `H6_content.md`.

### 7.4 Phase 4: Full Production JSON Pipeline (`build_h6_json.py` $\to$ `H6.json`)
Modeled on `HSK5 builder/build_h5_json.py`:
1. **Stage 1 — Skeleton & Lossless Tokenization (`H6_step1_skeleton.json`)**: Tokenize every line over $V_k$ (`"".join(tokens) == content`) and generate `audio_key = f"{passage_id}_{line_id}"`.
2. **Stage 2 — Bilingual Translations (`H6_step2_translations_cache.json`)**: Generate idiomatic English (`en`) and persona-appropriate Vietnamese (`vi`) translations for all lines.
3. **Stage 3 — Token-Aligned Pinyin**: Generate tone-marked `pinyin` strictly aligned 1-to-1 with `tokens` (`len(pinyin.split(" ")) == len(tokens)`), applying `一`/`不` tone sandhi, polyphone rules, and sentence-initial capitalization.
4. **Stage 4 — Final Assembly & Audit (`H6.json`)**: Assemble `H6.json` and run the 5-invariant test suite across all 165 lessons.

### 7.5 Open Decisions to Finalize Before Execution
1. **Dictionary Typo in `H6_53_3` (`讲攻` vs `讲究`)**: In `vocab_h6.json` (`id: 3777`, `py: "jiǎngjiu"`), `cn` is `"讲攻"`. Accept both `"讲攻"` and `"讲究"` in `verify_h6_content.py` (like `"贈送"`/`"赠送"` in HSK 5), or keep `"讲攻"`?
2. **Base Whitelist Extras (`approved_extras`)**: Confirm including standard de-erhua forms from `vocab_h5.json`, `"把", "往", "嗯", "啊", "呀", "吧", "呢", "哦"`, and approved speaker names (with `另`, `啦`, `嘛` strictly gated to their HSK 6 lessons).
3. **Execution Staging**: Pilot **Unit 1 (`H6_1_1`–`H6_1_3`)** first, complete **Phases 1–3 (`H6_lesson_contents.json` + `H6_content.md`)** before Phase 4, or run end-to-end?

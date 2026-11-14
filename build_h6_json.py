import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from openai import OpenAI
from pypinyin import pinyin as pypinyin_convert, Style
from verify_h6_content import load_resources, segment_and_check

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File Paths
LESSON_CONTENTS_FILE = os.path.join(BASE_DIR, "H6_lesson_contents.json")
SKELETON_FILE = os.path.join(BASE_DIR, "H6_step1_skeleton.json")
TRANSLATIONS_CACHE_FILE = os.path.join(BASE_DIR, "H6_step2_translations_cache.json")
FINAL_OUTPUT_FILE = os.path.join(BASE_DIR, "H6.json")

BATCH_SIZE = 4       # 4 lessons per batch (~24 lines)
MAX_WORKERS = 6      # 6 concurrent API workers


def atomic_write_json(path: str, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


# ==============================================================================
# STAGE 1: Build Skeleton with Exact Tokens & Audio Keys
# ==============================================================================


def step1_build_skeleton():
    print("[Stage 1] Building structural skeleton with exact tokenization...")
    outline, base_vocab, h6_word_to_idx, h6_word_to_pid = load_resources()
    outline_by_id = {item["passage_id"]: idx for idx, item in enumerate(outline)}

    with open(LESSON_CONTENTS_FILE, encoding="utf-8") as f:
        lessons = json.load(f)

    skeleton = []
    total_lines = 0
    for lesson in lessons:
        pid = lesson["passage_id"]
        l_idx = outline_by_id[pid]

        pass_item = {
            "passage_id": pid,
            "text_type": lesson["text_type"],
            "new_words": lesson["new_words"],
            "lines": [],
        }

        for line in lesson["lines"]:
            lid = line["line_id"]
            content = line["content"]
            akey = f"{pid}_{lid}"

            ok, tokens, errs = segment_and_check(
                content, l_idx, base_vocab, h6_word_to_idx, h6_word_to_pid
            )
            assert ok and "".join(tokens) == content, (
                f"Tokenization error on {akey}: {errs}"
            )

            pass_item["lines"].append(
                {
                    "line_id": lid,
                    "speaker": line["speaker"],
                    "content": content,
                    "audio_key": akey,
                    "tokens": tokens,
                }
            )
            total_lines += 1

        skeleton.append(pass_item)

    atomic_write_json(SKELETON_FILE, skeleton)
    print(
        f"[Stage 1] Successfully built skeleton for {len(skeleton)} lessons ({total_lines} lines) -> {SKELETON_FILE}"
    )
    return skeleton


# ==============================================================================
# STAGE 2: Batched LLM Translations (en & vi)
# ==============================================================================

SYSTEM_PROMPT = """You are an expert bilingual translator for Chinese learning textbooks (HSK 6).
You will receive a JSON list of dialogue turns or passage sentences in context.
For each item, output:
1. "audio_key": The exact audio key provided.
2. "translations":
   - "en": Fluent, natural, idiomatic English translation.
   - "vi": Culturally natural, accurate Vietnamese translation with appropriate pronouns (thầy/cô - em, anh/chị - em, bạn - mình, bác sĩ - tôi, cháu - ông/bà).

OUTPUT FORMAT:
Return ONLY a valid JSON object with the key "items":
{
  "items": [
    {
      "audio_key": "H6_1_1_1",
      "translations": {
        "en": "...",
        "vi": "..."
      }
    }
  ]
}"""


def process_translation_batch(
    client: OpenAI,
    b_idx: int,
    total_b: int,
    batch_lessons: list[dict],
    trans_cache: dict[str, dict],
    cache_lock: threading.RLock,
):
    pending = []
    with cache_lock:
        for lesson in batch_lessons:
            for line in lesson["lines"]:
                akey = line["audio_key"]
                entry = trans_cache.get(akey)
                if not (entry and entry.get("en", "").strip() and entry.get("vi", "").strip()):
                    pending.append(
                        {
                            "audio_key": akey,
                            "speaker": line["speaker"],
                            "content": line["content"],
                        }
                    )

    if not pending:
        return

    expected_keys = {it["audio_key"] for it in pending}
    pids = [l["passage_id"] for l in batch_lessons]
    user_prompt = (
        f"Translate ALL {len(pending)} Chinese lines from lessons {pids}. "
        f"Do not omit any audio_key:\n\n{json.dumps(pending, ensure_ascii=False, indent=2)}"
    )

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=90,
            )
            raw = resp.choices[0].message.content or ""
            data = json.loads(raw)
            items = data.get("items", [])

            got_keys = set()
            with cache_lock:
                for it in items:
                    akey = it.get("audio_key")
                    translations = it.get("translations", {})
                    en = translations.get("en", "").strip()
                    vi = translations.get("vi", "").strip()
                    if akey in expected_keys and en and vi:
                        trans_cache[akey] = {"en": en, "vi": vi}
                        got_keys.add(akey)
                atomic_write_json(TRANSLATIONS_CACHE_FILE, trans_cache)

            missing = expected_keys - got_keys
            if missing:
                raise ValueError(f"Missing translations for keys: {sorted(missing)}")

            print(
                f"[Stage 2] Batch {b_idx + 1}/{total_b} ({pids}) done ({len(got_keys)} lines cached).",
                flush=True,
            )
            return
        except Exception as e:
            print(
                f"[Stage 2] Batch {b_idx + 1} attempt {attempt + 1} failed: {e}",
                flush=True,
            )
            if attempt == 2:
                raise


def step2_generate_translations(skeleton: list[dict]) -> dict[str, dict]:
    print("[Stage 2] Checking and generating bilingual translations...")
    trans_cache = {}
    if os.path.exists(TRANSLATIONS_CACHE_FILE):
        try:
            with open(TRANSLATIONS_CACHE_FILE, encoding="utf-8") as f:
                trans_cache = json.load(f)
        except Exception:
            trans_cache = {}

    total_lines = sum(len(p["lines"]) for p in skeleton)
    cached_count = sum(
        1
        for p in skeleton
        for l in p["lines"]
        if trans_cache.get(l["audio_key"], {}).get("en", "").strip()
        and trans_cache.get(l["audio_key"], {}).get("vi", "").strip()
    )
    print(f"[Stage 2] Already cached translations: {cached_count}/{total_lines}")

    if cached_count == total_lines:
        print("[Stage 2] All translations already cached!")
        return trans_cache

    load_dotenv(os.path.join(BASE_DIR, ".env"))
    h4_env = os.path.abspath(os.path.join(BASE_DIR, "..", "HSK4 builder", ".env"))
    if os.path.exists(h4_env):
        load_dotenv(h4_env)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("Missing DEEPSEEK_API_KEY")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    batches = [
        skeleton[i : i + BATCH_SIZE] for i in range(0, len(skeleton), BATCH_SIZE)
    ]
    cache_lock = threading.RLock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                process_translation_batch,
                client,
                idx,
                len(batches),
                b,
                trans_cache,
                cache_lock,
            )
            for idx, b in enumerate(batches)
        ]
        for f in as_completed(futures):
            f.result()

    print(
        f"[Stage 2] Completed translations! Cached: {len(trans_cache)}/{total_lines}"
    )
    return trans_cache


# ==============================================================================
# STAGE 3: Deterministic Token-Aligned Pinyin Builder
# ==============================================================================

FOURTH_TONE_VOWELS = set("àèìòùǜ")
FIRST_SECOND_THIRD_VOWELS = set("āēīōūǖáéíóúǘǎěǐǒǔǚ")


def get_token_pinyin(
    tok: str, full_sentence: str, tok_idx: int, tokens: list[str], passage_id: str = ""
) -> str:
    if not re.search(r"[\u4e00-\u9fff]", tok):
        cleaned = re.sub(r"\s+", "", tok)
        return cleaned if cleaned else "_"

    # Context-specific polyphone overrides
    if tok == "待":
        if (
            "多待" in full_sentence
            or "待在" in full_sentence
            or "待一" in full_sentence
            or "待了" in full_sentence
        ):
            return "dāi"
        return "dài"

    if tok == "吐":
        if "想吐" in full_sentence or "呕吐" in full_sentence or "吐了" in full_sentence:
            return "tù"
        if "吐痰" in full_sentence or "地上吐" in full_sentence:
            return "tǔ"

    if tok == "扇":
        if tok_idx + 1 < len(tokens) and tokens[tok_idx + 1] in [
            "木头",
            "窗户",
            "门",
            "窗",
        ]:
            return "shàn"
        if tok_idx > 0 and tokens[tok_idx - 1] in ["这", "那", "一", "两", "每"]:
            return "shàn"
        return "shān"

    if tok == "得了":
        if "得了便宜" in full_sentence:
            return "déliǎo"
        return "déle"

    if tok == "同行":
        if passage_id == "H6_55_1":
            return "tóngháng"
        return "tóngxíng"

    if tok == "便宜":
        return "piányi"

    if tok == "便":
        if tok_idx > 0 and tokens[tok_idx - 1] == "方":
            return "biàn"
        return "biàn"

    if tok == "将军":
        return "jiāngjūn"

    syls = [s[0] for s in pypinyin_convert(tok, style=Style.TONE, heteronym=False)]
    return re.sub(r"\s+", "", "".join(syls).lower())


def build_pinyin_for_line(
    tokens: list[str], content: str, passage_id: str = ""
) -> str:
    raw_py = [
        get_token_pinyin(tok, content, i, tokens, passage_id)
        for i, tok in enumerate(tokens)
    ]

    # Apply 一 and 不 tone sandhi
    n = len(tokens)
    for i in range(n - 1):
        if not re.search(r"[\u4e00-\u9fff]", tokens[i + 1]):
            continue
        next_tok = tokens[i + 1]
        next_first_syl = pypinyin_convert(
            next_tok[0], style=Style.TONE, heteronym=False
        )[0][0]
        is_next_fourth = any(ch in FOURTH_TONE_VOWELS for ch in next_first_syl)
        is_next_123 = any(ch in FIRST_SECOND_THIRD_VOWELS for ch in next_first_syl)

        if tokens[i] == "不" and is_next_fourth:
            raw_py[i] = "bú"
        elif tokens[i] == "一":
            if is_next_fourth:
                raw_py[i] = "yí"
            elif is_next_123:
                raw_py[i] = "yì"

    # Capitalize the very first Chinese word token
    capitalized = False
    final_py = []
    for tok, py in zip(tokens, raw_py):
        if re.search(r"[\u4e00-\u9fff]", tok) and not capitalized and py:
            py = py[0].upper() + py[1:]
            capitalized = True
        final_py.append(py)

    return " ".join(final_py)


# ==============================================================================
# STAGE 4: Final Assembly & 5-Invariant Verification
# ==============================================================================


def step4_assemble_final(skeleton: list[dict], trans_cache: dict[str, dict]):
    print("[Stage 4] Assembling final H6.json and verifying invariants...")
    final_data = []

    for p in skeleton:
        pid = p["passage_id"]
        pass_item = {
            "passage_id": pid,
            "text_type": p["text_type"],
            "new_words": p["new_words"],
            "lines": [],
        }

        for l in p["lines"]:
            akey = l["audio_key"]
            tokens = l["tokens"]
            content = l["content"]

            pinyin_str = build_pinyin_for_line(tokens, content, pid)
            translations = trans_cache[akey]

            pass_item["lines"].append(
                {
                    "line_id": l["line_id"],
                    "speaker": l["speaker"],
                    "content": content,
                    "pinyin": pinyin_str,
                    "audio_key": akey,
                    "translations": translations,
                    "tokens": tokens,
                }
            )

        final_data.append(pass_item)

    atomic_write_json(FINAL_OUTPUT_FILE, final_data)
    print(
        f"[Stage 4] Output written to {FINAL_OUTPUT_FILE} ({len(final_data)} lessons, {os.path.getsize(FINAL_OUTPUT_FILE):,} bytes)."
    )

    print("[Stage 4] Running 5 data invariant tests...")
    assert len(final_data) == 165, f"Expected 165 lessons, got {len(final_data)}"

    total_lines = 0
    for p in final_data:
        pid = p["passage_id"]
        speakers = [l["speaker"] for l in p["lines"]]
        if p["text_type"] == "dialogue":
            assert len(set(speakers)) == 2, f"Expected 2 speakers in {pid}, got {set(speakers)}"
            for k in range(1, len(speakers)):
                assert speakers[k] != speakers[k - 1], f"Non-alternating speakers in {pid}"
        else:
            assert len(set(speakers)) == 1, f"Expected 1 narrator in {pid}, got {set(speakers)}"

        for l in p["lines"]:
            akey = l["audio_key"]
            assert "".join(l["tokens"]) == l["content"], f"Lossless token error in {akey}"
            assert len(l["pinyin"].split(" ")) == len(l["tokens"]), (
                f"Pinyin alignment error in {akey}: {l['pinyin'].split(' ')} vs {l['tokens']}"
            )
            assert akey == f"{pid}_{l['line_id']}", f"Audio key mismatch in {akey}"
            assert (
                l["translations"].get("en", "").strip()
                and l["translations"].get("vi", "").strip()
            ), f"Empty translation in {akey}"
            total_lines += 1

    print(
        f"SUCCESS: H6.json with all {len(final_data)} lessons ({total_lines} lines) PASSED all 5 data invariants 100%!"
    )


if __name__ == "__main__":
    skeleton = step1_build_skeleton()
    trans_cache = step2_generate_translations(skeleton)
    step4_assemble_final(skeleton, trans_cache)

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PUNCT_AND_DIGITS = set(
    "，。？！“”‘’、；：…—（）()《》0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ% "
)


def load_resources():
    with open(os.path.join(BASE_DIR, "H6_outline.json"), encoding="utf-8") as f:
        outline = json.load(f)
    with open(os.path.join(BASE_DIR, "vocab_h5.json"), encoding="utf-8") as f:
        h5 = json.load(f)

    # Map each H6 target word to its FIRST lesson index (0..164) and passage_id
    h6_word_to_idx = {}
    h6_word_to_pid = {}
    for idx, item in enumerate(outline):
        pid = item["passage_id"]
        for w in item["new_words"]:
            if w not in h6_word_to_idx:
                h6_word_to_idx[w] = idx
                h6_word_to_pid[w] = pid

    raw_h5 = {item["cn"].strip() for item in h5}
    h15_words = set(raw_h5)

    # Standard de-erhua forms for H1-5 erhua words, excluding H6 target words not raw in H5
    exceptions = ("女儿", "儿子", "儿童", "幼儿园", "模特儿")
    for w in raw_h5:
        if w.endswith("儿") and len(w) > 1 and w not in exceptions:
            cand = w[:-1]
            if cand not in h6_word_to_idx or cand in raw_h5:
                h15_words.add(cand)

    # Approved extras (strictly excludes H6 target words like 另, 啦, 嘛)
    approved_extras = {
        "把", "往", "陪", "聊", "猜", "嗯", "啊", "呀", "吧", "呢", "哦",
        "点儿", "块儿", "会儿", "头儿",
        "李伟", "王芳", "小王", "小李", "大卫", "丽丽", "小明",
        "李老师", "王老师", "张老师", "王经理", "张大爷", "王大妈",
    }
    base_vocab = h15_words | approved_extras

    return outline, base_vocab, h6_word_to_idx, h6_word_to_pid


def segment_and_check(sentence, lesson_idx, base_vocab, h6_word_to_idx, h6_word_to_pid):
    """
    Checks a sentence for Lesson `lesson_idx`:
    1. Forward max-match scan over all known words (vocab_k | future_h6) to detect future H6 word leaks.
    2. Exact DP segmentation over vocab_k (base_vocab + H6 words introduced at idx <= lesson_idx).
    Returns (is_valid, tokens, errors).
    """
    errors = []
    allowed_h6 = {w for w, idx in h6_word_to_idx.items() if idx <= lesson_idx}
    future_h6 = {
        w: h6_word_to_pid[w]
        for w, idx in h6_word_to_idx.items()
        if idx > lesson_idx and w not in base_vocab
    }

    vocab_k = base_vocab | allowed_h6
    all_known = vocab_k | set(future_h6.keys())
    max_len = max((len(w) for w in all_known), default=8)

    n = len(sentence)
    i = 0
    while i < n:
        ch = sentence[i]
        if ch in PUNCT_AND_DIGITS:
            i += 1
            continue
        matched = None
        for l in range(min(max_len, n - i), 0, -1):
            sub = sentence[i : i + l]
            if sub in all_known:
                matched = sub
                break
        if matched:
            if matched in future_h6 and matched not in vocab_k:
                errors.append(
                    f"Future HSK6 word leak: '{matched}' (belongs to {future_h6[matched]})"
                )
            i += len(matched)
        else:
            i += 1

    # Step 2: Exact DP segmentation using ONLY vocab_k (prefer fewest tokens / longest words)
    dp = [None] * (n + 1)
    dp[0] = []
    for i in range(1, n + 1):
        if sentence[i - 1] in PUNCT_AND_DIGITS:
            if dp[i - 1] is not None:
                dp[i] = dp[i - 1] + [sentence[i - 1]]
            continue
        best = None
        for j in range(max(0, i - max_len), i):
            if dp[j] is not None:
                sub = sentence[j:i]
                if sub in vocab_k:
                    cand = dp[j] + [sub]
                    if best is None or len(cand) < len(best):
                        best = cand
        dp[i] = best

    if dp[n] is None:
        furthest = 0
        for idx_p in range(n + 1):
            if dp[idx_p] is not None:
                furthest = idx_p
        bad_span = sentence[furthest : min(n, furthest + 6)]
        errors.append(
            f"OOV / unlearned word near: '{bad_span}' in sentence: '{sentence}'"
        )
        return False, [], errors

    return len(errors) == 0, dp[n], errors


def verify_file(filepath):
    outline, base_vocab, h6_word_to_idx, h6_word_to_pid = load_resources()
    outline_by_id = {
        item["passage_id"]: (idx, item) for idx, item in enumerate(outline)
    }

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    total_errors = 0

    for entry in data:
        pid = entry.get("passage_id")
        if pid not in outline_by_id:
            print(f"[ERROR] Unknown passage_id: {pid}")
            total_errors += 1
            continue

        lesson_idx, out_item = outline_by_id[pid]
        expected_nw = out_item["new_words"]
        expected_type = out_item["text_type"]

        if entry.get("text_type") != expected_type:
            print(
                f"[{pid}] text_type mismatch: got {entry.get('text_type')}, expected {expected_type}"
            )
            total_errors += 1
        if entry.get("new_words") != expected_nw:
            print(
                f"[{pid}] new_words mismatch: got {entry.get('new_words')}, expected {expected_nw}"
            )
            total_errors += 1

        lines = entry.get("lines", [])
        max_lines = len(expected_nw) + 2
        if not (4 <= len(lines) <= max_lines):
            print(f"[{pid}] Line count {len(lines)} out of range [4, {max_lines}]")
            total_errors += 1

        speakers = [l.get("speaker", "") for l in lines]
        if expected_type == "dialogue":
            uniq_sp = set(speakers)
            if len(uniq_sp) != 2:
                print(f"[{pid}] Dialogue must have exactly 2 speakers, got {uniq_sp}")
                total_errors += 1
            for k in range(1, len(speakers)):
                if speakers[k] == speakers[k - 1]:
                    print(
                        f"[{pid}] Non-alternating speaker on line {k + 1}: {speakers[k]}"
                    )
                    total_errors += 1
        else:
            if len(set(speakers)) != 1:
                print(
                    f"[{pid}] Passage must have 1 consistent narrator, got {set(speakers)}"
                )
                total_errors += 1

        full_text = "".join(l.get("content", "") for l in lines)
        for nw in expected_nw:
            if nw not in full_text:
                print(f"[{pid}] Missing target new_word: {nw}")
                total_errors += 1

        for l in lines:
            lid = l.get("line_id")
            content = l.get("content", "")
            ok, _tokens, errs = segment_and_check(
                content, lesson_idx, base_vocab, h6_word_to_idx, h6_word_to_pid
            )
            if not ok:
                for e in errs:
                    print(f"[{pid} Line {lid}] {e}")
                    total_errors += 1

    if total_errors == 0:
        print(
            f"SUCCESS: {filepath} ({len(data)} lessons) passed 100% of cumulative vocabulary & structural checks with 0 errors!"
        )
    else:
        print(f"FAILED: {filepath} had {total_errors} error(s).")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_h6_content.py <json_file>")
        sys.exit(1)
    verify_file(sys.argv[1])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爽文章節自動檢查器 —— 對齊 shuangwen-novel 技能嘅硬指標。

用法：
    python3 verify-chapter.py <chapter.txt> [...]        # 檢查指定章節
    python3 verify-chapter.py --dir <dir>                # 檢查目錄內全部 .txt

每章逐項驗：章長 / 段落數 / 平均段長 / 對話佔比 / 章尾鉤子 / 震場反應重複 /
對話標記重複 / 反轉詞密度 / 時間跳躍 / 心聲 / 半形標點 / 亂碼 / 重複段落。
退出碼 0 = 無 FAIL；1 = 有 FAIL。
"""

import argparse
import glob
import os
import re
import sys
from collections import Counter

REPL = "\ufffd"                # 亂碼替換符

# ── 目標值（來自 shuangwen-novel/references/measurements.md）────────────
TARGET = {
    "chapter_len": (1900, 3000, 4500),      # (目標下限, 目標上限, 硬上限)
    "paragraphs": (60, 110, 140),
    "avg_para": (0, 30, 40),
    "dialogue_ratio": (45.0, 60.0, 70.0),    # %
    "reverse_per_k": (4.0, 12.0, 20.0),
    "time_jumps": (0, 1, 2),
    "inner_voice": (0, 3, 5),
}

REVERSE_WORDS = ["但是", "但", "可是", "却", "然而", "不过", "反而",
                 "竟然", "居然", "没想到", "不料", "忽然", "突然", "猛地",
                 "愣", "懵", "傻眼", "震惊", "惊讶", "倒吸"]

TIME_MARKS = ["第二天", "翌日", "次日", "第三天", "一个小时后", "半小时后",
              "十分钟后", "晚上", "早上", "中午", "下午", "此时", "与此同时",
              "另一边", "同一时间", "次日清晨", "三天后", "一周后", "一个月后"]

# 震場反應句（參考作高頻集合，連續用同一種 = 疲勞）
SHOCK_PATTERNS = [
    "所有人都是一愣", "所有人都很吃惊", "所有人都懵了", "所有人都震惊了",
    "所有人都惊呆了", "众人面面相觑", "众人皆惊", "全场震惊", "全场都惊呆了",
    "全场都懵了", "众人傻在原地", "所有人都傻了", "所有人都大惊失色",
    "众人皆是一惊", "全场一片死寂", "所有人都惊了", "所有人都傻眼",
]
SHOCK_RE = re.compile("|".join(map(re.escape, SHOCK_PATTERNS)))

TAGS = ["说道", "喊道", "笑道", "怒道", "冷笑道", "叹气", "惊呆了", "懵了",
        "沉默了", "点点头", "眯起眼睛", "顿了顿", "道", "说", "问"]
TAG_RE = re.compile(
    r"([\u4e00-\u9fff]{2,4}?)("
    + "|".join(map(re.escape, sorted(TAGS, key=len, reverse=True)))
    + r")(?=[:\uff1a])"
)

# 半形標點緊鄰中文 → 疑似未轉全形
HALFWIDTH = re.compile(
    "[\u4e00-\u9fff][,.;:!?]|[,.;:!?][\u4e00-\u9fff]"
)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def paras(text):
    return [p.strip() for p in text.split("\n") if p.strip()]


def analyze(text):
    ps = paras(text)
    body = "".join(ps)
    n = len(body) or 1
    res = {}

    res["chapter_len"] = len(body)
    res["paragraphs"] = len(ps)
    res["avg_para"] = round(sum(len(p) for p in ps) / max(len(ps), 1), 1)
    res["max_para"] = max((len(p) for p in ps), default=0)

    quoted = sum(len(m) for m in re.findall(r"\u201c[^\u201d]*\u201d", body))
    res["dialogue_ratio"] = round(quoted / n * 100, 1)

    last = ps[-1] if ps else ""
    if re.search(r"(\u7a81\u7136|\u5ffd\u7136|\u7adf\u7136|\u5c45\u7136|\u731b\u5730|\u4e0d\u6599|\u51b7\u4e0d\u4e01)", last):
        res["hook"] = "轉折詞鉤子"
    elif last.endswith(("？", "?")):
        res["hook"] = "疑問鉤子"
    elif last.endswith(("！", "!")):
        res["hook"] = "驚嘆鉤子"
    elif re.search(r"(……|\.\.\.|…)$", last):
        res["hook"] = "省略號鉤子"
    elif re.search(r"[，,]$", last):
        res["hook"] = "逗號截斷"
    else:
        res["hook"] = "平鋪收尾"

    rev = sum(body.count(w) for w in REVERSE_WORDS)
    res["reverse_per_k"] = round(rev / (n / 1000), 2)
    res["time_jumps"] = sum(body.count(w) for w in TIME_MARKS)

    iv = re.findall(r"【([^】]*)】", body)
    res["inner_voice"] = len(iv)
    res["iv_bad_len"] = [s for s in iv if not (20 <= len(s) <= 60)]

    res["shock_counts"] = Counter(SHOCK_RE.findall(body))
    res["shock_max"] = res["shock_counts"].most_common(1)[0][1] if res["shock_counts"] else 0

    tags = TAG_RE.findall(body)
    res["tag_counts"] = Counter(tags)
    res["tag_max"] = res["tag_counts"].most_common(1)[0][1] if res["tag_counts"] else 0

    res["halfwidth"] = HALFWIDTH.findall(body)
    res["replacement_char"] = body.count(REPL)

    pc = Counter(p for p in ps if len(p) >= 12)
    res["dup_paras"] = {k: v for k, v in pc.items() if v > 1}
    return res


def check(res):
    """回傳 [(狀態, 項目, 實測, 目標)]"""
    out = []

    lo, hi, hard = TARGET["chapter_len"]
    v = res["chapter_len"]
    out.append(("FAIL" if v < lo or v > hard else ("WARN" if v > hi else "OK"),
                "章長", v, f"{lo}-{hi}（硬上限 {hard}）"))

    lo, hi, hard = TARGET["paragraphs"]
    v = res["paragraphs"]
    out.append(("FAIL" if v < lo or v > hard else ("WARN" if v > hi else "OK"),
                "段落數", v, f"{lo}-{hi}"))

    lo, hi, hard = TARGET["avg_para"]
    v = res["avg_para"]
    out.append(("FAIL" if v > hard else ("WARN" if v > hi else "OK"),
                "平均段長", v, f"≤{hi}"))

    lo, hi, hard = TARGET["dialogue_ratio"]
    v = res["dialogue_ratio"]
    out.append(("FAIL" if v < lo or v > hard else ("WARN" if v > hi else "OK"),
                "對話佔比", f"{v}%", f"{lo}%-{hi}%"))

    h = res["hook"]
    out.append(("OK" if h != "平鋪收尾" else "WARN", "章尾鉤子", h, "非平鋪收尾"))

    lo, hi, hard = TARGET["reverse_per_k"]
    v = res["reverse_per_k"]
    out.append(("FAIL" if v > hard else ("WARN" if v < lo else "OK"),
                "反轉詞/千字", v, f"{lo}-{hi}"))

    lo, hi, hard = TARGET["time_jumps"]
    v = res["time_jumps"]
    out.append(("FAIL" if v > hard else ("WARN" if v > hi else "OK"),
                "時間跳躍", v, f"≤{hi}"))

    lo, hi, hard = TARGET["inner_voice"]
    v = res["inner_voice"]
    out.append(("FAIL" if v > hard else ("WARN" if v > hi else "OK"),
                "心聲段數", v, f"≤{hi}"))
    if res["iv_bad_len"]:
        out.append(("WARN", "心聲長度",
                    f"{len(res['iv_bad_len'])} 段超出 20-60 字", "每段 20-60 字"))

    if res["shock_max"] >= 3:
        top = res["shock_counts"].most_common(1)[0]
        out.append(("FAIL", "震場反應重複", f"「{top[0]}」×{top[1]}", "同一句式 ≤2 次"))
    else:
        out.append(("OK", "震場反應重複", res["shock_max"], "≤2 次"))

    if res["tag_max"] >= 4:
        top = res["tag_counts"].most_common(1)[0]
        out.append(("FAIL", "對話標記重複", f"「{top[0][0]}{top[0][1]}」×{top[1]}", "同一標記 ≤3 次"))
    else:
        out.append(("OK", "對話標記重複", res["tag_max"], "≤3 次"))

    out.append(("FAIL" if res["halfwidth"] else "OK",
                "半形標點", len(res["halfwidth"]) or "無", "0"))
    out.append(("FAIL" if res["replacement_char"] else "OK",
                "亂碼 U+FFFD", res["replacement_char"], "0"))
    out.append(("FAIL" if res["dup_paras"] else "OK",
                "重複段落(≥12字)", len(res["dup_paras"]), "0"))

    if res["max_para"] > 80:
        out.append(("WARN", "最長段落", res["max_para"], "≤80 字"))
    return out


ICON = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}


def report(path, checks):
    fails = sum(1 for c in checks if c[0] == "FAIL")
    warns = sum(1 for c in checks if c[0] == "WARN")
    flag = "❌" if fails else ("⚠️ " if warns else "✅")
    print(f"\n{flag} {os.path.basename(path)}")
    for status, item, actual, target in checks:
        print(f"   {ICON[status]} {item:<14} 實測 {str(actual):<24} 目標 {target}")
    return fails, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir")
    a = ap.parse_args()

    paths = list(a.files)
    if a.dir:
        paths += sorted(glob.glob(os.path.join(a.dir, "*.txt")))
    if not paths:
        print(__doc__)
        return 2

    total_fail = total_warn = 0
    hook_hit = 0
    lens = []
    for p in paths:
        res = analyze(read(p))
        checks = check(res)
        f, w = report(p, checks)
        total_fail += f
        total_warn += w
        hook_hit += 1 if res["hook"] != "平鋪收尾" else 0
        lens.append(res["chapter_len"])

    print("\n" + "=" * 60)
    print(f"章數 {len(paths)}｜FAIL {total_fail}｜WARN {total_warn}")
    if lens:
        print(f"平均章長 {sum(lens)//len(lens)}｜最短 {min(lens)}｜最長 {max(lens)}")
    print(f"章尾鉤子率 {hook_hit/len(paths)*100:.1f}%（目標 ≥40%）")
    print("=" * 60)
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())

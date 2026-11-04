#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《信州・ふたり旅》章節品質驗證腳本

用法：
    python3 verify-chapter.py 11 12 13        # 驗證指定章（HTML 已注入）
    python3 verify-chapter.py --body 12        # 只驗證 _work/ch12_body.txt
    python3 verify-chapter.py --range 11 30    # 驗證整批

檢查項目（全部要 ✅）：
  1. 破折號「——」＝ 0
  2. ASCII 逗號/引號 ＝ 0
  3. 粵語口語詞 ＝ 0
  4. 簡體字 ＝ 0
  5. 「魔法」「兩位旅客」總數 ≤ 2
  6. 字數在 1800–2600
  7. HTML <p> 平衡
  8. CSS / JS 無外露到可見文字
  9. 無作者備註括號、無章號引用
  10. 無「Day X」字樣
  11. 鳳凰盒不得寫成發光（發亮/閃閃/展翅欲飛）
"""
import re
import sys
import os
from html.parser import HTMLParser

BASE = "/home/kenlo/hermes-novels/novels/shinshu/chapters"
WORK = "/home/kenlo/novels/_work"

CANTONESE = ["嘅", "咁", "係", "唔", "咩", "睇", "喺", "我哋", "攞", "啲",
             "乜", "嗰", "咗", "嘢", "邊度", "咁樣", "睇下", "仲", "俾"]
# 必須排除的合法用法：「係」可用於「就是…」？-> 禁止，改用「是」
SIMPLIFIED = set("为个国来时说过学们对开关门东车马鸟鱼长风飞门问间闻这还远进"
                 "过还发变风飞马鸟鱼长风开关闭门东车马长风飞门问间闻这这进过")
GLOW_WORDS = ["發亮", "闪闪发亮", "展翅欲飛", "如同一隻真的鳳凰", "閃閃發光",
              "散發著光", "發出光芒", "熠熠生輝", "閃著光"]

TAGS = ["魔法", "兩位旅客", "續講", "我即刻", "我都想"]


def count_words(s: str) -> int:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s", "", s)
    n = len(re.findall(r"[\u4e00-\u9fff]", s))
    n += len(re.findall(r"[\u3040-\u30ff]", s))
    n += len(re.findall(r"[0-9A-Za-z]", s))
    return n


def visible_text(html: str) -> str:
    class V(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tx = []
            self.sk = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("style", "script"):
                self.sk += 1

        def handle_endtag(self, tag):
            if tag in ("style", "script"):
                self.sk = max(0, self.sk - 1)

        def handle_data(self, d):
            if not self.sk:
                self.tx.append(d)

    v = V()
    v.feed(html)
    return "".join(v.tx)


def chapter_body(html: str) -> str:
    i = html.find('<div class="chapter-body">')
    if i < 0:
        return ""
    d = 0
    for m in re.finditer(r"<div\b|</div>", html[i:]):
        if m.group(0) == "<div":
            d += 1
        else:
            d -= 1
            if d == 0:
                return html[i:i + m.end()]
    return html[i:]


def check_body(body: str, label: str) -> list:
    fails = []
    vis = visible_text(body)
    text = re.sub(r"<[^>]+>", "", body)

    if body.count("——"):
        fails.append(f"破折號 {body.count('——')}")
    if body.count(","):
        fails.append(f"ASCII 逗號 {body.count(',')}")
    if text.count('"'):
        fails.append(f"ASCII 引號 {text.count(chr(34))}")

    hit = {}
    for w in CANTONESE:
        c = text.count(w)
        if c:
            hit[w] = c
    if hit:
        fails.append(f"粵語詞 {hit}")

    simp = sorted(set(text) & SIMPLIFIED)
    if simp:
        fails.append(f"簡體字 {''.join(simp)}")

    tagtotal = sum(text.count(t) for t in TAGS[:2])
    if tagtotal > 2:
        fails.append(f"標籤詞過多 {tagtotal}（魔法+兩位旅客）")
    for t in TAGS[2:]:
        if text.count(t):
            fails.append(f"禁用詞 {t}×{text.count(t)}")

    n = count_words(body)
    if not (1800 <= n <= 2600):
        fails.append(f"字數 {n} 超出 1800-2600")

    if re.search(r"第\s*\d+\s*章", text):
        fails.append("正文引用章號")
    if re.search(r"Day\s*\d+", text):
        fails.append("正文出現 Day X")
    if re.search(r"（[^）]{0,60}(角色|場景人物|冰封|非|首次)[^）]{0,60}）", text):
        fails.append("作者備註括號")

    # 鳳凰盒發光：只喺同一句/同一段出現「鳳凰盒」時才算違規
    for para in re.split(r"</p>", body):
        ptx = re.sub(r"<[^>]+>", "", para)
        if "鳳凰盒" in ptx:
            for g in GLOW_WORDS:
                if g in ptx:
                    fails.append(f"鳳凰盒發光描述「{g}」")

    if "<p>" in body:
        if body.count("<p>") != body.count("</p>"):
            fails.append(f"<p> 不平衡 {body.count('<p>')}/{body.count('</p>')}")

    return fails


def check_html(n: int) -> list:
    p = f"{BASE}/shinshu-chapter-{n:02d}.html"
    if not os.path.exists(p):
        return ["檔案不存在"]
    html = open(p, encoding="utf-8").read()
    body = chapter_body(html)
    if not body:
        return ["搵唔到 chapter-body"]
    fails = check_body(body, f"ch{n}")
    vis = visible_text(html)
    for leak in ["max-width: 720px", "location.href", "addEventListener",
                 "function (", "var PREV", "@media"]:
        if leak in vis:
            fails.append(f"CSS/JS 外露：{leak}")
    if "copyChapterBtn" not in html:
        fails.append("缺少複製按鈕")
    return fails


def check_work(n: int) -> list:
    p = f"{WORK}/ch{n:02d}_body.txt"
    if not os.path.exists(p):
        return ["檔案不存在"]
    body = open(p, encoding="utf-8").read()
    return check_body(body, f"ch{n} body")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == "--body":
        for a in args[1:]:
            f = check_work(int(a))
            print(f"章 {a} body: {'✅ PASS' if not f else '❌ ' + '; '.join(f)}")
        return
    if args[0] == "--range":
        lo, hi = int(args[1]), int(args[2])
        for n in range(lo, hi + 1):
            f = check_html(n)
            print(f"章 {n:02d}: {'✅ PASS' if not f else '❌ ' + '; '.join(f)}")
        return
    for a in args:
        f = check_html(int(a))
        print(f"章 {int(a):02d}: {'✅ PASS' if not f else '❌ ' + '; '.join(f)}")


if __name__ == "__main__":
    main()

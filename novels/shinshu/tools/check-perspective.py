#!/usr/bin/env python3
"""檢查章節敘事視角一致性（統一第一人稱「我」）"""
import re, sys, os

def body_of(p):
    t = open(p, encoding="utf-8").read()
    if p.endswith(".txt"):
        return t
    i = t.find('<div class="chapter-body">')
    j = t.find('<script', i)
    return t[i:j] if i >= 0 else t

def check(p):
    b = body_of(p)
    tx = re.sub(r'<[^>]+>', '', b)
    nwo = len(re.findall(r'我', tx))
    # 第三人稱殘留：「凜」+「她」
    kin = len(re.findall(r'凜', tx))
    # 「她」指凜的痕跡（凜出現在同句）
    she = len(re.findall(r'她', tx))
    # 直接引述模式：凜說
    kin_says = len(re.findall(r'凜[說問看寫把拿想聽點回轉停低抬握放翻坐站走]', tx))
    # 「她」+ 動詞 主語模式
    she_subject = len(re.findall(r'她[說問看寫把拿想聽點回轉停低抬握放翻坐站走]', tx))
    ok = (nwo >= 8) and kin_says == 0 and she_subject == 0
    return dict(wo=nwo, kin=kin, she=she, kin_says=kin_says, she_subj=she_subject, ok=ok)

if __name__ == "__main__":
    args = sys.argv[1:]
    mode = "body" if "--body" in args else "html"
    nums = [int(a) for a in args if a.isdigit()]
    base = "/home/kenlo/novels/_work/ch%02d_body.txt" if mode == "body" else \
           "/home/kenlo/hermes-novels/novels/shinshu/chapters/shinshu-chapter-%02d.html"
    for n in nums:
        p = base % n
        if not os.path.exists(p):
            print(f"章 {n}: 檔案不存在"); continue
        r = check(p)
        tag = "✅" if r["ok"] else "❌"
        print(f"章 {n}: {tag} 我={r['wo']:3d} 凜={r['kin']:3d} 她={r['she']:3d} "
              f"凜+動詞={r['kin_says']:3d} 她+動詞={r['she_subj']:3d}")

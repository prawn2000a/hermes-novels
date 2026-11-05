"""J5 檢查：正文出現嘅日文詞，是否全部有日文欄解釋。

用法：python3 check-j5-coverage.py
輸出：每章正文日文詞（假名詞／片假名）vs 日文欄已解釋詞嘅對照。
"""
import re
import importlib.util

CH_DIR = '/home/kenlo/hermes-novels/novels/shinshu/chapters'
spec = importlib.util.spec_from_file_location('pd', '/home/kenlo/novels/_work/preview_data.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def body(n):
    h = open(f'{CH_DIR}/shinshu-chapter-{n:02d}.html', encoding='utf-8').read()
    i = h.find('<div class="chapter-body">')
    seg = h[i:]
    d = 0
    for mm in re.finditer(r'<div\b[^>]*>|</div>', seg):
        d += -1 if mm.group(0).startswith('</div') else 1
        if d == 0:
            break
    return re.sub(r'<[^>]+>', '', seg[:mm.end()])


def norm(s):
    """去掉括號內讀音，只留字詞本身"""
    s = re.sub(r'[（(][^）)]*[）)]', '', s)
    return re.sub(r'[\s\u3000]', '', s)


total_missing = 0
for n in sorted(m.PREVIEWS):
    txt = body(n)
    # 假名詞（2字以上連續）同片假名詞
    words = set(re.findall(r'[ぁ-んァ-ヶ]{2,}', txt))
    # 漢字地名（2–6 字，用日文常見地名字尾或直接列已解釋表）
    expl = m.PREVIEWS[n]['japanese']
    expl_norm = set()
    for k, v in expl:
        base = norm(k)
        expl_norm.add(base)
        # 去掉「・」「／」等再拆
        for part in re.split(r'[・／／]', base):
            if part:
                expl_norm.add(part)
        # 括號前嘅詞
        head = re.split(r'[（(]', k)[0].strip()
        if head:
            expl_norm.add(re.sub(r'\s', '', head))
    # 章節標題可能重複，過濾常見非詞
    skip = {'こと', 'もの', 'とき', 'ところ', 'こと', 'ため', 'ながら', 'ように', 'こと', 'なら'}
    miss = []
    for w in sorted(words):
        if w in skip:
            continue
        if any(w in e or e in w for e in expl_norm if e):
            continue
        miss.append(w)
    if miss:
        total_missing += len(miss)
        print(f'章{n:02d} 未解釋: {miss}')

print(f'---')
print(f'總未解釋詞數: {total_missing}')

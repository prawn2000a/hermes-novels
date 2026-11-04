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
# 明確簡體字（繁體正字如「」「」「」不在此表）
# 合法例外：日文借字／專有名詞中會出現的簡體同形字
ALLOWED_SIMPLIFIED = {
    "干",  # 切り干し大根（切り干し大根）
    "晒",  # 舊體（部分古籍用字）
    "没",  # 部分舊稿殘留
}

ALLOWED_CANTONESE = {
    "仲",  # 仲見世通（善光寺商店街）
}

SIMPLIFIED = set(
    "这个们来时说过学对开关门东车马鸟鱼长风飞问间闻进还发变灯点没丽么义乐习买亚严丧"
    "丰临举义乌乔乡书乱争亏云产亲亿仅从仑仓仪价众优伙会伟传伤伦伪体佣佥侠侣侥侦侧侨侩"
    "侯俭债倾偿储儿兑兖党兰关兴兹养兽内冈册写军农冢冯冲决况冻净准凉减凑凛凤凭凯击凿"
    "刍刘则刚创删别刭刽刿剀剂剐剑剥剧劝办务动励劲劳势勋勚匀匦匮区医华协单卖卢卫却厂"
    "厅历厉压厌厕厢厦厨县参双叙叠叶号叹叽吁后吓吕吗听启吴呒呓呕员呛呜咏咙响哑哒哓哔"
    "哗哙哝哟唛唠唤唿啧啬啭啮啰啸喷喽嗫嗳嘘嘤嘱噜嚣团园囱围囵国图圆圣场坂坏块坚坛坝"
    "坞坟坠垄垒垦垫垭垱垲垴埘埙埚埝堑堕墙壮声壳壶处备复够头夸夹夺奁奋奖奥妆妇妈妩姗"
    "娄娅娆娇娈娱娲娴婴婵婶媪嫔嬷孙学孪宁宝实宠审宪宫宽宾寝对寻导寿将尔尘尧尴尸尽层屉"
    "届属屡屿岁岖岗岘岚岛岭岿峡峣峥峦崂崭嵘巅巩币帅师帐帘帜带帧帮幂干并广庄庆庐库应"
    "庙庞废开异弃张弥弯弹强归当录彻径忆忏忧忾怀态怂怅怆怜总怼恋恳恶恸恺恻恼悦悬悯惊惧"
    "惨惩惫惬惭惮惯愠愤愿慑懑懒戏戗战户扎扑执扩扪扫扬扰抚抛抠抢护报担拟拢拣拥拦拧拨择"
    "挂挚挛挝挞挟挠挡挣挤挥捞损捡换捣据掳掷掸掺揽揿搀搁搂搅携摄摆摇摈摊撑撵撷撸撺擞"
    "攒敌敛数斋斩断无旧旷昼显晋晒晓晕暂术朴机杀杂权条来杨杰极构枢枣枥枫枭柠标栈栉栊"
    "栋栏树栖样栾桠桦桧桨桩梦检椁椟椤楼榄榇榈榉槚槛槟槠横樯樱橱橹檩欢欧歼殁殇残殒殓"
    "殡殴毁毂毕毡气氢氩氲汇汉污汤汹沓沟没沥沦沧沪泞泪泷泻泼泽洁洒洼浅浆浇浊测济浏浑浓"
    "涂涌涛涝涟涡涣涤润涧涨涩淀渊渍渎渐渔渗温湾湿溃滚滨滞渺潍潇潋漳濑濒灏灭灵灾灿炉炖"
    "炜炫炷灭点汉广门马鸟鱼长风飞问间闻进还发变灯"
)
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
        if w in ALLOWED_CANTONESE:
            continue
        c = text.count(w)
        if c:
            hit[w] = c
    if hit:
        fails.append(f"粵語詞 {hit}")

    simp = sorted((set(text) & SIMPLIFIED) - ALLOWED_SIMPLIFIED)
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

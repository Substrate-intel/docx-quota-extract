# -*- coding: utf-8 -*-
"""
parse_desc_lvse.py —— 绿色建筑工程定额卷 目录层 + 条文层
toc：nowm.pdf 目录区（P5-9）双栏重组（x<280 左栏 / >=280 右栏，栏内 y±3 聚类）
desc_rules：md blocks 条文切片（册说明/章说明/计算规则/附表，每条一记录）
页码口径：正文印刷页 = 物理页 - 9（目录引用页码为正文印刷页）
"""
import fitz
import json
import re

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
NOWM = r"C:/Users/Administrator/Downloads/1773816825515128_nowm.pdf"
OFFSET = 9

# ============================== 一、目录层 ==============================
doc = fitz.open(NOWM)
toc_rows = []  # (seq, raw_line, page)
for pno in range(4, 9):  # P5-9
    d = doc[pno].get_text("dict")
    lines = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t and not re.fullmatch(r"[·\s\d]+", t):
                lines.append((l["bbox"][1], l["bbox"][0], t))
    # 分左右栏
    left = [(y, x, t) for y, x, t in lines if x < 280]
    right = [(y, x, t) for y, x, t in lines if x >= 280]
    for col in (left, right):
        col.sort()
        rows = []
        for y, x, t in col:
            if rows and abs(y - rows[-1][0]) <= 6.5:  # 章名与编码行 y 差~5，行距 14.7 安全
                rows[-1][1].append((x, t))
            else:
                rows.append([y, [(x, t)]])
        for y, cells in rows:
            raw = "".join(t for x, t in sorted(cells)).strip()
            if raw and not raw.startswith("目") or len(raw) > 3:
                toc_rows.append((pno + 1, raw))
doc.close()

# 行解析 → sz05 契约字段
CH_RE = re.compile(r"^第([一二三四五六七八九十]+)章\s*(.*?)\(([0-9]{6})\)\s*$")
SEC_RE = re.compile(r"^([一二三四五六七八九十]+)、")
SUB_RE = re.compile(r"^(\d+)\.\s*")
PG_RE = re.compile(r"^[.…·\s]*\((\d{1,3})\)\s*$")

records = []
seq = 0
cur_ch_no = None
cur_ch_code = None
i = 0
n_rows = len(toc_rows)
while i < n_rows:
    page, raw = toc_rows[i]
    r = raw.strip()
    # 长标题拆行：标题行以省略号结尾且无页码 → 与下一行（纯页码行）合并
    m_pg = re.match(r"^(.*?)\s*[.…·]{2,}\s*\((\d{1,3})\)\s*$", r)
    if not m_pg and i + 1 < n_rows and re.fullmatch(r"[.…·\s]+\(\d{1,3}\)\s*", toc_rows[i + 1][1]):
        nxt = toc_rows[i + 1][1]
        m2 = re.search(r"\((\d{1,3})\)", nxt)
        r2 = r + nxt
        m_pg = re.match(r"^(.*?)\s*[.…·]{2,}\s*\((\d{1,3})\)\s*$", r2)
        if m_pg:
            r = r2
            i += 1  # 吞并页码行
    # 扉页残余短行（目/录等 ≤2 字）丢弃留痕
    if len(re.sub(r"[…·\s]", "", r)) <= 2 and not re.search(r"\(\d+\)", r):
        i += 1
        continue
    title = m_pg.group(1).strip() if m_pg else r.strip()
    print_page = int(m_pg.group(2)) if m_pg else None
    raw = r
    # 章行（无页码）
    cm = CH_RE.match(raw.replace("　", " ").strip())
    if cm and print_page is None:
        cur_ch_no = "第%s章" % cm.group(1)
        cur_ch_code = cm.group(3)
        seq += 1
        records.append({"seq": seq, "id": "TOC-%04d" % seq, "level": "章行",
                        "ref_kind": "章", "chapter_code": cur_ch_code, "chapter_no": cur_ch_no,
                        "title": "%s%s(%s)" % (cur_ch_no, cm.group(2), cur_ch_code),
                        "raw_line": raw, "print_page": None,
                        "pdf_page": None, "toc_page": page})
        i += 1
        continue
    # 附录标题行（无页码）
    if print_page is None and re.fullmatch(r"附\s*录", title.replace("　", "")):
        seq += 1
        records.append({"seq": seq, "id": "TOC-%04d" % seq, "level": "附录行",
                        "ref_kind": "附录", "chapter_code": None, "chapter_no": None,
                        "title": "附录", "raw_line": raw, "print_page": None,
                        "pdf_page": None, "toc_page": page})
        i += 1
        continue
    # 无页码行且非章行 → 留痕不归类
    if print_page is None:
        seq += 1
        records.append({"seq": seq, "id": "TOC-%04d" % seq, "level": "其他行",
                        "ref_kind": "其他", "chapter_code": cur_ch_code, "chapter_no": cur_ch_no,
                        "title": title, "raw_line": raw, "print_page": None,
                        "pdf_page": None, "toc_page": page})
        i += 1
        continue
    pdf_page = print_page + OFFSET
    if "册" in title and "说" in title and len(title) <= 8:
        level, kind = "册说明行", "册说明"
    elif title.startswith("说"):
        level, kind = "说明行", "章说明"
    elif "计算规则" in title:
        level, kind = "规则行", "计算规则"
    elif title.startswith("附录") or "取定表" in title or "附表" in title:
        level, kind = "附表行", "附表"
    elif SEC_RE.match(title):
        level, kind = "节行", "节"
    elif SUB_RE.match(title):
        level, kind = "子目行", "子目"
    elif title.startswith("第") and "章" in title:
        level, kind = "章行", "章"
    else:
        level, kind = "其他行", "其他"
    seq += 1
    records.append({"seq": seq, "id": "TOC-%04d" % seq, "level": level, "ref_kind": kind,
                    "chapter_code": cur_ch_code, "chapter_no": cur_ch_no,
                    "title": title, "raw_line": raw,
                    "print_page": print_page, "pdf_page": pdf_page, "toc_page": page})
    i += 1

from collections import Counter
lv_cnt = Counter(r["level"] for r in records)
print("目录行:", len(records), dict(lv_cnt))
json.dump({"meta": {"source": "nowm.pdf 目录区 P5-9 双栏重组", "offset": OFFSET},
           "rows": records},
          open(BASE + r"\lvse_toc.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ============================== 二、条文层 ==============================
FULL = json.load(open(BASE + r"\md_extract_full.json", encoding="utf-8"))
IDX = json.load(open(BASE + r"\md_index.json", encoding="utf-8"))
blocks = FULL["blocks"]

desc_rules = []
did = 0


def add_rule(block_type, kind, ch_code, text, page, src_blks):
    global did
    did += 1
    print_page = page - OFFSET if page and page >= 10 else None
    desc_rules.append({
        "section_id": "GS-%03d" % did if block_type == "册说明" else
                      ("ZS-%03d" % did if block_type == "章说明" else
                       ("JR-%03d" % did if block_type == "计算规则" else "FB-%03d" % did)),
        "block_type": block_type, "md_kind": kind, "chapter_code": ch_code,
        "seq": did, "page": page, "print_page": print_page,
        "text": text, "src_blks": str(src_blks),
    })


# 册说明：P10 h2 标题块（目录区的「册　说　明」普通段不带 kind，防误命中）
in_gs = False
buf = []
for b in blocks:
    txt = b["text"].strip() if b["type"] == "para" else ""
    if (b["type"] == "para" and b.get("kind") == "h2"
            and re.fullmatch(r"册\s*说\s*明", txt.replace("　", "").replace(" ", ""))):
        in_gs = True
        continue
    if b["type"] == "para" and b.get("kind") == "h1":
        in_gs = False
        break
    if in_gs and txt:
        buf.append(b)

# 册说明按条切（一、二、… 条目起始；续行直拼）
def split_rules(paras, item_re):
    """段落流 → 条目列表；条目边界=编号行（一、二、…），续行一律拼入当前条
    （多句续段不因句号断开——sz05 坑㉕ 同源：条目边界只认编号头）"""
    items = []
    cur = None
    for b in paras:
        t = b["text"].strip()
        if item_re.match(t):
            if cur:
                items.append(cur)
            cur = {"text": t, "blks": [b["no"]], "page": b["page"]}
        elif cur is not None:
            cur["text"] += t
            cur["blks"].append(b["no"])
        else:
            # 无编号头的孤立段（留痕独立条）
            cur = {"text": t, "blks": [b["no"]], "page": b["page"]}
    if cur:
        items.append(cur)
    return items


GS_RE = re.compile(r"^[一二三四五六七八九十]+、")
gs_items = split_rules(buf, GS_RE)
for it in gs_items:
    add_rule("册说明", "册说明", None, it["text"], it["page"], it["blks"])
print("册说明条目:", len(gs_items))

# 章区：## 说明 / ## 工程量计算规则（md h2 块，chapter 归属）
cur_ch = None
cur_zone = None  # None / '说明' / '规则'
zone_buf = []
for b in blocks:
    if b["type"] == "para" and b.get("kind") == "h2":
        t = b["text"].replace("　", "").replace(" ", "")
        # 先结算上一个区
        if cur_zone and zone_buf:
            zone_items = split_rules(zone_buf, GS_RE)
            for it in zone_items:
                add_rule("章说明" if cur_zone == "说明" else "计算规则",
                         cur_zone, cur_ch, it["text"], it["page"], it["blks"])
        if t.startswith("说明") or t == "说明":
            cur_zone, zone_buf = "说明", []
        elif "计算规则" in t:
            cur_zone, zone_buf = "计算规则", []
        else:
            cur_zone, zone_buf = None, []
        continue
    if b["type"] == "para" and b.get("kind") == "h1":
        if cur_zone and zone_buf:
            zone_items = split_rules(zone_buf, GS_RE)
            for it in zone_items:
                add_rule("章说明" if cur_zone == "说明" else "计算规则",
                         cur_zone, cur_ch, it["text"], it["page"], it["blks"])
        cur_ch = b["chapter_code"]
        cur_zone, zone_buf = None, []
        continue
    if cur_zone and b["type"] == "para" and b["text"].strip():
        zone_buf.append(b)
    elif cur_zone and b["type"] == "table":
        # 表=子目区开始，结算说明/规则区
        zone_items = split_rules(zone_buf, GS_RE)
        for it in zone_items:
            add_rule("章说明" if cur_zone == "说明" else "计算规则",
                     cur_zone, cur_ch, it["text"], it["page"], it["blks"])
        cur_zone, zone_buf = None, []
# 尾部结算
if cur_zone and zone_buf:
    zone_items = split_rules(zone_buf, GS_RE)
    for it in zone_items:
        add_rule("章说明" if cur_zone == "说明" else "计算规则",
                 cur_zone, cur_ch, it["text"], it["page"], it["blks"])

# 附表：附录区材料预算价格取定表（13 表块拍平一条）
fb_blks = []
fb_title_page = None
for b in blocks:
    if b["type"] == "table" and b.get("ttype") == "附表":
        fb_blks.append(b)
    if b["type"] == "para" and "材料预算价格取定表" in b["text"]:
        fb_title_page = b["page"]
if fb_blks:
    cells = []
    for b in fb_blks:
        for r in b["rows"]:
            cells.append("｜".join(c for c in r if c))
    add_rule("附表", "附表", None, "材料预算价格取定表（附录）：" + " ⁃ ".join(cells),
             fb_title_page or fb_blks[0]["page"], [b["no"] for b in fb_blks])

bt_cnt = Counter(r["block_type"] for r in desc_rules)
print("条文层:", len(desc_rules), dict(bt_cnt))
json.dump({"meta": {"source": "md_extract_full.json 条文切片",
                    "n": len(desc_rules)},
           "rules": desc_rules},
          open(BASE + r"\lvse_desc_rules.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("written lvse_toc.json / lvse_desc_rules.json")

# -*- coding: utf-8 -*-
"""
extract_md.py —— 绿色建筑工程定额卷（辽宁2024）保真层
md 源（由 nowm.pdf 确定性生成，convert_greenbuilding.py）→ blocks JSON

对标 docx 版 docx_extract_full.json / docx_index.json 契约：
- blocks: para/table 全量按文档序，零语义过滤
- tables: no/page/chapter/type(子目表|附表|其他)/cont(续前)/rows
确定性：无运行时时间戳；meta 锚定 nowm.pdf sha12 + 官方原版 wm sha12 + convert 脚本 sha12

页码口径（本卷定版）：
- 正文/附录 P10-269: 印刷页 = 物理页 - 9
- 目录区 P6-9: 印刷页 = 物理页 - 5
- P1-5 及章扉页对(12/13,66/67,206/207,226/227,256/257) 无印刷页码
"""
import hashlib
import json
import re

MD = r"C:/Users/Administrator/WorkBuddy/sp/out_md/绿色建筑工程定额_辽宁2024_1773816825515128.md"
NOWM = r"C:/Users/Administrator/Downloads/1773816825515128_nowm.pdf"
WM = r"C:/Users/Administrator/Downloads/1773816825515128.pdf"       # 官方原版（校对源）
CONVERT = r"C:/Users/Administrator/WorkBuddy/sp/out_md/convert_greenbuilding.py"
OUT_DIR = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"

CODE_RE = re.compile(r"^20-\d{1,3}$")          # 定额编号
CH_RE = re.compile(r"^#\s+第([一二三四五六七八九十]+)章\s+(.+?)\s*\((\d{6})\)\s*$")
PAGE_RE = re.compile(r"^<!--\s*P(\d+)\s*-->$")


def sha12(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def parse_table_row(line):
    """'| a | b |' -> ['a','b']（去首尾空管段）"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def split_md_table_rows(rows):
    """去表头分隔行 |---|---|"""
    out = []
    for r in rows:
        if all(re.fullmatch(r":?-{2,}:?", c) for c in r if c != "") and any("-" in c for c in r):
            continue
        out.append(r)
    return out


lines = open(MD, encoding="utf-8").read().splitlines()

blocks = []          # {no,type,page,text|rows,chapter_code}
cur_page = 0
cur_chapter_code = None
cur_chapter_no = None
chapters = []        # {no,code,title,page}
tbl_no = 0
i = 0
n = len(lines)

while i < n:
    line = lines[i]
    m = PAGE_RE.match(line.strip())
    if m:
        cur_page = int(m.group(1))
        i += 1
        continue
    cm = CH_RE.match(line)
    if cm:
        cur_chapter_no = "第%s章" % cm.group(1)
        cur_chapter_code = cm.group(3)
        chapters.append({"no": cur_chapter_no, "code": cur_chapter_code,
                         "title": cm.group(2), "page": cur_page})
        blocks.append({"no": len(blocks), "type": "para", "page": cur_page,
                       "text": line[2:].strip(), "chapter_code": cur_chapter_code,
                       "kind": "h1"})
        i += 1
        continue
    if line.startswith("## "):
        blocks.append({"no": len(blocks), "type": "para", "page": cur_page,
                       "text": line[3:].strip(), "chapter_code": cur_chapter_code,
                       "kind": "h2"})
        i += 1
        continue
    if line.startswith("|"):
        # 聚连续表格行
        raw = []
        while i < n and lines[i].startswith("|"):
            raw.append(parse_table_row(lines[i]))
            i += 1
        rows = split_md_table_rows(raw)
        if not rows:
            continue
        tbl_no += 1
        # 表类型：含定额编号行 → 子目表；附录材料价格表 → 附表；否则 其他
        flat = [re.sub(r"\s+", "", c) for r in rows for c in r]
        has_code = any(CODE_RE.match(c) for c in flat)
        joined_head = "".join(flat[:40])
        if has_code:
            ttype = "子目表"
        elif "材料名称" in joined_head or "材料预算价格" in joined_head:
            ttype = "附表"
        else:
            ttype = "其他"
        # 续前判定：上方最近 para 文本 == 续前
        cont = False
        for b in reversed(blocks):
            if b["type"] == "para":
                cont = (b["text"].strip() == "续前")
                break
        blocks.append({"no": len(blocks), "type": "table", "page": cur_page,
                       "tbl_no": tbl_no, "rows": rows, "chapter_code": cur_chapter_code,
                       "ttype": ttype, "cont": cont})
        continue
    t = line.strip()
    if t:
        blocks.append({"no": len(blocks), "type": "para", "page": cur_page,
                       "text": t, "chapter_code": cur_chapter_code})
    i += 1

n_para = sum(1 for b in blocks if b["type"] == "para")
n_table = sum(1 for b in blocks if b["type"] == "table")
tables = [{"no": b["tbl_no"], "blk": b["no"], "page": b["page"],
           "chapter": b["chapter_code"], "type": b["ttype"], "cont": b["cont"],
           "n_rows": len(b["rows"])}
          for b in blocks if b["type"] == "table"]

meta = {
    "source": "绿色建筑工程定额_辽宁2024 md（nowm.pdf 确定性生成）",
    "md_sha12": sha12(MD),
    "nowm_pdf_sha12": sha12(NOWM),
    "wm_pdf_sha12": sha12(WM),
    "convert_script_sha12": sha12(CONVERT),
    "pages": 269,
    "page_offset": {"main": 9, "toc": 5},
    "no_page_print": [1, 2, 3, 4, 5, 12, 13, 66, 67, 206, 207, 226, 227, 256, 257],
    "n_blocks": len(blocks), "n_para": n_para, "n_table": n_table,
}
full = {"meta": meta, "blocks": blocks}
index = {"meta": meta, "chapters": chapters, "tables": tables}

import os
os.makedirs(OUT_DIR, exist_ok=True)
json.dump(full, open(OUT_DIR + r"\md_extract_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(index, open(OUT_DIR + r"\md_index.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

from collections import Counter
tc = Counter(t["type"] for t in tables)
cc = Counter(t["cont"] for t in tables)
print("blocks:", len(blocks), "para:", n_para, "table:", n_table)
print("表类型分布:", dict(tc), "| 续前表:", cc.get(True, 0))
print("章:", [(c["no"], c["code"], c["page"]) for c in chapters])
print("written md_extract_full.json / md_index.json")

# -*- coding: utf-8 -*-
"""只读提取 docx：段落(带样式) + 表格 + 统计画像。原始文件只读。"""
import json, sys, zipfile
from docx import Document
from docx.document import Document as _Doc
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

SRC = r"C:/Users/Administrator/Downloads/1773818587204558_nowm.docx"
OUT = r"C:/Users/Administrator/WorkBuddy/sp/out_organize/extracted_full.json"

def iter_block_items(parent):
    parent_elm = parent.element.body
    for child in parent_elm.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)

doc = Document(SRC)
blocks = []
tbl_i = 0
for blk in iter_block_items(doc):
    if isinstance(blk, Paragraph):
        t = blk.text.strip()
        if t:
            blocks.append({"type":"para","style":blk.style.name if blk.style else "", "text":t})
    else:
        tbl_i += 1
        rows = []
        for r in blk.rows:
            cells = [c.text.strip().replace("\n"," / ") for c in r.cells]
            rows.append(cells)
        blocks.append({"type":"table","table_no":tbl_i,"n_rows":len(rows),
                       "n_cols":len(rows[0]) if rows else 0,"rows":rows})

# 图片统计
with zipfile.ZipFile(SRC) as z:
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    props = z.getinfo("docProps/core.xml") if "docProps/core.xml" in z.namelist() else None
    core = z.read("docProps/core.xml").decode("utf-8", "ignore") if props else ""

# 分节标题结构
heads = [b for b in blocks if b["type"]=="para" and b["style"].lower().startswith(("heading","标题"))]

data = {
    "source_file": SRC,
    "source_size_bytes": 4671948,
    "n_blocks": len(blocks),
    "n_paras": sum(1 for b in blocks if b["type"]=="para"),
    "n_tables": tbl_i,
    "n_images": len(media),
    "media_names": media[:50],
    "core_props": core[:2000],
    "headings": [{"style":h["style"],"text":h["text"]} for h in heads],
    "blocks": blocks,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

print("paras:", data["n_paras"], "tables:", data["n_tables"], "images:", data["n_images"])
print("--- headings ---")
for h in data["headings"][:80]:
    print(h["style"], "|", h["text"][:60])

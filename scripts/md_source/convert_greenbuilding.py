# -*- coding: utf-8 -*-
"""
绿色建筑工程定额（辽宁2024）PDF -> Markdown（裸 fitz 链）
- 页眉/页码行剥离
- 19.7pt 黑体连续行 -> # 章标题；13.7pt 黑体短行 -> ## 节标题
- 10.3pt 宋体 -> 正文段落
- 有框线表格 -> find_tables() 转 Markdown 表格，按 y 序插入
"""
import fitz  # noqa
import re
import sys
import time

SRC = r"C:/Users/Administrator/Downloads/1773816825515128_nowm.pdf"  # 无水印干净源
DST = r"C:/Users/Administrator/WorkBuddy/sp/out_md/绿色建筑工程定额_辽宁2024_1773816825515128.md"

HEADER_TEXT = "2024年《辽宁省建设工程计价依据》"
PAGE_NO_RE = re.compile(r"^[\s·•．.]*\d{1,3}[\s·•．.]*$")
DOTS_RE = re.compile(r"^[\s·•．.]+$")  # 孤儿页码点线
# 侧边旋转水印"2024年《辽宁省建设工程计价依据》"的单字会作为前缀混入表格单元格；
# 仅剔行首孤立水印 token（污染形态=首字符），行中的"基 价 (元)"等正字不受影响
WM_CHARS = "年辽宁省建设工程计价依据《》"
WM_TOKEN_RE = re.compile(r"^([" + WM_CHARS + r"])\s")

def clean_cell(s):
    s = WM_TOKEN_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

doc = fitz.open(SRC)
out = []

def line_text(line):
    return "".join(s["text"] for s in line["spans"])

def line_size(line):
    sizes = [s["size"] for s in line["spans"] if s["text"].strip()]
    return max(sizes) if sizes else 0.0

def in_bbox(x0, y0, x1, y1, boxes):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for bx0, by0, bx1, by1 in boxes:
        if bx0 <= cx <= bx1 and by0 <= cy <= by1:
            return True
    return False

t0 = time.time()
pending_h1 = []          # 连续 19.7pt 行合并成一个章标题

def flush_h1():
    global pending_h1
    if pending_h1:
        title = " ".join(pending_h1).strip()
        title = re.sub(r"\s+", " ", title)
        out.append(f"# {title}\n")
        pending_h1 = []

for pno in range(doc.page_count):
    page = doc[pno]
    d = page.get_text("dict")

    # ---- 收集非表区文本行 ----
    # 表区 bbox
    tables = []
    try:
        tf = page.find_tables()
        for t in tf.tables:
            tables.append(t)
    except Exception:
        tables = []
    tboxes = [tuple(t.bbox) for t in tables]

    text_items = []  # (y0, x0, kind, payload)
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            txt = line_text(l).strip()
            if not txt:
                continue
            x0, y0, x1, y1 = l["bbox"]
            if in_bbox(x0, y0, x1, y1, tboxes):
                continue
            # 页眉
            if txt == HEADER_TEXT or HEADER_TEXT in txt.replace(" ", ""):
                continue
            # 页码行（纯数字/间隔符）
            if PAGE_NO_RE.match(txt) or DOTS_RE.match(txt):
                continue
            text_items.append((y0, x0, l, txt))

    # 若本页无表格且无文本，跳过
    if not text_items and not tables:
        continue

    out.append(f"\n<!-- P{pno + 1} -->\n")

    # ---- 按 y 排序输出：文本块与表格交错 ----
    elems = [("text", y0, x0, l, txt) for (y0, x0, l, txt) in text_items]
    elems += [("table", t.bbox[1], t.bbox[0], t, None) for t in tables]
    elems.sort(key=lambda e: (e[1], e[2]))

    for kind, y0, x0, obj, txt in elems:
        if kind == "table":
            flush_h1()
            try:
                rows = obj.extract()
            except Exception:
                continue
            if not rows:
                continue
            # 清洗单元格
            clean = []
            for r in rows:
                clean.append([clean_cell(c or "") for c in r])
            ncol = max(len(r) for r in clean)
            for r in clean:
                while len(r) < ncol:
                    r.append("")
            out.append("")
            out.append("| " + " | ".join(clean[0]) + " |")
            out.append("|" + "---|" * ncol)
            for r in clean[1:]:
                out.append("| " + " | ".join(r) + " |")
            out.append("")
            continue

        line, txt = obj, txt
        size = line_size(line)
        if size >= 15.0:
            # 章标题行（19.7pt），累积合并
            pending_h1.append(txt)
            continue
        if 12.0 <= size < 15.0:
            flush_h1()
            title = re.sub(r"\s+", "", txt)
            if len(title) <= 12:  # 黑体短标题：说明/册说明/附录等
                out.append(f"\n## {title}\n")
                continue
        # 正文
        flush_h1()
        out.append(txt)

    # 页末收口
    flush_h1()

doc.close()
flush_h1()

md = "\n".join(out)
md = re.sub(r"\n{3,}", "\n\n", md)
# E-BZ 排版残留：小数点后多余空格归一（"1228. 26"->"1228.26"）；
# 不动 "1. 屋面" 类序号（点后非数字不受影响）
md = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", md)
with open(DST, "w", encoding="utf-8") as f:
    f.write(md)

print(f"OK chars={len(md)} secs={time.time()-t0:.1f}")

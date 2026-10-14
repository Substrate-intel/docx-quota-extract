# -*- coding: utf-8 -*-
r"""docx 说明/规则/目录 每条一记录提取器（根治版，2026-10-14）
产物：docx_source/docx_desc_rules_raw.json（docx 视角中间产物） + docx_source/docx_toc.json
后继：align_desc.py 消费 raw 产对齐版 docx_desc_rules.json（PDF 版同构每条一记录）

根治两缺陷：
1. 目录层丢失根因：整卷目录在 docx 中包于 w:sdt 内容控件，python-docx 块级迭代
   （body 直接子元素）完全跳过 → 本脚本直接解析 document.xml 段落流（含 sdt）。
2. 章节说明/计算规则只有单段文本、内嵌系数表丢失、rules 列表尾部混入节标题
   （docx_index ch1 rules 41 条中 22 条是节标题）→ 按「条」切分 + 续行合并 +
   子项/单位/表题特判 + 内嵌表拍平，rules 区域止于首节标题。

合并规则（para 序列，非条首时）：
  1. ^\d+\s*[.．、] → 换行（子项；'0. 042m3' 十进制续行按换行入条，语义不丢）
  2. ^单位\s*[:：] → 换行（表单位行）
  3. 前段末无终结符（。；;：:！？）→ 直拼（排版折行续行）
  4. 其余 → 换行
表格 → 换行拍平为文本 + 结构化留痕 tables 字段。
确定性：无运行时时间戳，锚定 source sha12。"""
import json, re, zipfile, hashlib, sys

SRC = r"C:/Users/Administrator/Downloads/1773818587204558_nowm.docx"
DST = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/docx_source"
EXT = r"C:/Users/Administrator/WorkBuddy/sp/out_organize/extracted_full.json"

sha12 = hashlib.sha256(open(SRC, "rb").read()).hexdigest()[:12]
assert sha12 == "6008b61e81de", "source sha 变更，须复核全链"
blocks = json.load(open(EXT, encoding="utf-8"))["blocks"]
idx = json.load(open(DST + r"\docx_index.json", encoding="utf-8"))

# ============================================================
# Part A —— 目录（document.xml 段落流，穿透 w:sdt）
# ============================================================
with zipfile.ZipFile(SRC) as z:
    xml = z.read("word/document.xml").decode("utf-8")

paras_xml = []
for m in re.finditer(r"<w:p\b[^>]*>.*?</w:p>", xml, re.S):
    ts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", m.group(0), re.S)
    paras_xml.append("".join(ts).strip())

i_toc = next(i for i, t in enumerate(paras_xml) if re.fullmatch(r"目\s*录", t))
i_end = next(i for i in range(i_toc + 1, len(paras_xml))
             if re.fullmatch(r"册\s*说\s*明", paras_xml[i]))
toc_lines = [t for t in paras_xml[i_toc + 1:i_end] if t]

def _norm_title(s):
    return re.sub(r"\s+", "", s)

toc_records = []
seq = 0
cur_code, cur_no, cur_title = None, None, None
toc_sm, toc_rule = {}, {}
for raw in toc_lines:
    line = re.sub(r"\s+", " ", raw).strip()
    m_pg = re.search(r"\(\s*(\d{1,4})\s*\)\s*$", line)
    pg = int(m_pg.group(1)) if m_pg else None
    title_raw = line[:m_pg.start()].strip() if m_pg else line
    title = _norm_title(title_raw)
    if re.match(r"^第[一二三四五六七八九十]+章", title_raw):
        mc = re.search(r"0405\d{2}", title_raw)
        cur_code = mc.group(0) if mc else None
        cur_no = re.match(r"^(第[一二三四五六七八九十]+章)", title_raw).group(1)
        cur_title = title
        kind, level = "章", "章行"
    elif re.match(r"^册\s*说\s*明", title_raw):
        kind, level = "册说明", "册说明行"
    elif re.match(r"^说\s*明\s*$", title_raw):
        kind, level = "章说明", "说明行"
        if cur_code: toc_sm[cur_code] = pg
    elif re.match(r"^工程量计算规则", title_raw):
        kind, level = "计算规则", "规则行"
        if cur_code: toc_rule[cur_code] = pg
    elif re.match(r"^[一二三四五六七八九十]+\s*、", title_raw):
        kind, level = "节", "节行"
    elif re.match(r"^\d+\s*[.．]", title_raw):
        kind, level = "子目", "子目行"
    elif re.match(r"^附\s*录", title_raw):
        kind, level = "附录", "附录行"
        cur_code, cur_no = None, None  # 附录区脱离章上下文
    else:
        kind, level = "附录条目", "附录条目行"
    title = re.sub(r"[…\.\s]+$", "", title)
    seq += 1
    toc_records.append({
        "id": "TOC-%04d" % seq, "seq": seq, "level": level, "ref_kind": kind,
        "chapter_code": cur_code, "chapter_no": cur_no,
        "title": title, "raw_line": raw,
        "print_page": pg, "ref_print_page": pg,
        "ref_physical_page": (pg + 15) if pg else None,  # sz05 口径：P16 起恒定偏移 15
        "toc_page": None,
    })

# 孤儿页码行回填：源 docx 个别目录项标题与页码拆成两段（如 5.套环柔性接口 / (214)）
merged = []
for t in toc_records:
    if re.fullmatch(r"\(\s*\d{1,4}\s*\)", t["raw_line"]) and merged \
       and merged[-1]["print_page"] is None and merged[-1]["level"] in (
           "子目行", "节行", "说明行", "规则行", "册说明行", "附录条目行"):
        p = merged[-1]
        p["print_page"] = p["ref_print_page"] = t["print_page"]
        p["ref_physical_page"] = (t["print_page"] + 15) if t["print_page"] else None
        p["raw_line"] = p["raw_line"] + " " + t["raw_line"]
        continue
    merged.append(t)
toc_records = merged
for i, t in enumerate(toc_records, 1):
    t["seq"] = i
    t["id"] = "TOC-%04d" % i

# ============================================================
# Part B —— 说明/规则 每条一记录
# ============================================================
TERMINAL = ("。", "；", ";", "：", ":", "！", "？")
CH_NUM = "一二三四五六七八九十"
CLAUSE_RE = re.compile(r"^[" + CH_NUM + r"]{1,3}、")
CLAUSE_NO_RE = re.compile(r"^([" + CH_NUM + r"]{1,3})、")
SUB_RE = re.compile(r"^\d+\s*[.．、]")
UNIT_RE = re.compile(r"^单位\s*[:：]")

def flatten_table(b):
    rows = b.get("rows") or []
    flat = "；".join(" | ".join(c for c in r) for r in rows)
    return {"table_no": b["table_no"], "n_rows": b["n_rows"], "n_cols": b["n_cols"],
            "header": rows[0] if rows else [], "rows": rows, "flat": flat}

def clause_records(start, end, doc_type, code, ch_title, id_prefix):
    """扫描 [start,end) 段落流，按「条」聚合；返回 records + 未归属段取证"""
    recs, cur, leftovers = [], None, []
    for i in range(start, end):
        b = blocks[i]
        if b["type"] == "table":
            if cur is None:
                leftovers.append(("table", i)); continue
            t = flatten_table(b)
            cur["tables"].append(t)
            cur["blks"].append(i)
            cur["pieces"].append("\n〔内嵌表 %d：%s〕%s" % (t["table_no"], " | ".join(t["header"]), t["flat"]))
            continue
        txt = (b.get("text") or "").strip()
        if not txt:
            continue
        if CLAUSE_RE.match(txt):
            if cur: recs.append(cur)
            mno = CLAUSE_NO_RE.match(txt).group(1)
            cur = {"id": "%s-%02d" % (id_prefix, len(recs) + 1), "doc_type": doc_type,
                   "chapter_code": code, "chapter_title": ch_title,
                   "clause_no": mno, "clause_seq": len(recs) + 1,
                   "pieces": [txt], "blks": [i], "tables": []}
        elif cur is None:
            leftovers.append(("para", i, txt[:50]))
        else:
            prev = cur["pieces"][-1]
            if SUB_RE.match(txt) or UNIT_RE.match(txt):
                cur["pieces"].append("\n" + txt)
            elif prev.rstrip().endswith(TERMINAL):
                cur["pieces"].append("\n" + txt)
            elif re.search(r"[A-Za-z0-9%)）]$", prev.rstrip()):
                # 前段以 ASCII 字母/数字/右括号收尾（MPa、系数、规格等完整词元）
                # → 档位并列行，非折行续行
                cur["pieces"].append("\n" + txt)
            else:
                cur["pieces"].append(txt)  # 折行续行直拼
            cur["blks"].append(i)
    if cur: recs.append(cur)
    out = []
    for r in recs:
        text = "".join(r["pieces"])
        out.append({"id": r["id"], "doc_type": r["doc_type"], "chapter_code": r["chapter_code"],
                    "chapter_title": r["chapter_title"], "clause_no": r["clause_no"],
                    "clause_seq": r["clause_seq"], "text": text,
                    "blks": r["blks"], "n_tables": len(r["tables"]),
                    "tables": r["tables"] if r["tables"] else None})
    return out, leftovers

records = []
loose = []
# 总说明（27..54）与 册说明（58..104）：边界取自 docx_index.front
front = {f["id"]: f for f in idx["front"]}
gs_rec, gs_loose = clause_records(front["gs"]["start"], front["gs"]["end"], "总说明", None, None, "GS")
cs_rec, cs_loose = clause_records(front["cs"]["start"], front["cs"]["end"], "册说明", None, None, "CS")
records += gs_rec + cs_rec
loose += gs_loose + cs_loose

# 各章：说明区（章锚点→工程量计算规则标题）+ 规则区（标题→首节标题）
ch_starts = [c["anchor_blk"] for c in idx["chapters"]]
for ci, c in enumerate(idx["chapters"]):
    a = c["anchor_blk"]
    end_ch = ch_starts[ci + 1] if ci + 1 < len(ch_starts) else len(blocks)
    rule_at = next((i for i in range(a, end_ch) if blocks[i]["type"] == "para"
                    and re.sub(r"\s+", "", blocks[i]["text"]) == "工程量计算规则"), None)
    sec0 = c["sections"][0]["blk"] if c["sections"] else end_ch
    ch_title = re.sub(r"\s+", " ", c["title"])
    n_rec, n_loose = clause_records(a + 1, rule_at, "章节说明", c["code"], ch_title, c["code"] + "-N")
    r_rec, r_loose = clause_records(rule_at + 1, sec0, "计算规则", c["code"], ch_title, c["code"] + "-R")
    assert rule_at is not None and rule_at + 1 <= sec0, (c["code"], rule_at, sec0)
    records += n_rec + r_rec
    loose += n_loose

# ============================================================
# 落盘 + 自检
# ============================================================
meta_common = {"source_file": "1773818587204558_nowm.docx", "source_sha256_12": sha12,
               "extracted_at": "2026-10-14",
               "extract_tool": "python-docx 1.2.0 + document.xml 段落流（目录穿透 w:sdt）"}

json.dump({"meta": {**meta_common,
                   "n_records": len(records),
                   "doc_type_counts": {t: sum(1 for r in records if r["doc_type"] == t)
                                       for t in ["总说明", "册说明", "章节说明", "计算规则"]},
                   "n_records_with_table": sum(1 for r in records if r["tables"]),
                   "unassigned_blocks": [{"blk": x[1], "kind": x[0], "head": x[2]}
                                         if x[0] == "para" else {"blk": x[1], "kind": x[0]} for x in loose],
                   "note": "每条说明/规则一条记录：续行直拼、子项/单位行换行、内嵌表拍平留痕；"
                           "rules 区域止于首节标题（修复 docx_index 混入节标题缺陷）。"
                           "本文件为 docx 视角中间产物——终版 docx_desc_rules.json 由 align_desc.py 按 PDF 版对齐产出"},
          "records": records},
          open(DST + r"\docx_desc_rules_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

json.dump({"meta": {**meta_common,
                   "n_lines": len(toc_records),
                   "toc_pages_pdf": [10, 15], "page_offset": 15,
                   "toc_ref_sm": toc_sm, "toc_ref_rule": toc_rule,
                   "n_chapter_lines": sum(1 for t in toc_records if t["level"] == "章行"),
                   "note": "docx 目录原包于 w:sdt 内容控件，块级提取器整体跳过（仅余附录2行）；"
                           "本卷直接解析 document.xml 段落流全量恢复。物理页=印刷页+15（sz05 口径）"},
          "records": toc_records},
          open(DST + r"\docx_toc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 自检输出 ----------
from collections import Counter
cnt = Counter(r["doc_type"] for r in records)
print("desc_rules 记录数:", len(records), dict(cnt))
per_ch = {}
for c in idx["chapters"]:
    per_ch[c["code"]] = (sum(1 for r in records if r["doc_type"] == "章节说明" and r["chapter_code"] == c["code"]),
                         sum(1 for r in records if r["doc_type"] == "计算规则" and r["chapter_code"] == c["code"]))
print("每章(说明,规则):", per_ch, "  预期: 说明(21,19,3,10) 规则(19,8,4,8)")
print("未归属块:", len(loose), [x[1] for x in loose][:20])
print("内嵌表记录:", sum(1 for r in records if r["tables"]))
# 续行直拼点抽查（前段末无终结符）
joins = []
for r in records:
    for a, b in zip(r["blks"], r["blks"][1:]):
        pass
bad_end = [r["id"] for r in records if not r["text"].rstrip().endswith(TERMINAL + ("）", ")", "表", ":", "："))]
print("结尾无终结符记录:", len(bad_end), bad_end[:10])
# 目录对账
lv = Counter(t["level"] for t in toc_records)
print("toc 行数:", len(toc_records), dict(lv))
for c in idx["chapters"]:
    n_sec = sum(1 for t in toc_records if t["level"] == "节行" and t["chapter_code"] == c["code"])
    n_sub = sum(1 for t in toc_records if t["level"] == "子目行" and t["chapter_code"] == c["code"])
    idx_sec = len(c["sections"]); idx_sub = sum(len(s["subs"]) for s in c["sections"])
    flag = "✅" if (n_sec, n_sub) == (idx_sec, idx_sub) else "❌"
    print(f"  {flag} {c['code']} 目录节行 {n_sec} vs index {idx_sec} · 子目行 {n_sub} vs index {idx_sub}")
print("toc_ref_sm:", toc_sm, "toc_ref_rule:", toc_rule)

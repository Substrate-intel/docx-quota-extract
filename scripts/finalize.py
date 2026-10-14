# -*- coding: utf-8 -*-
"""docx 子目落库 SQLite（镜像辽宁定额库 schema）+ 重建带子目视图的前端"""
import json, sqlite3, os

DST = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05\docx_source"
out = json.load(open(DST + r"\docx_items.json", encoding="utf-8"))
rep = json.load(open(DST + r"\cost_check_report.json", encoding="utf-8"))
idx = json.load(open(DST + r"\docx_index.json", encoding="utf-8"))
full = json.load(open(DST + r"\docx_extract_full.json", encoding="utf-8"))

# ---------- 1) SQLite 落库 ----------
DB = DST + r"\docx_quota.db"
if os.path.exists(DB): os.remove(DB)
con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE book_meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE items(
  item_code TEXT PRIMARY KEY, chapter_code TEXT, list_code TEXT, name TEXT,
  unit TEXT, base_price REAL, labor_fee REAL, material_fee REAL, machine_fee REAL,
  combined_fee REAL, work_content TEXT, src_tbl INTEGER, src_col INTEGER);
CREATE TABLE item_labors(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE item_materials(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE item_machines(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE check_summary(id INTEGER PRIMARY KEY, check_id TEXT, pass_n INTEGER, fail_n INTEGER, skip_n INTEGER);
CREATE TABLE toc(seq INTEGER PRIMARY KEY, id TEXT, level TEXT, ref_kind TEXT, chapter_code TEXT,
  chapter_no TEXT, title TEXT, raw_line TEXT, print_page INTEGER, pdf_page INTEGER);
CREATE TABLE desc_rules(section_id TEXT PRIMARY KEY, block_type TEXT, docx_kind TEXT,
  chapter_code TEXT, seq INTEGER, page INTEGER, print_page TEXT,
  text TEXT, text_docx_raw TEXT, docx_src_id TEXT, docx_src_blks TEXT, align_status TEXT);
CREATE TABLE desc_docx_extra(docx_src_id TEXT, group_name TEXT, residual_text TEXT,
  residual_len INTEGER, n_tables INTEGER, blks TEXT);
""")
m = out["meta"]
for k, v in {"source_file": "1773818587204558_nowm.docx", "source_sha256_12": "6008b61e81de",
             "volume": "市政工程定额 第五册 市政管网工程 (0405)", "n_items": m["n_items"],
             "built_at": "2026-10-14", "pipeline": "docx 提取 → 子目解析 → 造价逻辑核验 H1-H6 + P1"}.items():
    cur.execute("insert into book_meta values(?,?)", (k, str(v)))
for r in out["items"]:
    cur.execute("insert into items values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r["item_code"], r["chapter"], r["list_code"], r["name"], r["unit"],
         r["base_price"], r["labor_fee"], r["material_fee"], r["machine_fee"], r["combined_fee"],
         r["work"], r["src"]["tbl"], r["src"]["col"]))
    for tab, key in (("item_labors","labors"),("item_materials","materials"),("item_machines","machines")):
        for i, x in enumerate(r[key], 1):
            cur.execute(f"insert into {tab} values(?,?,?,?,?,?)",
                (r["item_code"], i, x["name"], x["unit"], x.get("qty"), 1 if x.get("unpriced") else 0))
for cid, d in (("H1", rep["summary"]["H1"]), ("H2", rep["summary"]["H2"]), ("H3", rep["summary"]["H3"]),
               ("H4", rep["summary"]["H4"]), ("P1", rep["summary"]["P1"])):
    cur.execute("insert into check_summary(check_id,pass_n,fail_n,skip_n) values(?,?,?,?)",
                (cid, d["pass"], d["fail"], d["skip"]))

# 目录 + 说明/规则对齐版（PDF 版同构每条一记录，2026-10-14 按用户要求向 PDF 版对齐）
toc = json.load(open(DST + r"\docx_toc.json", encoding="utf-8"))["records"]
desc = json.load(open(DST + r"\docx_desc_rules.json", encoding="utf-8"))
dlog = json.load(open(DST + r"\desc_align_log.json", encoding="utf-8"))
for t in toc:
    cur.execute("insert into toc values(?,?,?,?,?,?,?,?,?,?)",
                (t["seq"], t["id"], t["level"], t["ref_kind"], t["chapter_code"], t["chapter_no"],
                 t["title"], t["raw_line"], t["print_page"], t["ref_physical_page"]))
for r in desc["records"]:
    cur.execute("insert into desc_rules values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["section_id"], r["block_type"], r["docx_kind"], r["chapter_code"],
                 r["seq"], r["page"], r["print_page"], r["text"], r["text_docx_raw"],
                 r["docx_src_id"] if isinstance(r["docx_src_id"], str) else json.dumps(r["docx_src_id"]),
                 json.dumps(r.get("docx_src_blks", [])), r["align_status"]))
for e in dlog["docx_extra"]:
    cur.execute("insert into desc_docx_extra values(?,?,?,?,?,?)",
                (e["docx_src_id"], e["group"], e["residual_text"], e["residual_len"],
                 e["n_tables"], json.dumps(e.get("blks", []))))
con.commit()
print("db rows: items", cur.execute("select count(*) from items").fetchone()[0],
      "| labors", cur.execute("select count(*) from item_labors").fetchone()[0],
      "| materials", cur.execute("select count(*) from item_materials").fetchone()[0],
      "| machines", cur.execute("select count(*) from item_machines").fetchone()[0],
      "| toc", cur.execute("select count(*) from toc").fetchone()[0],
      "| desc_rules", cur.execute("select count(*) from desc_rules").fetchone()[0],
      "| desc_docx_extra", cur.execute("select count(*) from desc_docx_extra").fetchone()[0])
con.close()

# ---------- 2) 前端数据 ----------
blocks = full["blocks"]
fronts = []
for f in idx["front"]:
    paras = [b["text"] for b in blocks[f["start"]:f["end"]] if b["type"] == "para" and b["text"].strip()]
    fronts.append({"id": f["id"], "title": f["title"], "paras": paras})

chapters = []
for ch in idx["chapters"]:
    chapters.append({"code": ch["code"], "title": ch["title"], "notes": ch["notes"], "rules": ch["rules"],
                     "sections": [{"title": s["title"], "blk": s["blk"], "subs": s["subs"],
                                   "tnos": s["tables"]} for s in ch["sections"]]})
appendix = {"材料价格": [t["no"] for t in idx["tables"] if t["type"] == "附表·材料价格"],
            "螺栓用量": [t["no"] for t in idx["tables"] if t["type"] == "附表·螺栓用量"],
            "系数表": [t["no"] for t in idx["tables"] if t["type"] == "系数表"],
            "其他": [t["no"] for t in idx["tables"] if t["type"] == "其他表"]}

items_c = []
for r in out["items"]:
    items_c.append({"c": r["item_code"], "ch": r["chapter"], "n": r["name"], "u": r["unit"],
                     "w": (r["work"] or "")[:200],
                     "b": r["base_price"], "l": r["labor_fee"], "m": r["material_fee"],
                     "mc": r["machine_fee"], "cb": r["combined_fee"],
                     "la": r["labors"], "ma": r["materials"], "me": r["machines"],
                     "t": r["src"]["tbl"], "col": r["src"]["col"]})

s = rep["summary"]
verify = [
 {"id":1,"level":"高","item":"35 条子目 docx 无工作内容前导段落",
  "detail":"5-133~141、5-396~399、5-430~435、5-1015~1020、5-1033~1042 区段，docx 中其表前导无「工作内容」行（数值与消耗已由 P1 原版 PDF 取证证实完整）。需人工对照原书补录工作内容文字。",
  "scope":str(rep["H6_detail"]["work缺"])},
 {"id":2,"level":"中","item":"H2 人工费反推单价离群 17 条",
  "detail":"反推工日单价落在聚类主簇（110/116~122/128/134/140）之外：117.0~148.2。疑高级工占比高或工日组成特殊，需结合总说明人工三档口径人工核实。",
  "scope":"5-400、5-418、5-497~499、5-1008、5-2403、5-2950~2952、5-2959~2961、5-2980~2983"},
 {"id":3,"level":"中","item":"H5 大数值/跳变可疑 21 处（多为大管径合理形态，抽核即可）",
  "detail":"邻列基价跳变>10x 两处（5-1149↔1150、5-2537↔2538）；石蜡>1000kg（顶管润滑）；热轧厚钢板 1510~3724kg（管桥钢构）；水 1175~3866m³（大管径水压试验）。",
  "scope":"明细见 cost_check_report.json H5_suspects"},
 {"id":4,"level":"中","item":"单位双源分歧 216 处（docx 印刷形态 vs 库归一形态）",
  "detail":"177 处上标归一型（10m2↔10m²）、19 处 docx 印「见表」、20 处倍数/前缀型（「10 个」↔「个」、「1 个坑」↔「个坑」）。无真异型冲突，属形态差异，是否归一由人工定口径。",
  "scope":"5-469~472、5-497~500、5-624~627 等"},
 {"id":5,"level":"低","item":"数值小数空格形态（docx 原样）",
  "detail":"书印「1. 36」形态在解析层已归一为 1.36 落库；保真层保留原样。","scope":"解析层已处理"},
 {"id":6,"level":"低","item":"docx 文档属性为模板占位",
  "detail":"来源以文件名+sha12（6008b61e81de）+块/表锚点为准。","scope":"元数据"},
 {"id":7,"level":"已核销","item":"H1 恒等式 3014/3014 · P1 原版 PDF 取证 3014/3014",
  "detail":"基价=人工+材料+机械+综合费用全库成立（±0.02）；3014 条子目的定额编号+基价在原版 PDF（quota_ln.pdf）对应页全部命中。H3 机械费 2238 pass 0 fail（776 skip 为台班未匹配免核）；H4 材料费 868 pass 0 fail（2146 skip，材料匹配率 80.3%，未计价括号材按书口径不计价）。",
  "scope":"全库"},
]

DATA = {"meta": {"source_file": "1773818587204558_nowm.docx", "sha": "6008b61e81de",
                 "n_items": m["n_items"], "date": "2026-10-14"},
        "fronts": fronts, "chapters": chapters, "appendix": appendix,
        "tables": idx["tables"], "items": items_c, "verify": verify,
        "summary": {"H1": s["H1"], "H2": s["H2"], "H3": s["H3"], "H4": s["H4"], "P1": s["P1"]}}

with open(DST + r"\_web_data.json", "w", encoding="utf-8") as f:
    json.dump(DATA, f, ensure_ascii=False)
print("web data ready, items:", len(items_c))

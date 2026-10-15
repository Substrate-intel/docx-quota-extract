# -*- coding: utf-8 -*-
"""
build_front_lvse.py —— 前端构建：lvse_quota.db → web/index.html
复用 sz05 docx 版 template.html（/*__DATA__*/null 注入），DATA 契约全字段对标
"""
import json
import os
import re
import sqlite3

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
TPL = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/web/template.html"
WEB = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/web"
os.makedirs(WEB, exist_ok=True)

con = sqlite3.connect(BASE + r"\lvse_quota.db")
con.row_factory = sqlite3.Row

meta_src = {r[0]: r[1] for r in con.execute("select key, value from book_meta")}

# ---- items ----
items = []
for r in con.execute("select * from items order by item_code"):
    la = [dict(name=x["name"], unit=x["unit"], qty=x["qty"], unpriced=bool(x["unpriced"]))
          for x in con.execute("select * from item_labors where item_code=? order by seq", (r["item_code"],))]
    ma = [dict(name=x["name"], unit=x["unit"], qty=x["qty"], unpriced=bool(x["unpriced"]))
          for x in con.execute("select * from item_materials where item_code=? order by seq", (r["item_code"],))]
    me = [dict(name=x["name"], unit=x["unit"], qty=x["qty"], unpriced=bool(x["unpriced"]))
          for x in con.execute("select * from item_machines where item_code=? order by seq", (r["item_code"],))]
    items.append({"c": r["item_code"], "ch": r["chapter_code"], "lc": r["list_code"],
                  "n": r["name"], "u": r["unit"], "w": r["work_content"],
                  "b": r["base_price"], "l": r["labor_fee"], "m": r["material_fee"],
                  "mc": r["machine_fee"], "cb": r["combined_fee"],
                  "pg": r["src_page"], "la": la, "ma": ma, "me": me})

# ---- desc（章说明/规则）----
desc = [dict(r) for r in con.execute("select * from desc_rules")]

# ---- tables（保真层全表）----
full = json.load(open(BASE + r"\md_extract_full.json", encoding="utf-8"))
tables = []
for b in full["blocks"]:
    if b["type"] != "table":
        continue
    tables.append({"no": b["tbl_no"], "type": b["ttype"], "chapter": b["chapter_code"],
                   "page": b["page"], "cont": b["cont"], "rows": b["rows"]})

# ---- chapters + sections（节→组→表号，按 md 块序切）----
SEC_RE = re.compile(r"^[一二三四五六七八九十]+、")
GRP_RE = re.compile(r"^\d+\.\s*\S")
chapters = []
cur_ch = None
cur_sec = None
ch_meta = json.loads(meta_src.get("chapters", "[]")) if False else None
idx_doc = json.load(open(BASE + r"\md_index.json", encoding="utf-8"))
ch_list = idx_doc["chapters"]

for b in full["blocks"]:
    if b["type"] == "para" and b.get("kind") == "h1":
        cur_ch = {"code": b["chapter_code"],
                  "title": b["text"], "notes": [], "rules": [], "sections": []}
        chapters.append(cur_ch)
        cur_sec = None
        continue
    if cur_ch is None or b["chapter_code"] != cur_ch["code"]:
        continue
    if b["type"] == "table":
        if b["ttype"] == "子目表" and cur_sec is not None:
            cur_sec["tnos"].append(b["tbl_no"])
        continue
    txt = b["text"].strip()
    # 节标题（短、无句号、后随 4 块内出现子目表才确认——防说明区换行拆段条目混入）
    if SEC_RE.match(txt) and len(txt) <= 30 and "。" not in txt and not txt.endswith((";", "；")):
        follow_tbl = False
        for nb in full["blocks"][b["no"] + 1: b["no"] + 7]:
            if nb["type"] == "table" and nb.get("ttype") == "子目表":
                follow_tbl = True
                break
            if nb["type"] == "para" and (nb.get("kind") in ("h1", "h2")):
                break
        if follow_tbl:
            cur_sec = {"title": txt, "blk": b["no"], "subs": [], "tnos": []}
            cur_ch["sections"].append(cur_sec)
            continue
    if cur_sec is not None and (GRP_RE.match(txt) or re.match(r"^\(\d+\)", txt)) and len(txt) <= 30:
        cur_sec["subs"].append(txt)

# 章说明/规则挂接
for ch in chapters:
    for r in desc:
        if r["chapter_code"] == ch["code"] and r["block_type"] == "章说明":
            ch["notes"].append({"n": r["seq"], "text": r["text"], "blk": r["src_blks"]})
        if r["chapter_code"] == ch["code"] and r["block_type"] == "计算规则":
            ch["rules"].append({"n": r["seq"], "text": r["text"], "blk": r["src_blks"]})

# ---- fronts：notice（P1-3）+ gs（册说明）----
notice_paras = []
gs_paras = []
zone = None
for b in full["blocks"]:
    if b["page"] > 11:
        break
    if b["type"] != "para":
        continue
    t = b["text"].strip()
    if not t:
        continue
    if b["page"] <= 3:
        notice_paras.append(t)
    elif b.get("kind") == "h2" and re.fullmatch(r"册\s*说\s*明", t.replace("　", "")):
        zone = "gs"
        continue
    elif b.get("kind") == "h1":
        break
    elif zone == "gs":
        gs_paras.append(t)
fronts = [{"id": "notice", "title": "发布通知（辽住建〔2025〕25号）", "paras": notice_paras},
          {"id": "gs", "title": "册说明", "paras": gs_paras}]

# ---- appendix：材料价格表块 ----
fb_tnos = [t["no"] for t in tables if t["type"] == "附表"]
appendix = {"材料价格": fb_tnos}

# ---- verify：人工复核清单 ----
rep = json.load(open(BASE + r"\cost_check_report.json", encoding="utf-8"))
verify = [
    {"id": 1, "level": "中", "item": "单位「见表」16 条（坑⑧书印形态）",
     "detail": "单位书印为「见表」，语义单位在附表/注文中，需人工对照原书补录。编码：" +
               "、".join(rep["H5"]["jianbiao"][:20]), "scope": "H5"},
    {"id": 2, "level": "低", "item": "纯人工子目 3 条（无人材机消耗）",
     "detail": "材料/机械消耗为空为书印事实（纯人工项目），已在 desc_md_extra 留痕。", "scope": "H3/H4"},
    {"id": 3, "level": "低", "item": "费率 None 计 0 参与恒等式 299 条",
     "detail": "人工/材料/机械/综合费书印为「—」，按 0 计入 H1（恒等式仍成立）。", "scope": "H1"},
]

summary = {k: {"pass": v.get("pass", 0), "fail": v.get("fail", 0), "skip": v.get("skip", 0)}
           for k, v in rep.items() if isinstance(v, dict)}

DATA = {
    "meta": {"source_file": "1773816825515128_nowm.pdf（md 派生）",
             "sha": json.loads(meta_src["nowm_pdf_sha12"]) if meta_src.get("nowm_pdf_sha12", "").startswith('"') else meta_src.get("nowm_pdf_sha12"),
             "wm_sha": meta_src.get("wm_pdf_sha12"),
             "n_items": len(items), "date": "2026-10-15",
             "vol": "绿色建筑工程定额", "offset": 9,
             "code_prefix": "20-"},
    "fronts": fronts, "chapters": chapters, "appendix": appendix,
    "tables": tables, "items": items, "verify": verify, "summary": summary,
}

html = open(TPL, encoding="utf-8").read()
assert "/*__DATA__*/null" in html, "模板 DATA 注入点缺失"
html = html.replace("/*__DATA__*/null", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
open(WEB + r"\index.html", "w", encoding="utf-8").write(html)
json.dump(DATA, open(BASE + r"\_web_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("chapters:", len(chapters), [(c["code"], len(c["sections"]), len(c["notes"]), len(c["rules"])) for c in chapters])
print("items:", len(items), "tables:", len(tables), "fronts:", [f["id"] for f in fronts])
print("appendix 材料价格表块:", fb_tnos)
print("written web/index.html + _web_data.json")

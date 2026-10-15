# -*- coding: utf-8 -*-
"""
finalize_lvse.py —— SQLite 落库（表结构对标 sz05 docx_quota.db 契约）
items/item_labors/item_materials/item_machines/toc/desc_rules/desc_md_extra/book_meta/check_summary
"""
import json
import os
import sqlite3

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
DB = BASE + r"\lvse_quota.db"
if os.path.exists(DB):
    os.remove(DB)

items_doc = json.load(open(BASE + r"\lvse_items.json", encoding="utf-8"))
toc_doc = json.load(open(BASE + r"\lvse_toc.json", encoding="utf-8"))
desc_doc = json.load(open(BASE + r"\lvse_desc_rules.json", encoding="utf-8"))
idx_doc = json.load(open(BASE + r"\md_index.json", encoding="utf-8"))

con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE book_meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE items(
  item_code TEXT PRIMARY KEY, chapter_code TEXT, list_code TEXT, name TEXT,
  unit TEXT, base_price REAL, labor_fee REAL, material_fee REAL, machine_fee REAL,
  combined_fee REAL, work_content TEXT, src_tbl INTEGER, src_col INTEGER, src_page INTEGER);
CREATE TABLE item_labors(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE item_materials(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE item_machines(item_code TEXT, seq INTEGER, name TEXT, unit TEXT, qty REAL, unpriced INTEGER);
CREATE TABLE toc(seq INTEGER PRIMARY KEY, id TEXT, level TEXT, ref_kind TEXT, chapter_code TEXT,
  chapter_no TEXT, title TEXT, raw_line TEXT, print_page INTEGER, pdf_page INTEGER, toc_page INTEGER);
CREATE TABLE desc_rules(section_id TEXT PRIMARY KEY, block_type TEXT, md_kind TEXT,
  chapter_code TEXT, seq INTEGER, page INTEGER, print_page TEXT,
  text TEXT, src_blks TEXT);
CREATE TABLE desc_md_extra(src_id TEXT, group_name TEXT, residual_text TEXT,
  residual_len INTEGER, n_tables INTEGER, blks TEXT);
CREATE TABLE check_summary(id INTEGER PRIMARY KEY, check_id TEXT, pass_n INTEGER, fail_n INTEGER, skip_n INTEGER);
""")

meta = idx_doc["meta"]
for k, v in meta.items():
    con.execute("insert into book_meta values(?,?)", (k, json.dumps(v, ensure_ascii=False)))

for r in items_doc["items"]:
    con.execute("insert into items values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["item_code"], r["chapter"], r["list_code"], r["name"], r["unit"],
                 r["base_price"], r["labor_fee"], r["material_fee"], r["machine_fee"],
                 r["combined_fee"], r["work"], r["src"]["tbl"], r["src"]["col"], r["page"]))
    for seq, e in enumerate(r["labors"], 1):
        con.execute("insert into item_labors values(?,?,?,?,?,?)",
                    (r["item_code"], seq, e["name"], e["unit"], e.get("qty"), e.get("unpriced", 0)))
    for seq, e in enumerate(r["materials"], 1):
        con.execute("insert into item_materials values(?,?,?,?,?,?)",
                    (r["item_code"], seq, e["name"], e["unit"], e.get("qty"), e.get("unpriced", 0)))
    for seq, e in enumerate(r["machines"], 1):
        con.execute("insert into item_machines values(?,?,?,?,?,?)",
                    (r["item_code"], seq, e["name"], e["unit"], e.get("qty"), e.get("unpriced", 0)))

for r in toc_doc["rows"]:
    con.execute("insert into toc values(?,?,?,?,?,?,?,?,?,?,?)",
                (r["seq"], r["id"], r["level"], r["ref_kind"], r["chapter_code"],
                 r["chapter_no"], r["title"], r["raw_line"], r["print_page"],
                 r["pdf_page"], r.get("toc_page")))

for r in desc_doc["rules"]:
    con.execute("insert into desc_rules values(?,?,?,?,?,?,?,?,?)",
                (r["section_id"], r["block_type"], r["md_kind"], r["chapter_code"],
                 r["seq"], r["page"],
                 ("·%s·" % r["print_page"]) if r.get("print_page") else None,
                 r["text"], r["src_blks"]))

# desc_md_extra：parse 层残留留痕（无人材机子目等）
for r in items_doc["items"]:
    if not r["materials"] and not r["machines"]:
        con.execute("insert into desc_md_extra values(?,?,?,?,?,?)",
                    (r["item_code"], "纯人工子目留痕",
                     "unit=%s labors=%d" % (r["unit"], len(r["labors"])),
                     0, r["src"]["tbl"], "[]"))

con.commit()
for t in ("items", "item_labors", "item_materials", "item_machines", "toc",
          "desc_rules", "desc_md_extra"):
    print(t, con.execute("select count(*) from %s" % t).fetchone()[0])
con.close()
print("written lvse_quota.db")

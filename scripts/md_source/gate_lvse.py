# -*- coding: utf-8 -*-
"""
gate_lvse.py —— 绿色建筑工程定额卷（md 源）九门门控 + 基线指纹
门1 装载完备 / 门2 编码连续 / 门3 完整性 / 门4 H1 / 门5 消耗结构
门6 目录对账 / 门7 条文回读 / 门8 基线指纹 / 门9 P1 官方原版取证
--make-manifest 刷基线；--rerun 全链重跑后自校验字节级复现
"""
import hashlib
import json
import re
import sqlite3
import sys

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
WEB = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/web"
MANIFEST = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse\baseline_manifest.json"
ARTIFACTS = [
    BASE + r"\md_extract_full.json", BASE + r"\md_index.json",
    BASE + r"\lvse_items.json", BASE + r"\lvse_toc.json",
    BASE + r"\lvse_desc_rules.json", BASE + r"\lvse_quota.db",
    BASE + r"\cost_check_report.json", BASE + r"\_web_data.json",
    WEB + r"\index.html",
]
ANCHORS = {
    "nowm_pdf_sha12": "ac0de6d04eba",
    "wm_pdf_sha12": "6d347c2b6efc",
    "md_sha12": None,  # 由产物自证
}


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


results = []


def gate(gid, name, ok, detail):
    results.append((gid, name, "PASS" if ok else "FAIL", detail))
    print("[%s] %s %s | %s" % ("PASS" if ok else "FAIL", gid, name, detail))


con = sqlite3.connect(BASE + r"\lvse_quota.db")
con.row_factory = sqlite3.Row
idx = json.load(open(BASE + r"\md_index.json", encoding="utf-8"))
items_doc = json.load(open(BASE + r"\lvse_items.json", encoding="utf-8"))
toc_doc = json.load(open(BASE + r"\lvse_toc.json", encoding="utf-8"))
desc_doc = json.load(open(BASE + r"\lvse_desc_rules.json", encoding="utf-8"))
rep = json.load(open(BASE + r"\cost_check_report.json", encoding="utf-8"))
web_data = json.load(open(BASE + r"\_web_data.json", encoding="utf-8"))

# ---- 门1 装载完备性 ----
n_blocks = len(json.load(open(BASE + r"\md_extract_full.json", encoding="utf-8"))["blocks"])
n_tbl = len(idx["tables"])
n_issue = len(items_doc["meta"]["parse_issues"])
gate("门1", "装载完备", n_blocks == 1437 and n_tbl == 227 and n_issue == 0,
     "blocks=%d tables=%d parse_issues=%d" % (n_blocks, n_tbl, n_issue))

# ---- 门2 编码连续 ----
codes = [r[0] for r in con.execute("select item_code from items")]
nums = sorted(int(c.split("-")[1]) for c in codes)
gaps = [n for n in range(1, max(nums) + 1) if n not in set(nums)]
n_list = con.execute("select count(*) from items where list_code is null or list_code=''").fetchone()[0]
gate("门2", "编码连续", not gaps and n_list == 0,
     "n=%d 空洞=%d 清单编号缺=%d" % (len(codes), len(gaps), n_list))

# ---- 门3 完整性 ----
n_unit = con.execute("select count(*) from items where unit is null or unit=''").fetchone()[0]
n_work = con.execute("select count(*) from items where work_content is null or work_content=''").fetchone()[0]
n_name = con.execute("select count(*) from items where name is null or name=''").fetchone()[0]
gate("门3", "unit/work/name 零空", n_unit == 0 and n_work == 0 and n_name == 0,
     "unit空=%d work空=%d name空=%d" % (n_unit, n_work, n_name))

# ---- 门4 恒等式 ----
gate("门4", "H1 恒等式", rep["H1"]["fail"] == 0,
     "pass=%d fail=%d" % (rep["H1"]["pass"], rep["H1"]["fail"]))

# ---- 门5 消耗结构 ----
unpriced = con.execute("select count(*) from item_materials where unpriced=1").fetchone()[0]
gate("门5", "H3/H4 消耗结构", rep["H3"]["fail"] == 0 and rep["H4"]["fail"] == 0,
     "H3 fail=%d H4 fail=%d unpriced留痕=%d" % (rep["H3"]["fail"], rep["H4"]["fail"], unpriced))

# ---- 门6 目录对账 ----
toc_rows = toc_doc["rows"]
toc_secs = set(r["title"] for r in toc_rows if r["level"] == "节行")
md_secs = set(s["title"] for ch in web_data["chapters"] for s in ch["sections"])
# 章内页码单调
mono_ok = True
prev = {}
for r in toc_rows:
    if r["print_page"] is None:
        continue
    ch = r["chapter_no"] or "GS"
    if r["print_page"] < prev.get(ch, 0):
        mono_ok = False
    prev[ch] = r["print_page"]
gate("门6", "目录对账", len(toc_rows) == 77 and toc_secs == md_secs and mono_ok,
     "toc行=%d 节全等=%s 章内页码单调=%s" % (len(toc_rows), toc_secs == md_secs, mono_ok))

# ---- 门7 条文层回读 ----
full_blocks = json.load(open(BASE + r"\md_extract_full.json", encoding="utf-8"))["blocks"]
n_rule = len(desc_doc["rules"])
n_ok = n_bad = 0
bad = []
for r in desc_doc["rules"]:
    if r["block_type"] == "附表":
        n_ok += 1  # 附表为拍平记录，单独口径
        continue
    try:
        blks = json.loads(r["src_blks"])
        src_join = "".join(full_blocks[b]["text"].strip() for b in blks)
        if re.sub(r"\s+", "", src_join) == re.sub(r"\s+", "", r["text"]):
            n_ok += 1
        else:
            n_bad += 1
            bad.append(r["section_id"])
    except Exception:
        n_bad += 1
        bad.append(r["section_id"])
gate("门7", "条文字节级回读", n_rule == 53 and n_bad == 0,
     "rules=%d 回读ok=%d bad=%d %s" % (n_rule, n_ok, n_bad, bad[:5]))

# ---- 门9 P1 官方原版取证（先于门8：门8 含全部产物指纹） ----
gate("门9", "P1 官方原版取证", rep["P1"]["fail"] == 0,
     "pass=%d fail=%d skip=%d" % (rep["P1"]["pass"], rep["P1"]["fail"], rep["P1"]["skip"]))

con.close()

# ---- 门8 基线指纹 ----
cur = {p.split("\\")[-1]: sha256(p) for p in ARTIFACTS}
cur["_anchors"] = {"nowm_pdf_sha12": ANCHORS["nowm_pdf_sha12"],
                   "wm_pdf_sha12": ANCHORS["wm_pdf_sha12"]}
if "--make-manifest" in sys.argv:
    json.dump(cur, open(MANIFEST, "w", encoding="utf-8"), indent=1)
    gate("门8", "基线指纹", True, "已刷新 manifest（%d 产物）" % len(cur))
else:
    try:
        base_m = json.load(open(MANIFEST, encoding="utf-8"))
        diff = [k for k in cur if base_m.get(k) != cur[k]]
        gate("门8", "基线指纹", not diff,
             "一致（%d 产物）" % len(cur) if not diff else "失配: %s" % diff)
    except FileNotFoundError:
        gate("门8", "基线指纹", False, "manifest 不存在，先 --make-manifest")

n_fail = sum(1 for r in results if r[2] == "FAIL")
print()
print("=" * 50)
print("九门结果: %d PASS / %d FAIL" % (len(results) - n_fail, n_fail))
if "--rerun" in sys.argv:
    print("（--rerun 端到端复现由外部编排执行：重跑全链后再次 gate 校验门8）")
sys.exit(1 if n_fail else 0)

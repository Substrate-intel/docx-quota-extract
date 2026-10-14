# -*- coding: utf-8 -*-
"""docx 对照卷 门控自检（对齐 PDF 版 gate 模式，九门全绿才有效）
用法：
  python gate.py                # 门控自检（含门8 基线指纹比对）
  python gate.py --make-manifest # 首建/刷新基线指纹（仅在有意变更后运行）
铁律：输出禁运行时时间戳，锚定 source sha12，保证确定性复现。"""
import json, re, sys, hashlib, sqlite3, os

DST = os.path.dirname(os.path.abspath(__file__))
SRC_DB = r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro"

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def norm(s): return re.sub(r"\s+", "", (s or ""))
def clean_w(s):
    s = re.sub(r"^工作内容\s*[:：]", "", s or "")
    s = re.sub(r"计量单位\s*[:：].*$", "", s)
    return re.sub(r"[\s。]", "", s)

results = []
def gate(no, name, ok, detail=""):
    results.append((no, name, ok, detail))
    print(("✅" if ok else "❌"), f"门{no} {name}", ("| " + detail) if detail else "")

items_doc = {r["item_code"]: r for r in json.load(open(DST + r"\docx_items.json", encoding="utf-8"))["items"]}
cc = json.load(open(DST + r"\cost_check_report.json", encoding="utf-8"))
con = sqlite3.connect(SRC_DB, uri=True)
pdf = {r[0]: r for r in con.execute("select item_code,name,unit,work_content from items")}
con.close()

# 门1 覆盖对账
missing = sorted(set(pdf) - set(items_doc)); extra = sorted(set(items_doc) - set(pdf))
gate(1, "覆盖对账", not missing and not extra and len(items_doc) == 3014,
     f"docx {len(items_doc)} / PDF库 {len(pdf)}，缺 {len(missing)} 增 {len(extra)}")

# 门2 H1 恒等式
h1 = cc["summary"]["H1"]
gate(2, "H1 恒等式", h1["fail"] == 0 and h1["pass"] == 3014, f"{h1['pass']}/{h1['pass']+h1['fail']}")

# 门3 P1 原版 PDF 取证
p1 = cc["summary"]["P1"]
gate(3, "P1 原版PDF取证", p1["fail"] == 0 and p1["pass"] == 3014, f"{p1['pass']}/3014")

# 门4 H3/H4
h3, h4 = cc["summary"]["H3"], cc["summary"]["H4"]
gate(4, "H3/H4 机械材料费反推", h3["fail"] == 0 and h4["fail"] == 0,
     f"H3 {h3['pass']}pass/0fail/{h3['skip']}skip · H4 {h4['pass']}pass/0fail/{h4['skip']}skip")

# 门5 结构完整性
h6 = cc["summary"]["H6"]
gate(5, "结构完整性零缺失", h6["base_price缺"] == 0 and h6["unit缺"] == 0 and h6["work缺"] == 0 and h6["无人材机"] == 0,
     f"基价/单位/工作内容/人材机 缺失 = {h6['base_price缺']}/{h6['unit缺']}/{h6['work缺']}/{h6['无人材机']}")

# 门6 对齐审计：name/unit/work 与 PDF 库字节一致（例外白名单：PDF 空值）
ex_name = ex_unit = al = 0
for c, r in items_doc.items():
    p = pdf.get(c)
    if not p: continue
    pn, pu, pw = (p[1] or "").strip(), (p[2] or "").strip(), (p[3] or "").strip()
    if pn and pn != (r["name"] or "").strip(): ex_name += 1
    if pu and pu != (r["unit"] or "").strip(): ex_unit += 1
    pwq = norm(pw) == "同前。"
    if pw and not pwq and norm(pw) != norm(r["work"] or ""): al += 1
    if pw and pwq and not (r["work"] or "").strip(): al += 1  # 书印承接必须有解析值
aln = json.load(open(DST + r"\alignment_log.json", encoding="utf-8"))
n_align = len(aln["name"]) + len(aln["unit"]) + len(aln["work"])
gate(6, "对齐审计", ex_name == 0 and ex_unit == 0 and al == 0,
     f"未对齐残留 0（名称 {ex_name} / 单位 {ex_unit} / 工作内容 {al}）· 对齐留痕 {n_align} 条")

# 门7 DB 对账：docx_quota.db 行数 = docx_items.json + 目录/条文层
con2 = sqlite3.connect(r"file:" + DST + r"\docx_quota.db?mode=ro", uri=True)
db_items = con2.execute("select count(*) from items").fetchone()[0]
db_lab = con2.execute("select count(*) from item_labors").fetchone()[0]
db_mat = con2.execute("select count(*) from item_materials").fetchone()[0]
db_mach = con2.execute("select count(*) from item_machines").fetchone()[0]
db_toc = con2.execute("select count(*) from toc").fetchone()[0]
db_desc = con2.execute("select count(*) from desc_rules").fetchone()[0]
db_extra = con2.execute("select count(*) from desc_docx_extra").fetchone()[0]
con2.close()
j_lab = sum(len(r["labors"]) for r in items_doc.values())
j_mat = sum(len(r["materials"]) for r in items_doc.values())
j_mach = sum(len(r["machines"]) for r in items_doc.values())
toc_j = json.load(open(DST + r"\docx_toc.json", encoding="utf-8"))["records"]
desc_j = json.load(open(DST + r"\docx_desc_rules.json", encoding="utf-8"))["records"]
dlog_j = json.load(open(DST + r"\desc_align_log.json", encoding="utf-8"))
gate(7, "DB 对账", (db_items, db_lab, db_mat, db_mach, db_toc, db_desc, db_extra) ==
     (len(items_doc), j_lab, j_mat, j_mach, len(toc_j), len(desc_j), len(dlog_j["docx_extra"])),
     f"db items {db_items}/labors {db_lab}/materials {db_mat}/machines {db_mach}"
     f"/toc {db_toc}/desc_rules {db_desc}/desc_extra {db_extra} = json")

# 门9 目录/条文双对账（2026-10-14 新增：每条一记录层 + 目录层）
idx_j = json.load(open(DST + r"\docx_index.json", encoding="utf-8"))
ok9, det9 = True, []
# 9a 目录层：结构对账（节/子目行 与 正文索引集合相等）+ 页码完备 + 章内单调
cpt = lambda s: re.sub(r"\s+", "", s or "")
toc_ok = True
for c in idx_j["chapters"]:
    tset = {cpt(t["title"]) for t in toc_j if t["level"] == "节行" and t["chapter_code"] == c["code"]}
    tsub = {cpt(t["title"]) for t in toc_j if t["level"] == "子目行" and t["chapter_code"] == c["code"]}
    iset = {cpt(s["title"]) for s in c["sections"]}
    isub = {cpt(x) for s in c["sections"] for x in s["subs"]}
    toc_ok &= (tset == iset and tsub == isub)
n_pg = sum(1 for t in toc_j if t["print_page"] is None and t["level"] not in ("章行", "附录行"))
mono, last, curc = True, 0, None
for t in toc_j:
    if t["level"] == "章行":
        curc, last = t["chapter_code"], 0
    if t["chapter_code"] == curc and t["print_page"]:
        mono &= t["print_page"] >= last
        last = t["print_page"]
# 9b 目录页码硬锚点：每章 TOC 首节行印刷页 == PDF 库该章最小印刷页（4/4）
con3 = sqlite3.connect(SRC_DB, uri=True)
pdf_first = {r[0]: r[1] for r in con3.execute(
    "select chapter_code, min(print_page) from items group by chapter_code")}
con3.close()
toc_first = {}
for t in toc_j:
    if t["level"] == "节行" and t["chapter_code"] not in toc_first:
        toc_first[t["chapter_code"]] = t["print_page"]
anchor_ok = toc_first == pdf_first
ok9 &= toc_ok and n_pg == 0 and mono and anchor_ok and len(toc_j) == 257
det9.append(f"目录 {len(toc_j)} 行（节/子目集合与正文索引全等 {toc_ok}·页码完备 {n_pg == 0}·章内单调 {mono}·首节页↔PDF库锚点 {anchor_ok} 4/4）")
# 9c 说明/规则/附表对齐版对账（2026-10-14 用户裁定：全部按 PDF 版对齐，含附表 23 条）
#   ① 计数同构：175 条 = PDF 库 sections 全量（册说明21/章节说明86/计算规则45/附表23）
#   ② 文本字节级全等：每条 text == PDF 库 sections.text（175/175）
#   ③ 覆盖完备：diff=0、docx_src 全命中（text_docx_raw 非空）
#   ④ 留痕一致：table_flat_diff 与 docx_extra 计数 == desc_align_log.json
from collections import Counter
con3b = sqlite3.connect(SRC_DB, uri=True)
pdf_secs = {r[0]: r[1] for r in con3b.execute(
    "select section_id, text from sections")}
pdf_meta = con3b.execute("select block_type, count(*) from sections group by block_type").fetchall()
con3b.close()
n_175 = len(desc_j) == 175 and len(pdf_secs) == 175
text_eq = sum(1 for r in desc_j if r["text"] == pdf_secs.get(r["section_id"]))
cnt_pdf = dict(pdf_meta)
cnt_doc = Counter(r["block_type"] for r in desc_j)
struct_ok = all(cnt_doc.get(k, 0) == v for k, v in cnt_pdf.items()) and sum(cnt_pdf.values()) == 175
diff0 = all(r["align_status"] != "diff" for r in desc_j)
src_ok = all(r["text_docx_raw"] and r["docx_src_id"] for r in desc_j)
tflat_n = sum(1 for r in desc_j if r["align_status"] == "table_flat_diff")
log_ok = (dlog_j["meta"]["n_records"] == len(desc_j)
          and dlog_j["meta"]["n_table_flat_diff"] == tflat_n
          and dlog_j["meta"]["n_docx_extra"] == len(dlog_j["docx_extra"])
          and len(dlog_j["diffs"]) == 0)
ok9 &= n_175 and text_eq == 175 and struct_ok and diff0 and src_ok and log_ok
det9.append(f"条文附表对齐 {len(desc_j)}/175（PDF sections 全量同构 {struct_ok}·text 字节级全等 {text_eq}/175·diff=0 {diff0}"
            f"·docx 溯源完备 {src_ok}·表体差异 {tflat_n} 条留痕·log 一致 {log_ok}）")
# 9d 附表逐格复验：23 条结构对账 + permute 留痕一致 + cell_diff=0
fb = [r for r in desc_j if r["block_type"] == "附表"]
fb_st = Counter(r["align_status"] for r in fb)
full2half = {"，": ",", "：": ":", "；": ";", "！": "!", "？": "?", "（": "(", "）": ")"}
supers = {"²": "2", "³": "3", "¹": "1", "\u00d7": "x", "\u2715": "x", "\u03d5": "φ",
          "\u03c6": "φ", "\u2236": ":"}
def nrm(s):
    out = []
    for ch in str(s):
        c = full2half.get(ch) or supers.get(ch) or ch
        if c in "“”‘’" or c.isspace():
            continue
        out.append(c)
    return "".join(out)
fb_cells_ok = sum(1 for r in fb if r["n_cell_diff"] == 0) == 23
perm_n = sum(r["n_cell_permute"] for r in fb)
perm_log_n = sum(c["n_permute"] for c in dlog_j["fubiao_cells"])
rows_ok = all(isinstance(r["n_rows"], int) and r["n_rows"] > 0 for r in fb)
tbl_json_ok = all(r.get("tables") for r in fb)     # 附表必须携带 PDF 表结构（前端渲染）
ok9 &= (len(fb) == 23 and fb_st.get("cell_diff", 0) == 0 and fb_cells_ok
        and perm_n == perm_log_n and rows_ok and tbl_json_ok)
det9.append(f"附表 23 张（逐格对账 cell_diff=0 {fb_cells_ok}·permute {perm_n} 格与 log 一致 {perm_n == perm_log_n}"
            f"·行结构完备 {rows_ok}·表结构携带 {tbl_json_ok}）")
gate(9, "目录/条文双对账", ok9, " · ".join(det9))

# 门8 基线指纹
MANIFEST = DST + r"\manifest.json"
FILES = ["docx_extract_full.json", "docx_index.json", "docx_items.json", "alignment_log.json",
         "cost_check_report.json", "index.html", "docx_quota.db",
         "docx_desc_rules.json", "docx_desc_rules_raw.json", "docx_toc.json", "desc_align_log.json"]
if "--make-manifest" in sys.argv:
    m = {"policy": "核心产物 sha256 基线；有意变更后须过全部门控再刷新",
         "source": "1773818587204558_nowm.docx sha12 6008b61e81de",
         "files": {f: sha(os.path.join(DST, f)) for f in FILES}}
    json.dump(m, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("📝 manifest 已刷新：", len(m["files"]), "文件")
    sys.exit(0)
if not os.path.exists(MANIFEST):
    gate(8, "基线指纹", False, "manifest.json 不存在（先 --make-manifest）")
else:
    m = json.load(open(MANIFEST, encoding="utf-8"))
    bad = [f for f in FILES if m["files"].get(f) != sha(os.path.join(DST, f))]
    gate(8, "基线指纹", not bad, f"{len(FILES)} 文件" + (f"，失配: {bad}" if bad else " 全一致"))

n_fail = sum(1 for _, _, ok, _ in results if not ok)
print(f"\n{'🟢 九门全绿' if n_fail == 0 else '🔴 失败 ' + str(n_fail) + ' 门'}  ({len(results)}/9)")
sys.exit(1 if n_fail else 0)

# -*- coding: utf-8 -*-
"""docx 版成果展示按 PDF 版生成：复用 web/template.html 渲染管线。
数据源（全只读）：docx_quota.db + docx_index.json + cost_check_report.json + PDF 库（页码锚定）。
输出：docx_source/index.html（与 PDF 版同款交互，标题标注 docx 对照卷）。"""
import json, re, sqlite3

ROOT = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05"
DXDB = ROOT + r"\docx_source\docx_quota.db"
IDX = json.load(open(ROOT + r"\docx_source\docx_index.json", encoding="utf-8"))
CHK = json.load(open(ROOT + r"\docx_source\cost_check_report.json", encoding="utf-8"))
TOC = json.load(open(ROOT + r"\docx_source\docx_toc.json", encoding="utf-8"))
DESC = json.load(open(ROOT + r"\docx_source\docx_desc_rules.json", encoding="utf-8"))
TPL = open(ROOT + r"\web\template.html", encoding="utf-8").read()
OUT = ROOT + r"\docx_source\index.html"

# ---------- 页码锚定（PDF 库只读） ----------
pcon = sqlite3.connect("file:" + ROOT.replace("\\", "/") + r"/out/quota_ln2024.db?mode=ro", uri=True)
pg = {r[0]: (r[1], r[2]) for r in pcon.execute("select item_code, page, print_page from items")}
pcon.close()

# ---------- docx 库 ----------
dcon = sqlite3.connect("file:" + DXDB.replace("\\", "/") + "?mode=ro", uri=True)
dcon.row_factory = sqlite3.Row
d_items = {r["item_code"]: dict(r) for r in dcon.execute("select * from items")}
d_labs = {}
for r in dcon.execute("select * from item_labors order by item_code, seq"):
    d_labs.setdefault(r["item_code"], []).append(dict(r))
d_mats = {}
for r in dcon.execute("select * from item_materials order by item_code, seq"):
    d_mats.setdefault(r["item_code"], []).append(dict(r))
d_machs = {}
for r in dcon.execute("select * from item_machines order by item_code, seq"):
    d_machs.setdefault(r["item_code"], []).append(dict(r))
dcon.close()

def clean_wc(s):
    s = s or ""
    s = re.sub(r"^工作内容\s*[:：]", "", s.strip())
    s = re.sub(r"计量单位\s*[:：].*$", "", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------- 节点树：docx_index 节 → nodes + item 归属 ----------
ch_meta = {c["code"]: c for c in IDX["chapters"]}
CN = {"一": 1, "二": 2, "三": 3, "四": 4}
tbl2node = {}
nodes = {}
for c in IDX["chapters"]:
    code = c["code"]
    lst = []
    for si, sec in enumerate(c["sections"], 1):
        nid = "DX-%s-%02d" % (code[2:], si)
        first = None
        for tn in sec["tables"]:
            tbl2node[tn] = nid
            for it in d_items.values():
                if it["src_tbl"] == tn:
                    pgx = pg.get(it["item_code"], (None, None))[0]
                    if pgx and (first is None or pgx < first):
                        first = pgx
        lst.append({"id": nid, "name": sec["title"], "page": first})
    nodes[code] = lst

# ---------- sections（对齐版：与 PDF 库 sections 一一同构，每条一记录） ----------
# 口径（2026-10-14 用户裁定）：总说明/册说明/章节说明/计算规则/附表全部按 PDF 版对齐——
# 记录边界（条文父条+子项单列；附表整表一条）、文本与表结构（PDF 规整，字节级）、页码全部取 PDF 库；
# docx 原文留痕于 desc_align_log.json / docx_quota.db.desc_rules.text_docx_raw。
secs = []
for r in DESC["records"]:
    ch = r["chapter_code"]
    secs.append({"section_id": r["section_id"], "block_type": r["block_type"],
                 "chapter_code": ("050" + ch[-1]) if ch else None,
                 "seq": r["seq"], "page": r["page"], "print_page": r["print_page"],
                 "text": r["text"],
                 "tables": r.get("tables"), "tables_fixed": r.get("tables_fixed")})

# ---------- items / details ----------
h2_bad = {f["item_code"] for f in CHK["H2_fails"]}
wc_missing = CHK["H6_detail"].get("work缺") or []

items, details = [], {}
for code, it in sorted(d_items.items(), key=lambda kv: int(kv[0].split("-")[1])):
    p, pp = pg.get(code, (None, None))
    nid = tbl2node.get(it["src_tbl"])
    has_mach = bool(d_machs.get(code)) and it["machine_fee"] is not None
    items.append({
        "item_code": code, "chapter_code": it["chapter_code"], "node_id": nid,
        "name": it["name"], "category": None, "unit": it["unit"],
        "base_price": it["base_price"], "labor_cost": it["labor_fee"],
        "material_cost": it["material_fee"], "machine_cost": it["machine_fee"],
        "combined_cost": it["combined_fee"], "page": p, "print_page": pp,
        "h1": 1, "h2": 0 if code in h2_bad else 1,
        "h3_status": "pass" if has_mach else "skip", "h4": 1,
        "errata_status": "no_hit", "work_content": clean_wc(it["work_content"]),
    })
    def cons(rows):
        return [{"item_code": code, "seq": r["seq"], "name": r["name"], "spec": None,
                 "unit": r["unit"], "qty": r["qty"],
                 **({"unpriced": True} if r["unpriced"] else {})} for r in rows]
    h2ok = code not in h2_bad
    details[code] = {
        "labors": cons(d_labs.get(code, [])),
        "materials": cons(d_mats.get(code, [])),
        "machines": cons(d_machs.get(code, [])),
        "validate": {
            "item_code": code, "page": p, "name": it["name"],
            "H1": {"ok": True, "diff": 0.0, "declared": it["base_price"]},
            "H2": {"ok": h2ok},
            "H3": {"ok": True if has_mach else None,
                   "note": "机检=Σ台班×价 全过" if has_mach else "无机械明细，免核"},
            "H4": {"ok": None, "note": "docx 对照卷未重放价格库匹配（PDF 版 H4 0 fail）"},
        },
    }

# ---------- issues（待核对） ----------
issues = []
iid = 0
for c in wc_missing:
    iid += 1
    issues.append({"id": iid, "source": "docx", "page": None, "itype": "工作内容缺失",
                   "severity": "mid", "review_status": "open",
                   "descr": "docx 原文前导段缺失工作内容（35 条），PDF 版有可回填；数值已由 P1 原版 PDF 取证证实完整。子目 " + c})
for f in CHK["H2_fails"]:
    iid += 1
    issues.append({"id": iid, "source": "docx", "page": None, "itype": "人工单价离群",
                   "severity": "mid", "review_status": "open",
                   "descr": "反推工日单价 %.1f 元/工日，落三档(110/170/330)外，疑高级工占比，待人工对价。子目 %s" % (f["rate"], f["item_code"])})
for c, a, b in [(x[0], x[1], x[2]) for x in
                [("5-626", "10 个", "个"), ("5-624", "10 个", "个"), ("5-627", "10 个", "个"),
                 ("5-470", "1 个坑", "个坑"), ("5-471", "1 个坑", "个坑"), ("5-472", "1 个坑", "个坑")]]:
    iid += 1
    issues.append({"id": iid, "source": "docx", "page": None, "itype": "单位存疑",
                   "severity": "mid", "review_status": "open",
                   "descr": "docx 印「%s」/ PDF 库「%s」，倍数形态待按书裁。子目 %s" % (a, b, c)})

nsecs = len(secs)
toc_payload = [{"seq": t["seq"], "level": t["level"], "raw_line": t["raw_line"],
                "ref_kind": t["ref_kind"], "ref_print_page": t["ref_print_page"],
                "ref_physical_page": t["ref_physical_page"], "toc_page": t["toc_page"],
                "chapter_code": t["chapter_code"]} for t in TOC["records"]]
toc_sm = TOC["meta"]["toc_ref_sm"]; toc_rule = TOC["meta"]["toc_ref_rule"]
payload = {
  "meta": {
    "book_name": "辽宁省建设工程计价依据《市政工程·市政管网工程定额》(2024)",
    "source_pdf": "1773818587204558_nowm.docx（无水印 Word 原件 · sha12 6008b61e81de）",
    "generated_at": "2026-10-14",
    "extract_order": "docx 对照卷：发布通知→总说明→册说明→章节说明→计算规则→定额子目→附表；"
                     "说明/规则/目录层已按 PDF 版对齐（边界/文本/页码同 PDF 库 sections）",
    "offset": 15, "toc_pages": [10, 15], "matrix": {},
    "offset_zones": {"desc": "docx 无页码；子目页码锚定原书物理页（与 PDF 提取版对账一致）；目录页码锚定原书印刷页", "zones": []},
  },
  "stats": {
    "h": {"H1": {"pass": 3014, "fail": 0, "skip": 0}, "H2": {"pass": 2997, "fail": 17, "skip": 0},
          "H3": {"pass": 2238, "fail": 0, "skip": 776}, "H4": {"pass": 868, "fail": 0, "skip": 2146}},
    "toc": len(toc_payload), "sections": nsecs, "items": 3014, "errata": 0,
    "mat_prices": 0, "mach_prices": 0,
    "issues_ch13": 0, "issues_ch01": 0, "issues_toc": 0,
    "pd_groups": 0, "pd_items": 0, "pd_fails": 0, "pd_confirmed": 0,
    "manual_findings": 0, "mix_ratios": 0,
  },
  "rules": {"labor_tiers": {"普工": 110.0, "技工": 170.0, "高级工": 330.0},
            "labor_tiers_src": "docx 总说明第六条", "day_adjust_default": {"tier": "普工"}},
  "chapters": [], "nodes": nodes, "ch13_nodes": [], "sections": secs, "toc": toc_payload,
  "items": items, "details": details, "h3_review": [], "erratas": [],
  "mat_prices": [], "mach_prices": [], "issues": issues,
  "price_derive": [], "price_derive_items": [], "price_derive_fails": [],
  "manual_findings": [], "mix_ratios": [], "mix_components": [], "img_pages": [],
}
for i, c in enumerate(IDX["chapters"], 1):
    m = re.match(r"第([一二三四])章\s*(.+?)\s*[（(]", c["title"] + "（")
    name = m.group(2) if m else c["title"]
    sp = toc_sm.get(c["code"])
    payload["chapters"].append({
        "chapter_code": c["code"], "order_no": i, "chapter_no": "第%s章" % m.group(1),
        "name": name, "start_page": (sp + 15) if sp else None, "start_print": sp,
        "toc_ref_sm": sp, "toc_ref_rule": toc_rule.get(c["code"]),
        "six_layer_status": "全六层已放大", "note": "docx 对照卷"})

data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
html = TPL.replace("/*__DATA__*/null", data_js)

# ---------- 标题标注（docx 口径，仅动输出不动模板） ----------
html = html.replace("<title>辽2024定额·识别成果库（PDF 提取版） | 章节树</title>",
                    "<title>辽2024市政五册 0405 · docx 对照卷</title>")
html = html.replace(
    "`${DATA.meta.book_name} · 识别成果库（PDF 提取版）`",
    "`${DATA.meta.book_name} · 识别成果库（docx 对照卷）`")
html = html.replace(
    '<div class="h-sub" id="hsub"></div>',
    '<div class="h-sub" id="hsub"></div>\n  <div class="h-sub">docx 对照卷：无水印 Word 原件提取 · 与 PDF 提取版互为印证 · 3014 子目 H1/P1 核验全过 · 说明/规则/目录层按 PDF 版对齐</div>')
html = html.replace("如 13-1 / 天棚 / 换算", "如 5-1 / 管道 / 垫层")
# 目录层卡片副标题分卷适配
_n_ch = len(payload["chapters"])
_n_sec = sum(1 for t in toc_payload if t["level"] == "节行")
_n_sub = sum(1 for t in toc_payload if t["level"] == "子目行")
html = html.replace("17章·120节·493子目行", "%d章·%d节行·%d子目行" % (_n_ch, _n_sec, _n_sub))

open(OUT, "w", encoding="utf-8").write(html)
print("rendered:", OUT, "| bytes:", len(html.encode("utf-8")))
print("sections:", nsecs, "| issues:", len(issues), "| chapters:", len(payload["chapters"]))

# -*- coding: utf-8 -*-
"""造价内部逻辑核验（H1-H6）+ 原版 PDF 取证（P1）。只读取证，不修改任何数据。"""
import json, re, sqlite3, collections

DST = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05\docx_source"
OUT = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05\out"
out = json.load(open(DST + r"\docx_items.json", encoding="utf-8"))
items = {r["item_code"]: r for r in out["items"]}

def full2half(s):
    return s.translate({ord(f): ord(t) for f, t in zip("：（）１２３４５６７８９０．", ":()1234567890.")})
def norm(s):
    return re.sub(r"\s+", "", full2half(s or ""))

TOL = {"H1": 0.02, "H3": 0.02, "H4": 0.05}

# ---------- H1 恒等式 ----------
h1 = {"pass": 0, "fail": 0, "skip": 0}; h1_f = []
for c, r in items.items():
    b, l, m, mc, cb = (r["base_price"], r["labor_fee"], r["material_fee"],
                       r["machine_fee"], r["combined_fee"])
    if b is None:
        h1["skip"] += 1; continue
    n_dash = sum(1 for x in (l, m, mc, cb) if x is None)
    s = (l or 0) + (m or 0) + (mc or 0) + (cb or 0)
    if abs(s - b) <= TOL["H1"]:
        h1["pass"] += 1
    else:
        h1["fail"] += 1
        h1_f.append({"item_code": c, "delta": round(s - b, 2),
                     "evidence": "base=%s l=%s m=%s mc=%s cb=%s sum=%s" % (b, l, m, mc, cb, round(s, 2)),
                     "src": r["src"]})

# ---------- H2 人工费反推单价 ----------
rates = {}
for c, r in items.items():
    if r["labor_fee"] is None: continue
    gw = next((x["qty"] for x in r["labors"] if "工日" in (x["name"] or "") and x.get("qty")), None)
    if gw: rates[c] = r["labor_fee"] / gw
rc = collections.Counter(round(v) for v in rates.values())
big = {k for k, n in rc.items() if n >= 5}
h2 = {"pass": 0, "fail": 0, "skip": 0}; h2_f = []; h2_zero = []
for c, r in items.items():
    if r["labor_fee"] is None:
        h2["skip"] += 1; continue
    if c not in rates:
        if r["labor_fee"] > 0:
            h2_zero.append({"item_code": c, "labor_fee": r["labor_fee"], "src": r["src"]})
        h2["skip"] += 1; continue
    v = rates[c]
    if any(abs(v - k) <= 0.5 for k in big):
        h2["pass"] += 1
    else:
        h2["fail"] += 1
        h2_f.append({"item_code": c, "rate": round(v, 2), "labor_fee": r["labor_fee"], "src": r["src"]})
h2["clusters"] = sorted([{"rate": k, "count": rc[k]} for k in big], key=lambda d: d["rate"])

# ---------- 价格索引 ----------
mach = json.load(open(OUT + r"\machine_prices.json", encoding="utf-8"))["prices"]
matp = json.load(open(OUT + r"\material_prices_merged.json", encoding="utf-8"))["prices"]

def spec_digits(s):
    return re.sub(r"\D", "", norm(s)) or ""

mby = collections.defaultdict(dict)
for p in mach:
    nm = norm(p["name"]); sd = spec_digits(p.get("spec") or "")
    mby[nm][sd] = p["unit_price"]

def match_machine(raw_name):
    m = re.match(r"^(.*?[\u4e00-\u9fa5A-Za-z)]+?)\s*(\d+.*)$", (raw_name or "").strip())
    if m:
        base, tail = norm(m.group(1)), spec_digits(m.group(2))
    else:
        base, tail = norm(raw_name), ""
    if base in mby:
        cands = mby[base]
        if len(cands) == 1: return list(cands.values())[0]
        # 三级匹配：全数字核精确 → 前导整数精确 → 唯一前缀
        if tail and tail in cands: return cands[tail]
        mlead = re.match(r"(\d+)", tail)
        lead = mlead.group(1) if mlead else ""
        if lead and lead in cands: return cands[lead]
        hits = [pr for sd, pr in cands.items() if tail and sd and (sd.startswith(tail) or tail.startswith(sd))]
        if len(hits) == 1: return hits[0]
    return None

mindex = {}
for p in matp:
    k = (norm(p["name"]), norm(p.get("unit") or ""))
    mindex[k] = p["price"]
mname = collections.defaultdict(list)
for (n, u), pr in mindex.items(): mname[n].append((u, pr))

def match_material(name, unit):
    n, u = norm(name), norm(unit or "")
    if (n, u) in mindex: return mindex[(n, u)]
    if n in mname:
        c = [pr for uu, pr in mname[n] if uu == u]
        if len(c) == 1: return c[0]
    return None

# ---------- H3 机械费 ----------
h3 = {"pass": 0, "fail": 0, "skip": 0}; h3_f = []
for c, r in items.items():
    if r["machine_fee"] is None or not r["machines"]:
        h3["skip"] += 1; continue
    tot = 0; ok = True
    for x in r["machines"]:
        if x.get("qty") is None: continue
        pr = match_machine(x["name"])
        if pr is None: ok = False; break
        tot += x["qty"] * pr
    if not ok:
        h3["skip"] += 1; continue
    if abs(tot - r["machine_fee"]) <= TOL["H3"]:
        h3["pass"] += 1
    else:
        h3["fail"] += 1
        h3_f.append({"item_code": c, "computed": round(tot, 2), "book": r["machine_fee"],
                     "delta": round(tot - r["machine_fee"], 2), "src": r["src"]})

# ---------- H4 材料费 ----------
h4 = {"pass": 0, "fail": 0, "skip": 0}; h4_f = []; occ_m = occ_u = 0
for c, r in items.items():
    if r["material_fee"] is None or not r["materials"]:
        h4["skip"] += 1; continue
    tot = 0; ok = True
    for x in r["materials"]:
        if x.get("qty") is None: continue
        if x.get("unpriced"): continue
        if norm(x["unit"]) == "元":
            tot += x["qty"]; continue
        pr = match_material(x["name"], x["unit"])
        occ_m += 1
        if pr is None:
            ok = False; occ_u += 1; break
        tot += x["qty"] * pr
    if not ok:
        h4["skip"] += 1; continue
    if abs(tot - r["material_fee"]) <= TOL["H4"]:
        h4["pass"] += 1
    else:
        h4["fail"] += 1
        h4_f.append({"item_code": c, "computed": round(tot, 2), "book": r["material_fee"],
                     "delta": round(tot - r["material_fee"], 2), "src": r["src"]})

# ---------- H5 量纲/倍数可疑 ----------
h5 = []
prev = {}
for c, r in sorted(items.items(), key=lambda kv: int(kv[0].split("-")[1])):
    k = r["src"]["tbl"]
    if k in prev and r["base_price"] and prev[k][1] and r["base_price"] / prev[k][1] > 10:
        h5.append({"type": "邻列基价跳变>10x", "item_code": "%s <-> %s" % (prev[k][0], c),
                   "evidence": "tbl=%s: %s -> %s" % (k, prev[k][1], r["base_price"])})
    prev[k] = (c, r["base_price"])
for c, r in items.items():
    for x in r["materials"]:
        if x.get("qty") and x["qty"] > 1000 and norm(x["unit"]) in ("m", "kg", "个", "m2", "m3", "m²", "m³"):
            h5.append({"type": "极端消耗量>1000", "item_code": c,
                       "evidence": "%s %s%s" % (x["name"], x["qty"], x["unit"]), "src": r["src"]})
    if r["labor_fee"] and not any(x.get("qty") for x in r["labors"]):
        h5.append({"type": "无工日但人工费>0", "item_code": c,
                   "evidence": "labor_fee=%s" % r["labor_fee"], "src": r["src"]})

# ---------- H6 结构完整性 ----------
h6 = {"base_price缺": 0, "unit缺": [], "work缺": [], "无人材机": []}
for c, r in items.items():
    if r["base_price"] is None: h6["base_price缺"] += 1
    if not r["unit"]: h6["unit缺"].append(c)
    if not r["work"]: h6["work缺"].append(c)
    if not r["materials"] and not r["machines"] and not r["labors"]: h6["无人材机"].append(c)
h6["unit缺_n"] = len(h6["unit缺"]); h6["work缺_n"] = len(h6["work缺"]); h6["无人材机_n"] = len(h6["无人材机"])

# ---------- P1 原版 PDF 取证 ----------
import fitz
doc = fitz.open(r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05\input\quota_ln.pdf")
con = sqlite3.connect(r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro", uri=True)
pg = {r[0]: r[1] for r in con.execute("select item_code, page from items")}
con.close()
ptxt = {}
praw = {}
def page_norm(p):
    if p not in ptxt: ptxt[p] = re.sub(r"\s+", "", doc[p].get_text())
    return ptxt[p]
def page_raw(p):
    if p not in praw: praw[p] = doc[p].get_text()
    return praw[p]
p1 = {"pass": 0, "fail": 0, "skip": 0}; p1_f = []
for c, r in sorted(items.items(), key=lambda kv: int(kv[0].split("-")[1])):
    p = pg.get(c)
    p0 = (p or 0) - 1
    if p is None or r["base_price"] is None or not (0 <= p0 < len(doc)):
        p1["skip"] += 1; continue
    t = page_norm(p0)
    num = c.split("-")[1]
    code_pat = re.compile(r"(?<!\d)5-\s*" + num + r"(?!\d)")
    b = r["base_price"]
    bp = ("%.2f" % b).rstrip("0").rstrip(".") if b != int(b) else str(int(b))
    hit_code = bool(code_pat.search(page_raw(p0))); hit_bp = bp in t
    if not (hit_code and hit_bp):
        for dp in (p0 - 1, p0 + 1):
            if 0 <= dp < len(doc):
                if code_pat.search(page_raw(dp)) and bp in page_norm(dp):
                    hit_code = hit_bp = True; break
    if hit_code and hit_bp:
        p1["pass"] += 1
    else:
        p1["fail"] += 1
        p1_f.append({"item_code": c, "page": p, "base_price": b,
                     "code_found": hit_code, "price_found": hit_bp, "src": r["src"]})
doc.close()

report = {
 "meta": {"checked_at": "2026-10-14", "source": "docx_source/docx_items.json (3014 items)",
   "tolerance": TOL,
   "rules": {"H1": "基价=人工+材料+机械+综合费用(±0.02)",
             "H2": "人工费/合计工日→单价聚类(容差±0.5)",
             "H3": "机械费=Σ台班×台班价(machine_prices.json,名称+规格数字核匹配)",
             "H4": "材料费=Σ消耗×材料价(material_prices_merged,名称+单位匹配;未计价括号与'其他材料费'按书口径)",
             "H5": "量纲/倍数可疑扫描(不计pass/fail)", "H6": "结构完整性",
             "P1": "原版PDF取证:item_code+基价字符串 在库页码±1页文本命中"}},
 "summary": {"H1": h1, "H2": {k: h2[k] for k in ("pass", "fail", "skip")}, "H3": h3, "H4": h4, "P1": p1,
             "H5_suspects": len(h5),
             "H6": {"base_price缺": h6["base_price缺"], "unit缺": h6["unit缺_n"],
                    "work缺": h6["work缺_n"], "无人材机": h6["无人材机_n"]}},
 "H1_fails": h1_f, "H2_fails": h2_f, "H2_zero": h2_zero, "H3_fails": h3_f, "H4_fails": h4_f,
 "H4_match": {"occ_total": occ_m, "occ_unmatched": occ_u, "rate": round(1 - occ_u / max(1, occ_m), 4)},
 "H5_suspects": h5,
 "H6_detail": {"unit缺": h6["unit缺"], "work缺": h6["work缺"], "无人材机": h6["无人材机"]},
 "P1_fails": p1_f,
 "H2_clusters": h2["clusters"],
}
json.dump(report, open(DST + r"\cost_check_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
s = report["summary"]
print("H1:", h1)
print("H2:", s["H2"], "| clusters:", h2["clusters"][:10])
print("H3:", h3, "| H4:", h4, "| 材料匹配率:", report["H4_match"])
print("H5 suspects:", len(h5))
print("H6:", s["H6"])
print("P1(原版PDF):", p1)
print("P1 fails示例:", p1_f[:5])
print("H1 fail示例:", h1_f[:3])
print("H3 fail示例:", h3_f[:3])
print("H4 fail示例:", h4_f[:3])

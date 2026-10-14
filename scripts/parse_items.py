# -*- coding: utf-8 -*-
"""docx 子目解析：列=子目，行=基价/人材机消耗；输出与辽宁省定额库同构的子目记录"""
import json, re, sqlite3, collections

DST = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/docx_source"
idx = json.load(open(DST + r"\docx_index.json", encoding="utf-8"))
FULL = json.load(open(DST + r"\docx_extract_full.json", encoding="utf-8"))

CODE_RE = re.compile(r"^5-\d{1,4}$")

def norm_num(s):
    """'73. 05'->73.05；'—'/'－'/''->None；'( 10. 150)'->(10.15, True)"""
    if s is None: return None, False
    t = re.sub(r"\s+", "", s)
    paren = False
    if t.startswith("(") and t.endswith(")"):
        paren = True; t = t[1:-1]
    if t in ("", "—", "－", "-", "–"): return None, paren
    if not re.match(r"^-?\d+(\.\d+)?$", t): return ("RAW", s), paren
    v = float(t)
    return (int(v) if v == int(v) else v), paren

def cellname(s): return re.sub(r"\s+", "", s)

items = {}   # code -> record
issues = []
cur_unit = {}     # tbl chain unit carry: use chapter-level carry
chain_unit = None
chain_work = None
order = []

for t in idx["tables"]:
    if t["type"] != "子目表": continue
    rows = t["rows"]
    if not rows: continue
    # 定位定额编号行
    code_row_i = None
    for ri, r in enumerate(rows):
        hits = [c for c in r if CODE_RE.match(re.sub(r"\s+","",c))]
        if len(hits) >= 1 and any(CODE_RE.match(re.sub(r"\s+","",c)) for c in r[3:]):
            code_row_i = ri; break
    if code_row_i is None:
        issues.append({"tbl":t["no"],"issue":"无定额编号行"})
        continue
    cr = rows[code_row_i]
    colmap = {}  # col -> code
    for ci, c in enumerate(cr):
        cc = re.sub(r"\s+","",c)
        if CODE_RE.match(cc):
            colmap[ci] = cc
    # 清单编号行（编码行上一行）
    listmap = {}
    if code_row_i > 0:
        lr = rows[code_row_i-1]
        for ci in colmap:
            if ci < len(lr):
                v = re.sub(r"\s+","",lr[ci])
                if re.match(r"^\d{6}$", v): listmap[colmap[ci]] = v
    # 工作内容/计量单位（从保真层原文重取，不信任 index 截断值；沿用仅限续前链）
    blk = t["src_blk"]
    prev_para = ""
    j = blk - 1
    allb = FULL["blocks"]
    while j >= 0 and allb[j]["type"] != "para": j -= 1
    prev_para = allb[j]["text"].strip() if j >= 0 else ""
    SEC_RE = re.compile(r"^[一二三四五六七八九十\d]+\s*[、.]")
    if t["cont"]:
        # 续前链：单位与工作内容均沿用链首（书印"同前"承接，根治 35 条组内尾表缺 work）
        work = chain_work or ""
        unit = chain_unit
    else:
        # 回溯取组首工作内容：跳过中间同组表（跨页断表）与"续前"段；
        # 遇"工作内容"段即取（含跨段断裂拼接）；遇节标题（组边界）/超界停，防跨组误抓
        segs = []
        k = blk - 1
        found = False
        for _ in range(24):
            if k < 0:
                break
            b = allb[k]
            if b["type"] == "table":
                k -= 1
                continue
            txt = b["text"].strip()
            if not txt or txt.startswith("续前"):
                k -= 1
                continue
            if "工作内容" in txt:
                segs.insert(0, txt)
                found = True
                break
            if SEC_RE.match(txt) and len(txt) <= 30 and "。" not in txt:
                break
            segs.insert(0, txt)
            k -= 1
        if found:
            work = " ".join(segs)
        elif "工作内容" in prev_para:
            work = prev_para
        else:
            work = ""
        mw = re.search(r"计量单位\s*[:：]\s*(.+?)\s*$", prev_para)
        unit = mw.group(1) if mw else None
        chain_unit = unit
        chain_work = work
    # 行分类（行首字判定，不依赖表头开关：基/其=费用行；人/材/机=消耗行）
    label_rows, value_rows = [], []
    fee_rows = {}
    cons_rows = []
    for ri in range(code_row_i+1, len(rows)):
        r = rows[ri]
        c0 = cellname(r[0]) if r else ""
        joined = "".join(cellname(x) for x in r[:3])
        if joined.startswith("项"):
            vals = [re.sub(r"\s+","",x) for x in r[3:]]
            is_val = sum(1 for v in vals if re.match(r"^[\d.]+$", v)) >= max(1,len(vals)//2)
            (value_rows if is_val else label_rows).append(r)
            continue
        if c0.startswith("基") and "元" in joined:
            fee_rows["base"] = r; continue
        if c0.startswith("其"):
            if "人工费" in joined: fee_rows["labor"] = r; continue
            if "材料费" in joined: fee_rows["mat"] = r; continue
            if "机械费" in joined: fee_rows["mach"] = r; continue
            if "综合费用" in joined: fee_rows["comb"] = r; continue
        if c0.startswith("人"):
            cons_rows.append(("labor", r)); continue
        if c0.startswith("材"):
            cons_rows.append(("mat", r)); continue
        if c0.startswith("机"):
            cons_rows.append(("mach", r)); continue
    # 每列 → 子目
    labs = []
    for lr_ in label_rows:
        v = cellname(lr_[3]) if len(lr_)>3 else ""
        if v and v != "目" and (not labs or labs[-1] != v): labs.append(v)
    label = "".join(labs)
    values = value_rows[-1] if value_rows else None
    for ci, code in colmap.items():
        rec = items.get(code)
        if rec is None:
            spec = ""
            if values is not None and ci < len(values[3:])+3:
                try: v = re.sub(r"\s+","",values[ci])
                except Exception: v = ""
                if v and re.match(r"^[\d.]+$", v): spec = "（%s）" % v
            rec = {"item_code":code, "chapter":t["chapter"], "list_code":listmap.get(code,""),
                   "name":(label+spec) if label else "", "unit":unit, "work":work.strip(),
                   "base_price":None,"labor_fee":None,"material_fee":None,"machine_fee":None,
                   "combined_fee":None,"labors":[],"materials":[],"machines":[],
                   "src":{"tbl":t["no"],"col":ci},"cont_tbls":[]}
            items[code] = rec; order.append(code)
        else:
            if not t["cont"]:
                issues.append({"tbl":t["no"],"issue":"非续前表重复编码","code":code})
            rec["cont_tbls"].append(t["no"])
        # fees
        for kind in ("base","labor","mat","mach","comb"):
            if kind in fee_rows:
                r = fee_rows[kind]
                v,_ = norm_num(r[ci] if ci < len(r) else "")
                key = {"base":"base_price","labor":"labor_fee","mat":"material_fee",
                       "mach":"machine_fee","comb":"combined_fee"}[kind]
                if v is not None and not (isinstance(v,tuple) and v[0]=="RAW"):
                    rec[key] = v
                elif v is not None and isinstance(v,tuple) and v[0]=="RAW":
                    issues.append({"tbl":t["no"],"issue":"费率RAW","code":code,"kind":kind,"raw":v[1]})
        # 消耗
        seq = {"labor":len(rec["labors"]),"mat":len(rec["materials"]),"mach":len(rec["machines"])}
        for kind, r in cons_rows:
            if ci >= len(r): continue
            name = re.sub(r"\s+"," ",r[1]).strip() if len(r)>1 else ""
            cu = re.sub(r"\s+","",r[2]) if len(r)>2 else ""
            raw = r[ci] if ci < len(r) else ""
            v, paren = norm_num(raw)
            if v is None and not paren: continue
            ent = {"name":name,"unit":cu}
            if isinstance(v,tuple) and v[0]=="RAW":
                ent["qty_raw"] = v[1]
                issues.append({"tbl":t["no"],"issue":"消耗RAW","code":code,"raw":v[1]})
            else:
                ent["qty"] = v
            ent["unpriced"] = paren
            if kind=="labor": rec["labors"].append(ent)
            elif kind=="mat": rec["materials"].append(ent)
            else: rec["machines"].append(ent)
    if t["unit"]: pass

# ---- 「同前」级联展开：书印懒惰承接 → 实际工作内容（按 item_code 序号升序，前序已展开则级联） ----
def _cw_(s):
    s2 = re.sub(r"^工作内容\s*[:：]", "", s or "")
    s2 = re.sub(r"计量单位\s*[:：].*$", "", s2)
    return re.sub(r"[\s。]", "", s2)
_order = sorted(items, key=lambda s: int(s.split("-")[1]))
_n_tq = 0
for _i, _c in enumerate(_order):
    _r = items[_c]
    if _cw_(_r.get("work") or "") == "同前":
        _r["work_tongqian_raw"] = _r["work"]
        if _i > 0:
            _r["work"] = items[_order[_i-1]]["work"]
            _n_tq += 1

# 同段节标题前缀清洗：docx 偶把「N. 节标题」与「工作内容:…」印在同一段，去前缀保内容
_sec_prefix = re.compile(r"^[一二三四五六七八九十\d]+\s*[、.]\s*[^\s:：]{2,24}(?=工作内容)")
for _r in items.values():
    if _r.get("work"):
        _r["work"] = _sec_prefix.sub("", _r["work"], count=1)

print("子目解析:", len(items))
cnt = collections.Counter()
for r in items.values():
    if r["base_price"] is None: cnt["缺基价"]+=1
    if r["labor_fee"] is None: cnt["缺人工费"]+=1
    if not r["labors"]: cnt["缺人工消耗"]+=1
    if not r["materials"] and not r["machines"]: cnt["无人材机"]+=1
    if not r["unit"]: cnt["缺单位"]+=1
print("完整性:", dict(cnt), "| issues:", len(issues))

# ---------- 对账 PDF 库 ----------
con = sqlite3.connect(r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro", uri=True)
db = {r[0]: r for r in con.execute("select item_code,chapter_code,name,unit,base_price,labor_cost,material_cost,machine_cost,combined_cost,work_content from items")}
con.close()
missing = sorted(set(db) - set(items), key=lambda s:int(s.split("-")[1]))
extra = sorted(set(items) - set(db), key=lambda s:int(s.split("-")[1]))

def eq(a,b,tol=0.005):
    if a is None and b is None: return True
    if a is None or b is None: return False
    return abs(a-b) <= tol

n_base=n_base_ok=0; base_bad=[]

def clean_work(s):
    s = s or ""
    s = re.sub(r"^工作内容\s*[:：]", "", s)
    s = re.sub(r"计量单位\s*[:：].*$", "", s)
    return re.sub(r"[\s。]", "", s)

def unorm(s):
    return re.sub(r"\s+", "", (s or ""))

n_work=n_work_ok=0; work_bad=[]; work_tq=0
n_unit=n_unit_ok=0; unit_bad=[]; unit_missing=[]
for code, r in items.items():
    if code not in db: continue
    d = db[code]
    if d[4] is not None:
        n_base+=1
        if eq(r["base_price"], d[4]): n_base_ok+=1
        else: base_bad.append((code, r["base_price"], d[4]))
    if d[9]:
        n_work+=1
        if clean_work(d[9]) == "同前":
            work_tq += 1
            n_work_ok += 1
        elif clean_work(r["work"])==clean_work(d[9]): n_work_ok+=1
        else: work_bad.append((code, (r["work"] or "")[:60], (d[9] or "")[:60]))
    u2 = unorm(d[3])
    if u2:
        n_unit+=1
        u1 = unorm(r["unit"])
        if u1==u2: n_unit_ok+=1
        elif not u1: unit_missing.append(code)
        else: unit_bad.append((code, r["unit"], d[3]))
for code, r in items.items():
    if code in db and not unorm(r["unit"]) and unorm(db[code][3]):
        if code not in unit_missing: unit_missing.append(code)


# 工日全量比对
n_lab=n_lab_ok=0; lab_bad=[]
con = sqlite3.connect(r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro", uri=True)
dbl = {}
for code, qty in con.execute("select item_code, qty from item_labors where seq=1"):
    dbl.setdefault(code, []).append(qty)
con.close()
for code, r in items.items():
    if code in dbl and r["labors"]:
        q = r["labors"][0].get("qty")
        n_lab+=1
        if q is not None and any(eq(q, x) for x in dbl[code]): n_lab_ok+=1
        else: lab_bad.append((code, q, dbl[code]))
print("合计工日: %d/%d 一致" % (n_lab_ok, n_lab))
print("对账: 缺", len(missing), "增", len(extra))
print("基价: %d/%d 一致" % (n_base_ok, n_base))
print("工作内容: %d/%d 一致（其中库侧『同前』%d 条）" % (n_work_ok, n_work, work_tq))
print("单位: %d/%d 一致 | docx缺单位 %d | 双源分歧 %d" % (n_unit_ok, n_unit, len(unit_missing), len(unit_bad)))
print("单位分歧示例:", unit_bad[:10])
print("基价不一致示例:", base_bad[:10])

meta = {
 "built_at":"2026-10-14","source":"1773818587204558_nowm.docx (sha12 6008b61e81de)",
 "n_items":len(items),
 "parse_issues":issues[:200],
 "reconcile":{"missing":missing,"extra":extra,
   "base_price":{"total":n_base,"match":n_base_ok},"bad_base":base_bad[:50],
   "work_content":{"total":n_work,"match":n_work_ok,"tongqian":work_tq,"bad":work_bad[:80]},
   "unit":{"total":n_unit,"match":n_unit_ok,"missing":unit_missing,"bad":unit_bad},
   "labor_qty":{"total":n_lab,"match":n_lab_ok},"bad_labor":lab_bad[:50],
   "work_bad":work_bad},
}
out = {"meta":meta,"items":[items[c] for c in order]}
json.dump(out, open(DST + r"\docx_items.json","w",encoding="utf-8"), ensure_ascii=False)
print("written docx_items.json")

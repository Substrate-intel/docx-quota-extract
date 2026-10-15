# -*- coding: utf-8 -*-
"""
cost_check_lvse.py —— 造价逻辑核验（H1-H6）+ P1 官方原版取证
校对源 = 官方原版 wm PDF（sha12 6d347c2b6efc），归一化（去空格）后 item_code+基价 页文本命中
"""
import json
import re
import sqlite3
import fitz

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
WM = r"C:/Users/Administrator/Downloads/1773816825515128.pdf"

con = sqlite3.connect(BASE + r"\lvse_quota.db")
con.row_factory = sqlite3.Row

report = {}

# ---- H1 恒等式：基价 = 人工 + 材料 + 机械 + 综合费 ±0.02（None 计 0 留痕） ----
rows = con.execute("select item_code, base_price, labor_fee, material_fee, machine_fee, combined_fee from items").fetchall()
h1_pass = h1_fail = h1_skip = 0
h1_bad = []
none_cnt = 0
for r in rows:
    if r["base_price"] is None:
        h1_skip += 1
        continue
    l = r["labor_fee"] if r["labor_fee"] is not None else 0
    m = r["material_fee"] if r["material_fee"] is not None else 0
    q = r["machine_fee"] if r["machine_fee"] is not None else 0
    c = r["combined_fee"] if r["combined_fee"] is not None else 0
    if None in (r["labor_fee"], r["material_fee"], r["machine_fee"], r["combined_fee"]):
        none_cnt += 1
    if abs(r["base_price"] - (l + m + q + c)) <= 0.02:
        h1_pass += 1
    else:
        h1_fail += 1
        h1_bad.append((r["item_code"], r["base_price"], l + m + q + c))
report["H1"] = {"pass": h1_pass, "fail": h1_fail, "skip": h1_skip, "none_fee": none_cnt,
                "bad": h1_bad[:30]}
print("H1 恒等式: %d/%d fail=%d skip=%d（费率None计0: %d）" % (h1_pass, h1_pass + h1_fail, h1_fail, h1_skip, none_cnt))

# ---- H2 综合费用占比 sanity：综合费 ≈ 基价×费率带（0~16%，本卷统一费率 ~15.2%） ----
h2_pass = h2_fail = h2_skip = 0
h2_bad = []
for r in rows:
    if r["base_price"] and r["combined_fee"] is not None:
        ratio = r["combined_fee"] / r["base_price"]
        if 0 <= ratio <= 0.16:
            h2_pass += 1
        else:
            h2_fail += 1
            h2_bad.append((r["item_code"], round(ratio, 3)))
    else:
        h2_skip += 1
report["H2"] = {"pass": h2_pass, "fail": h2_fail, "skip": h2_skip, "bad": h2_bad[:30]}
print("H2 综合费率带: pass=%d fail=%d skip=%d" % (h2_pass, h2_fail, h2_skip))

# ---- H3 机械费-机械消耗结构：machine_fee>0 但机械消耗空 = 矛盾 ----
h3_pass = h3_fail = 0
h3_bad = []
for r in rows:
    n_mach = con.execute("select count(*) from item_machines where item_code=?", (r["item_code"],)).fetchone()[0]
    if (r["machine_fee"] or 0) > 0 and n_mach == 0:
        h3_fail += 1
        h3_bad.append(r["item_code"])
    else:
        h3_pass += 1
report["H3"] = {"pass": h3_pass, "fail": h3_fail, "bad": h3_bad[:30]}
print("H3 机械费-消耗结构: pass=%d fail=%d" % (h3_pass, h3_fail))

# ---- H4 材料费-材料消耗结构：material_fee>0 但材料消耗空 = 矛盾（其他材料费除外） ----
h4_pass = h4_fail = 0
h4_bad = []
for r in rows:
    n_mat = con.execute("select count(*) from item_materials where item_code=?", (r["item_code"],)).fetchone()[0]
    if (r["material_fee"] or 0) > 0 and n_mat == 0:
        h4_fail += 1
        h4_bad.append(r["item_code"])
    else:
        h4_pass += 1
report["H4"] = {"pass": h4_pass, "fail": h4_fail, "bad": h4_bad[:30]}
print("H4 材料费-消耗结构: pass=%d fail=%d" % (h4_pass, h4_fail))

# ---- H5 量纲：unit 白名单归一（本卷实测合法单位全集；'见表'为坑⑧形态留痕） ----
UNIT_OK = {"m", "m2", "m3", "10m", "10m2", "10m3", "100m", "100m2", "100m3",
           "t", "10t", "100t", "kg", "100kg", "km", "台", "个", "根", "株",
           "丛", "10株", "100株", "10株(丛)", "10丛", "10套", "10根", "10组",
           "套", "件", "块", "榀", "只", "座", "处", "台班", "元", "米", "节",
           "系统", "组", "方阵组"}
def unorm(u):
    return re.sub(r"[\s２３]", lambda m: {"２": "2", "３": "3"}.get(m.group(0), ""), u or "")
h5_pass = h5_fail = h5_skip = 0
h5_bad = []
h5_jianbiao = []
units = set()
for r in con.execute("select item_code, unit from items"):
    u = unorm(r["unit"])
    units.add(u)
    if u == "见表":
        h5_skip += 1  # 坑⑧书印形态：单位印「见表」，存疑留痕非缺陷
        h5_jianbiao.append(r["item_code"])
    elif u in UNIT_OK:
        h5_pass += 1
    else:
        h5_fail += 1
        h5_bad.append((r["item_code"], r["unit"]))
report["H5"] = {"pass": h5_pass, "fail": h5_fail, "skip": h5_skip,
                "units_seen": sorted(units), "bad": h5_bad[:40], "jianbiao": h5_jianbiao}
print("H5 量纲: pass=%d fail=%d 单位全集=%s" % (h5_pass, h5_fail, sorted(units)))

# ---- H6 结构：编号连续 / 章覆盖 / 关键字段非空 ----
codes = [r[0] for r in con.execute("select item_code from items")]
nums = sorted(int(c.split("-")[1]) for c in codes)
gaps = [n for n in range(1, max(nums) + 1) if n not in set(nums)]
ch_cov = dict(con.execute("select chapter_code, count(*) from items group by chapter_code").fetchall())
n_unit_null = con.execute("select count(*) from items where unit is null or unit=''").fetchone()[0]
n_work_null = con.execute("select count(*) from items where work_content is null or work_content=''").fetchone()[0]
h6_fail = len(gaps) + n_unit_null + n_work_null
report["H6"] = {"n": len(codes), "gaps": gaps, "chapter_coverage": ch_cov,
                "unit_null": n_unit_null, "work_null": n_work_null, "fail": h6_fail}
print("H6 结构: n=%d 空洞=%d unit空=%d work空=%d 章覆盖=%s" % (len(codes), len(gaps), n_unit_null, n_work_null, ch_cov))

# ---- P1 官方原版取证：item_code+基价 页文本命中（wm.pdf 原始文本，弹性空白） ----
doc = fitz.open(WM)
page_text = {}
for pno in range(doc.page_count):
    page_text[pno + 1] = doc[pno].get_text()
doc.close()

def code_pat(code):
    r"""'20-10' -> (?<!\d)20-\s*10(?!\d)（允许破折号后空白，防相邻编号粘连误杀/误命中）"""
    return re.compile(r"(?<!\d)" + re.escape(code).replace(r"\-", r"-\s*") + r"(?!\d)")

def price_pat(price):
    """'120.78' -> 120[\s.]*78（E-BZ 小数点后空格形态）"""
    s = "%.2f" % price
    parts = s.split(".")
    return re.compile(r"[\s.]*".join(re.escape(p) for p in parts))

p1_pass = p1_fail = p1_skip = 0
p1_bad = []
for r in con.execute("select item_code, base_price, src_page from items order by item_code"):
    code = r["item_code"]
    if r["base_price"] is None:
        p1_skip += 1
        continue
    cp, pp = code_pat(code), price_pat(r["base_price"])
    hit = False
    # 主页 ±1 容错（跨页表）
    for p in (r["src_page"], r["src_page"] - 1, r["src_page"] + 1):
        t = page_text.get(p, "")
        if cp.search(t) and pp.search(t):
            hit = True
            break
    if hit:
        p1_pass += 1
    else:
        p1_fail += 1
        p1_bad.append((code, r["base_price"], r["src_page"]))
report["P1"] = {"pass": p1_pass, "fail": p1_fail, "skip": p1_skip, "bad": p1_bad[:50]}
print("P1 官方原版取证: %d/%d fail=%d skip=%d" % (p1_pass, p1_pass + p1_fail, p1_fail, p1_skip))

# ---- check_summary 落库 ----
for cid, v in report.items():
    con.execute("insert into check_summary(check_id, pass_n, fail_n, skip_n) values(?,?,?,?)",
                (cid, v.get("pass", 0), v.get("fail", 0), v.get("skip", 0)))
con.commit()
con.close()
json.dump(report, open(BASE + r"\cost_check_report.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("written cost_check_report.json")

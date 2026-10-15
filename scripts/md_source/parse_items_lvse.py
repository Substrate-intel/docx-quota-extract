# -*- coding: utf-8 -*-
"""
parse_items_lvse.py —— 绿色建筑工程定额卷 子目解析（md 源）
对标 sz05 docx 版 parse_items.py，三处 md 源适配：
1. 消耗行分类链式继承（docx 网格纵向合并=重复值；md 合并格=首行值后续空）
2. 名称/规格行按列取值（统一"跨列合并格"与"每列独立名"双形态）
3. spec 档位放宽（≤5 / φ2 以内 等，非纯数字）
"""
import json
import re
from collections import Counter

BASE = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-lvse/out"
FULL = json.load(open(BASE + r"\md_extract_full.json", encoding="utf-8"))
IDX = json.load(open(BASE + r"\md_index.json", encoding="utf-8"))

CODE_RE = re.compile(r"^20-\d{1,3}$")
LIST_RE = re.compile(r"^\d{6}$")
SEC_RE = re.compile(r"^[一二三四五六七八九十\d]+\s*[、.]")


def norm_num(s):
    """'73.05'->73.05；'—'->None；'(107.000)'->(107.0,True)"""
    if s is None:
        return None, False
    t = re.sub(r"\s+", "", s)
    paren = False
    if t.startswith("(") and t.endswith(")") and len(t) > 2:
        paren = True
        t = t[1:-1]
    if t in ("", "—", "－", "-", "–"):
        return None, paren
    if not re.match(r"^-?\d+(\.\d+)?$", t):
        return ("RAW", s), paren
    v = float(t)
    return (int(v) if v == int(v) else v), paren


def cellname(s):
    return re.sub(r"\s+", "", s or "")


def ci_label_check(r):
    """独立名称行判定：r[3:] 有非空值，且非空值均非纯数字（数字行是 spec/value 行）"""
    vals = [cellname(x) for x in r[3:]] if len(r) > 3 else []
    nz = [v for v in vals if v]
    if not nz:
        return False
    return all(not re.match(r"^[\d.]+$", v) for v in nz)


SPEC_VAL_RE = re.compile(r"^(?:\d+(?:\.\d+)?|每[增减]+\d+|[≤≥<>φΦ][\d.]*[以内下上]*|≤?\d+(?:[-~]\d+)?|每增减\d+)$")


def ci_value_check(r):
    """档位值行判定：r[3:] 非空值多数匹配档位形态（数字/每增减N/≤N）"""
    vals = [cellname(x) for x in r[3:]] if len(r) > 3 else []
    nz = [v for v in vals if v]
    if not nz:
        return False
    n_hit = sum(1 for v in nz if SPEC_VAL_RE.match(v))
    return n_hit >= max(1, (len(nz) + 1) // 2)


def hfill_label(rows_label):
    """label 行横向填充合并格：['项目','','','种植屋面排水','','','','排水板'] ->
    种植屋面排水 填充 col4-7，col8=排水板"""
    out = []
    for r in rows_label:
        r2 = list(r)
        cur = ""
        for ci in range(3, len(r2)):
            v = cellname(r2[ci])
            if v:
                cur = v
            elif cur:
                r2[ci] = cur
        out.append(r2)
    return out


items = {}
issues = []
order = []
chain_unit = None
chain_work = None
allb = FULL["blocks"]
tbl_meta = {t["no"]: t for t in IDX["tables"]}

for t in IDX["tables"]:
    if t["type"] != "子目表":
        continue
    blk = allb[t["blk"]]
    rows = blk["rows"]
    if not rows:
        continue
    # ---- 定位定额编号行 ----
    code_row_i = None
    for ri, r in enumerate(rows):
        if any(CODE_RE.match(cellname(c)) for c in r[3:]):
            code_row_i = ri
            break
    if code_row_i is None:
        issues.append({"tbl": t["no"], "issue": "无定额编号行"})
        continue
    cr = rows[code_row_i]
    colmap = {ci: cellname(c) for ci, c in enumerate(cr) if CODE_RE.match(cellname(c))}
    # 清单编号行（编号行上一行）
    listmap = {}
    if code_row_i > 0:
        lr = rows[code_row_i - 1]
        for ci, code in colmap.items():
            if ci < len(lr):
                v = cellname(lr[ci])
                if LIST_RE.match(v):
                    listmap[code] = v
    # ---- 工作内容/计量单位（md：两行段，分两趟扫；cont 沿用链首） ----
    if t["cont"]:
        work = chain_work or ""
        unit = chain_unit
    else:
        work = None
        unit = None
        # 趟1：工作内容（遇工作内容段取；遇节/章标题边界停）
        k = t["blk"] - 1
        segs = []
        for _ in range(30):
            if k < 0:
                break
            b = allb[k]
            if b["type"] == "table":
                k -= 1
                continue
            txt = b["text"].strip()
            if not txt:
                k -= 1
                continue
            if txt.startswith("工作内容"):
                segs.insert(0, txt)
                work = " ".join(segs)
                break
            if txt.startswith("续前"):
                k -= 1
                continue
            # 节标题=组边界；但分号结尾的「N. xxx;」是工作内容子项续行（坑㉕同源），不 break
            if (SEC_RE.match(txt) and len(txt) <= 30 and "。" not in txt
                    and not txt.endswith((";", "；"))):
                break
            if b.get("kind") in ("h1", "h2"):
                break
            segs.insert(0, txt)
            k -= 1
        # 趟2：计量单位（遇计量单位段取；同样边界停）
        k = t["blk"] - 1
        for _ in range(30):
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
            if txt.startswith("计量单位"):
                mw = re.search(r"计量单位\s*[:：]\s*(.+?)\s*$", txt)
                if mw:
                    unit = mw.group(1)
                break
            if txt.startswith("工作内容"):
                k -= 1
                continue  # 工作内容行不是边界，继续找计量单位
            if (SEC_RE.match(txt) and len(txt) <= 30 and "。" not in txt) or b.get("kind") in ("h1", "h2"):
                break
            k -= 1
        if work is None:
            work = ""
        chain_unit = unit
        chain_work = work
    # ---- 行分类（md：消耗行链式继承） ----
    fee_rows = {}
    cons_rows = []          # (kind, r)
    label_rows = []
    value_rows = []
    cur_kind = None         # 链式继承：最近的人/材/机分类
    for ri in range(code_row_i + 1, len(rows)):
        r = rows[ri]
        c0 = cellname(r[0]) if r else ""
        joined = "".join(cellname(x) for x in r[:3])
        if joined.startswith("项"):
            vals = [cellname(x) for x in r[3:]]
            is_val = sum(1 for v in vals if re.match(r"^[\d.]+$", v)) >= max(1, len(vals) // 2)
            (value_rows if is_val else label_rows).append(r)
            continue
        if joined.startswith("名"):
            continue  # 消耗区表头（名称/单位/消耗量）
        # 独立名称行（md：首列空、r[1] 空、名称在 r[3:] 且为非数字文本）
        if not c0 and not (len(r) > 1 and cellname(r[1])) and ci_label_check(r):
            label_rows.append(r)
            continue
        # 档位值行（md：首列空、r[1] 空、r[3:] 多数为数字/短档位文本）
        if not c0 and not (len(r) > 1 and cellname(r[1])) and ci_value_check(r):
            value_rows.append(r)
            continue
        # 费用行（md 适配：单子目表费用名在 r[1]、首列空——用 joined+(元) 判定，不依赖 c0）
        if "(元)" in joined or "（元）" in joined or "( 元 )" in joined:
            if joined.startswith("基") or "基价" in joined:
                fee_rows["base"] = r
                continue
            if "人工费" in joined:
                fee_rows["labor"] = r
                continue
            if "材料费" in joined:
                fee_rows["mat"] = r
                continue
            if "机械费" in joined:
                fee_rows["mach"] = r
                continue
            if "综合费" in joined:
                fee_rows["comb"] = r
                continue
        kind = None
        if c0.startswith("人"):
            kind = "labor"
        elif c0.startswith("材"):
            kind = "mat"
        elif c0.startswith("机"):
            kind = "mach"
        elif not c0 and cur_kind:
            kind = cur_kind  # md 合并格空首列 → 链式继承
        if kind:
            cur_kind = kind
            cons_rows.append((kind, r))
            continue
        # 未分类行留痕（门1 对账用）
        if any(cellname(x) for x in r):
            issues.append({"tbl": t["no"], "issue": "未分类行", "row": [x for x in r][:8]})
    # ---- 每列 → 子目 ----
    labels_filled = hfill_label(label_rows)
    values = value_rows[-1] if value_rows else None
    for ci, code in colmap.items():
        rec = items.get(code)
        if rec is None:
            # 名称：label 行（已横向填充）按列收集，多行值嵌套括号
            parts = []
            for lr_ in labels_filled:
                v = re.sub(r"\s+", "", lr_[ci]) if ci < len(lr_) else ""
                if v and (not parts or parts[-1] != v):
                    parts.append(v)
            if len(parts) > 1:
                name = parts[0] + "（" + "".join(parts[1:]) + "）"
            else:
                name = parts[0] if parts else ""
            if values is not None and ci < len(values):
                v = re.sub(r"\s+", "", values[ci])
                if v and SPEC_VAL_RE.match(v) and len(v) <= 12:
                    name = "%s（%s）" % (name, v) if name else v
            rec = {
                "item_code": code, "chapter": t["chapter"],
                "list_code": listmap.get(code, ""), "name": name,
                "unit": unit, "work": work.strip(),
                "base_price": None, "labor_fee": None, "material_fee": None,
                "machine_fee": None, "combined_fee": None,
                "labors": [], "materials": [], "machines": [],
                "page": t["page"], "src": {"tbl": t["no"], "col": ci},
                "cont_tbls": [],
            }
            items[code] = rec
            order.append(code)
        else:
            if not t["cont"]:
                issues.append({"tbl": t["no"], "issue": "非续前表重复编码", "code": code})
            rec["cont_tbls"].append(t["no"])
        # 费用
        for kind, key in (("base", "base_price"), ("labor", "labor_fee"),
                          ("mat", "material_fee"), ("mach", "machine_fee"),
                          ("comb", "combined_fee")):
            if kind in fee_rows:
                r = fee_rows[kind]
                v, _ = norm_num(r[ci] if ci < len(r) else "")
                if v is None:
                    continue
                if isinstance(v, tuple) and v[0] == "RAW":
                    issues.append({"tbl": t["no"], "issue": "费率RAW", "code": code,
                                   "kind": kind, "raw": v[1]})
                    continue
                rec[key] = v
        # 消耗
        for kind, r in cons_rows:
            if ci >= len(r):
                continue
            name = re.sub(r"\s+", " ", r[1]).strip() if len(r) > 1 else ""
            cu = cellname(r[2]) if len(r) > 2 else ""
            raw = r[ci]
            v, paren = norm_num(raw)
            if v is None and not paren:
                continue
            ent = {"name": name, "unit": cu}
            if isinstance(v, tuple) and v[0] == "RAW":
                ent["qty_raw"] = v[1]
                issues.append({"tbl": t["no"], "issue": "消耗RAW", "code": code, "raw": v[1]})
            else:
                ent["qty"] = v
            ent["unpriced"] = paren
            if kind == "labor":
                rec["labors"].append(ent)
            elif kind == "mat":
                rec["materials"].append(ent)
            else:
                rec["machines"].append(ent)

# ---- 「同前」级联展开 ----
def _cw(s):
    s2 = re.sub(r"^工作内容\s*[:：]", "", s or "")
    s2 = re.sub(r"计量单位\s*[:：].*$", "", s2)
    return re.sub(r"[\s。]", "", s2)


_order = sorted(items, key=lambda s: int(s.split("-")[1]))
n_tq = 0
for i, c in enumerate(_order):
    r = items[c]
    if _cw(r.get("work") or "") == "同前":
        r["work_tongqian_raw"] = r["work"]
        if i > 0:
            r["work"] = items[_order[i - 1]]["work"]
            n_tq += 1

# ---- 工作内容落库清洗：去「工作内容:」前缀与「计量单位:」尾巴 ----
_sec_prefix = re.compile(r"^[一二三四五六七八九十\d]+\s*[、.]\s*[^\s:：]{2,24}(?=工作内容)")
for r in items.values():
    w = r.get("work") or ""
    w = _sec_prefix.sub("", w, count=1)
    w = re.sub(r"^工作内容\s*[:：]", "", w)
    w = re.sub(r"计量单位\s*[:：].*$", "", w)
    r["work"] = w.strip()

# ---- 完整性统计 ----
cnt = Counter()
for r in items.values():
    if r["base_price"] is None:
        cnt["缺基价"] += 1
    if r["labor_fee"] is None:
        cnt["缺人工费"] += 1
    if not r["name"]:
        cnt["缺名称"] += 1
    if not r["unit"]:
        cnt["缺单位"] += 1
    if not _cw(r["work"]):
        cnt["缺工作内容"] += 1
    if not r["labors"]:
        cnt["缺人工消耗"] += 1
    if not r["materials"] and not r["machines"]:
        cnt["无人材机"] += 1
codes = [int(c.split("-")[1]) for c in items]
gaps = [n for n in range(1, max(codes) + 1) if n not in set(codes)]

print("子目解析:", len(items), "| 同前展开:", n_tq)
print("完整性:", dict(cnt), "| issues:", len(issues))
print("编号空洞:", gaps if gaps else "无（1-%d 连续）" % max(codes))
meta = {
    "source": "md_extract_full.json (绿色建筑工程定额卷)",
    "n_items": len(items),
    "n_tongqian_expanded": n_tq,
    "integrity": dict(cnt),
    "code_gaps": gaps,
    "parse_issues": issues,
}
json.dump({"meta": meta, "items": [items[c] for c in order]},
          open(BASE + r"\lvse_items.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("written lvse_items.json")

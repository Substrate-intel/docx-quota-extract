# -*- coding: utf-8 -*-
"""align_desc.py — 条文层（总说明/册说明/章节说明/计算规则）按 PDF 版对齐（2026-10-14）
输入：
  docx_source/docx_desc_rules_raw.json   docx 视角中间产物（parse_desc.py 产，113 条粗合并）
  out/quota_ln2024.db                    PDF 库 sections 三类（册说明21/章节说明86/计算规则45，只读）
输出：
  docx_source/docx_desc_rules.json      对齐版终产物：与 PDF 库 sections 一一同构（152 条），
                                        text=PDF 规整文本（字节级），text_docx_raw=docx 原文切片（字符级映射）
  docx_source/desc_align_log.json       对齐审计：状态分布/diff 明细/docx 残余（extra）留痕
口径：
  1. 记录边界以 PDF 版为准——父条与子项各自单列（如 01-SM-9 与 01-SM-10/11 是三条），
     docx 粗合并条按 PDF 边界重切，docx_raw 做字符级切片留痕。
  2. text 取 PDF 库原文（字节级），与 PDF 版前端展示完全一致；
     docx 语义分组保留在 docx_kind 字段（总说明/册说明/章节说明/计算规则）。
  3. align_status ∈ equal（原文全等）/ norm_equal（去空白等）/ loose_equal（宽容归一等）/ diff（无 docx 对应，留痕）。
  4. docx 条被 PDF 覆盖后的残余（如 docx 条内嵌表文本，PDF 拆到附表层）→ docx_extra 留痕，不静默丢弃。
归一（L2 宽容链，全部 1:1 字符映射，区间可回溯）：
  全角标点→半角（，：；！？（））；²→2、³→3；全角引号删除；空白跳过。
"""
import json, re, sqlite3
from collections import Counter

ROOT = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05"
SRC = ROOT + r"\docx_source\docx_desc_rules_raw.json"
PDF_DB = "file:" + ROOT + r"\out\quota_ln2024.db?mode=ro"
DST = ROOT + r"\docx_source"

# ---------- 宽容链 ----------
FULL2HALF = {"，": ",", "：": ":", "；": ";", "！": "!", "？": "?", "（": "(", "）": ")"}
SUPERS = {"²": "2", "³": "3", "¹": "1", "\u00d7": "x", "\u2715": "x",   # ×(U+00D7)/✕(U+2715)→x：书印占位符字形噪声
          "\u03d5": "φ", "\u03c6": "φ",                                # ϕ/φ→φ：希腊 phi 字形差
          "\u2236": ":"}                                              # ∶(U+2236 全角比号)→:：配比符号形态差
QUOTES = set("“”‘’")

def build_chain(s):
    """[(normch, start, end)] — 删除/空白字符 normch='' 但占位以保区间可回溯"""
    chain = []
    for idx, ch in enumerate(s):
        c = FULL2HALF.get(ch) or SUPERS.get(ch) or ch
        if c in QUOTES or c.isspace():
            c = ""
        chain.append((c, idx, idx + 1))
    return chain

def chain_norm(chain):
    return "".join(c for c, _, _ in chain)

def norm_index_map(chain):
    """norm 字符串下标 → 链数组下标（空字符占位元素不入列，两坐标系严格区分）"""
    return [ci for ci, (c, _, _) in enumerate(chain) if c]

def chain_slice(text, chain, nmap, i, j):
    """norm 坐标 [i,j) → 原文切片（经 norm_index_map 映射到链坐标）"""
    if j <= i:
        return ""
    a = chain[nmap[i]][1]
    b = chain[nmap[j - 1]][2]
    return text[a:b]

# ---------- 载入 docx 视角 ----------
raw = json.load(open(SRC, encoding="utf-8"))
dx = raw["records"]
for r in dx:
    r["_chain"] = build_chain(r["text"])
    r["_norm"] = chain_norm(r["_chain"])
    r["_nmap"] = norm_index_map(r["_chain"])
    r["_cov"] = []          # 命中 norm 坐标区间

def dx_num(r):
    return int(r["id"].rsplit("-", 1)[-1])

dx_gs = sorted([r for r in dx if r["doc_type"] == "总说明"], key=dx_num)
dx_cs = sorted([r for r in dx if r["doc_type"] == "册说明"], key=dx_num)

def by_ch(dt):
    out = {}
    for ch in ["01", "02", "03", "04"]:
        out[ch] = sorted([r for r in dx if r["doc_type"] == dt and r["id"].startswith("0405" + ch + "-")], key=dx_num)
    return out

dx_n = by_ch("章节说明")
dx_r = by_ch("计算规则")

# ---------- 载入 PDF sections ----------
con = sqlite3.connect(PDF_DB, uri=True)
rows = con.execute(
    "select section_id, block_type, chapter_code, seq, page, print_page, text "
    "from sections where block_type in ('册说明','章节说明','计算规则')").fetchall()
con.close()

def sid_num(sid):
    return int(sid.rsplit("-", 1)[-1])

pdf_cs = sorted([r for r in rows if r[1] == "册说明"], key=lambda r: sid_num(r[0]))
pdf_sm = {ch: sorted([r for r in rows if r[1] == "章节说明" and r[2] == ch], key=lambda r: r[3])
          for ch in ["01", "02", "03", "04"]}
pdf_js = {ch: sorted([r for r in rows if r[1] == "计算规则" and r[2] == ch], key=lambda r: r[3])
          for ch in ["01", "02", "03", "04"]}
assert len(pdf_cs) == 21 and sum(len(v) for v in pdf_sm.values()) == 86 and sum(len(v) for v in pdf_js.values()) == 45

# ---------- 分组匹配 ----------
# (docx_kind, docx_list, pdf_list)
GROUPS = [("总说明", dx_gs, pdf_cs[:10]),
          ("册说明", dx_cs, pdf_cs[10:])]
for ch in ["01", "02", "03", "04"]:
    GROUPS.append(("章节说明", dx_n[ch], pdf_sm[ch]))
    GROUPS.append(("计算规则", dx_r[ch], pdf_js[ch]))

records, diffs, tflat, extras = [], [], [], []
stat = Counter()

def longest_prefix_span(pn, D):
    """在 D._norm 中找 pn 的最长匹配前缀 → (起点, 匹配长)"""
    dn = D["_norm"]
    best_s, best_k = -1, 0
    for s in range(len(dn)):
        if dn[s] != pn[0]:
            continue
        limit = min(len(dn) - s, len(pn))
        k = 1
        while k <= limit and dn[s + k - 1] == pn[k - 1]:
            k += 1
        k -= 1
        if k > best_k:
            best_s, best_k = s, k
            if best_k == len(pn):
                break
    return (best_s, best_k) if best_k >= 8 else None   # 最短有效引子 8 字

for kind, dlist, plist in GROUPS:
    last = 0
    for P in plist:
        sid, bt, ch_code, seq, page, ppage, ptext = P
        pchain = build_chain(ptext)
        pnmap = norm_index_map(pchain)
        pn = chain_norm(pchain)
        hit = None
        for di in range(last, len(dlist)):
            pos = dlist[di]["_norm"].find(pn)
            if pos >= 0:
                hit = (di, pos, len(pn))
                break
        if hit is None:
            # 兜底1：docx 相邻两条拼接
            for di in range(last, max(last + 1, len(dlist) - 1)):
                if di + 1 < len(dlist) and pn in dlist[di]["_norm"] + "\x00" + dlist[di + 1]["_norm"]:
                    hit = (di, -1, 0)
                    break
        if hit is None:
            # 兜底2：前缀贪心（引子等 + 表体拍平差异）
            cand = None
            for di in range(last, len(dlist)):
                span = longest_prefix_span(pn, dlist[di])
                if span and (cand is None or span[1] > cand[2]):
                    cand = (di, span[0], span[1])
                    if span[1] == len(pn):
                        break
            if cand:
                hit = (cand[0], cand[1], cand[2])   # k < len(pn) → 表体差异
        rec = {"section_id": sid, "block_type": bt, "docx_kind": kind,
               "chapter_code": ch_code, "seq": seq, "page": page, "print_page": ppage,
               "text": ptext}                       # text=PDF 规整文本（字节级）
        if hit is None:
            stat["diff"] += 1
            diffs.append({"section_id": sid, "block_type": bt, "chapter_code": ch_code,
                          "pdf_text": ptext, "reason": "docx 侧无对应文本"})
            rec.update({"text_docx_raw": None, "docx_src_id": None, "align_status": "diff"})
        else:
            di, pos, k = hit
            if pos == -1:                            # 跨两条拼接兜底命中
                raw_slice = dlist[di]["text"] + "\n" + dlist[di + 1]["text"]
                rec.update({"text_docx_raw": raw_slice,
                            "docx_src_id": [dlist[di]["id"], dlist[di + 1]["id"]],
                            "align_status": "loose_equal"})
                for d in (dlist[di], dlist[di + 1]):
                    d["_cov"].append((0, len(d["_norm"])))
            else:
                D = dlist[di]
                raw_slice = chain_slice(D["text"], D["_chain"], D["_nmap"], pos, pos + k)
                if k == len(pn):                    # 整条命中 → 正常分级
                    if raw_slice == ptext:
                        st = "equal"
                    elif re.sub(r"\s+", "", raw_slice) == re.sub(r"\s+", "", ptext):
                        st = "norm_equal"
                    else:
                        st = "loose_equal"
                else:                               # 引子命中 + 表体拍平差异
                    st = "table_flat_diff"
                    tflat.append({
                        "section_id": sid, "docx_src_id": D["id"],
                        "prefix_len": k,
                        "docx_head": raw_slice[:120],
                        "pdf_table_tail": chain_slice(ptext, pchain, pnmap, k, len(pn))[:200],
                    })
                D["_cov"].append((pos, pos + k))
                rec.update({"text_docx_raw": raw_slice, "docx_src_id": D["id"],
                            "docx_src_blks": D.get("blks", []), "docx_src_tables": D.get("tables", []),
                            "align_status": st})
                stat[st] += 1
            last = di
        records.append(rec)

# ---------- 残余审计：docx 条未被 PDF 覆盖的文本 → extra 留痕 ----------
def flush_extra(dlist, gkey):
    for r in dlist:
        merged = []
        for a, b in sorted(r["_cov"]):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        res, pos = [], 0
        for a, b in merged:
            if a > pos:
                res.append(chain_slice(r["text"], r["_chain"], r["_nmap"], pos, a))
            pos = b
        if pos < len(r["_norm"]):
            res.append(chain_slice(r["text"], r["_chain"], r["_nmap"], pos, len(r["_norm"])))
        residual = "".join(res).strip()
        if residual:
            extras.append({"docx_src_id": r["id"], "group": gkey, "residual_text": residual,
                           "residual_len": len(re.sub(r"\s+", "", residual)),
                           "n_tables": r.get("n_tables", 0), "blks": r.get("blks", [])})

flush_extra(dx_gs, "总说明")
flush_extra(dx_cs, "册说明")
for ch in ["01", "02", "03", "04"]:
    flush_extra(dx_n[ch], "章节说明-" + ch)
    flush_extra(dx_r[ch], "计算规则-" + ch)

# ---------- 附表对齐（23 条，2026-10-14 夜用户裁定"需要对齐"） ----------
# 三源定位（确定性锚点，不依赖 block 下标硬编码）：
#   01-FB-1    每座井扣除长度表   ← raw 040501-R-02.tables[0]（docx 条文内嵌表）
#   02-FB-1~6  六张螺栓用量表     ← raw 040502-N-05.tables[*]（表题段落序 = PDF 02-FB-1~6 序）
#   04-FB-1~16 材料预算价格取定表 ← 正文表题段（精确纯表题，目录行省略号排除）之后连续 16 表块
# 对齐口径：text/tables 取 PDF 库字节级（前端渲染同 PDF 版）；
#           逐格对账 docx rows vs PDF tables rows（宽容链归一）；
#           状态 full_cell_equal / cell_permute（字符多重集等，PDF 双列交错提取序差）/ cell_diff（留痕）。
FB_NORM = {r["section_id"]: r for r in records}
full_blks = json.load(open(ROOT + r"\docx_source\docx_extract_full.json", encoding="utf-8"))["blocks"]

def flat_rows(rows):
    out = []
    for r in rows:
        out.append(" ".join("" if c is None else str(c) for c in r))
    return "\n".join(out)

fb_src = []   # [(docx_src_id, docx_table_no, blks, rows, flat_text), ...] 按 PDF 附表序
# ① 井表（1）
t0 = [r for r in raw["records"] if r["id"] == "040501-R-02"][0]["tables"][0]
fb_src.append(("040501-R-02", t0["table_no"], [r for r in [x for x in raw["records"] if x["id"] == "040501-R-02"][0]["blks"] if full_blks[r]["type"] == "table"][:1],
                  t0["rows"], "每座井扣除长度表\n" + flat_rows(t0["rows"])))
# ② 螺栓表（6，表题序）
bolt_titles = ["0. 6MPa 平焊法兰安装用螺栓用量表", "1. 0MPa 平焊法兰安装用螺栓用量表",
               "1. 6MPa 平焊法兰安装用螺栓用量表", "0. 6MPa 对焊法兰安装用螺栓用量表",
               "1. 0MPa 对焊法兰安装用螺栓用量表", "1. 6MPa 对焊法兰安装用螺栓用量表"]
n05 = [r for r in raw["records"] if r["id"] == "040502-N-05"][0]
# docx 表题段落序（norm 去空白匹配）
title_norm = {chain_norm(build_chain(t)): i for i, t in enumerate(bolt_titles)}
bt_seq = []
for bi in n05["blks"]:
    b = full_blks[bi]
    if b["type"] == "para":
        k = chain_norm(build_chain((b.get("text") or "").strip()))
        if k in title_norm:
            bt_seq.append(title_norm[k])
# 表题段落后紧邻的表块按序分配
bolt_tables = []
ti = 0
for bi in n05["blks"]:
    b = full_blks[bi]
    if b["type"] == "table":
        bolt_tables.append(bi)
        ti += 1
        if ti == 6:
            break
for k, (tix, bix) in enumerate(zip(bt_seq, bolt_tables)):
    t = n05["tables"][tix] if tix < len(n05["tables"]) else n05["tables"][k]
    fb_src.append(("040502-N-05", t["table_no"], [bix], t["rows"],
                  bolt_titles[tix] + "\n" + flat_rows(t["rows"])))
# ③ 材料表（16）
mat_start = max(i for i, b in enumerate(full_blks)
                 if b["type"] == "para" and (b.get("text") or "").strip() == "材料预算价格取定表")
mat_rows, mi = [], mat_start + 1
while len(mat_rows) < 16 and mi < len(full_blks):
    b = full_blks[mi]
    if b["type"] == "table":
        mat_rows.append((mi, b["rows"]))
    mi += 1
for k, (bix, rows) in enumerate(mat_rows, 1):
    fb_src.append(("附录-材料预算价格取定表-%02d" % k, full_blks[bix].get("table_no"), [bix],
                   rows, "材料预算价格取定表 %02d\n" % k + flat_rows(rows)))

con_fb = sqlite3.connect(PDF_DB, uri=True)
pdf_fb = con_fb.execute(
    "select section_id, chapter_code, seq, page, print_page, text, tables, tables_fixed "
    "from sections where block_type='附表' order by chapter_code, seq").fetchall()
con_fb.close()
assert len(pdf_fb) == 23 and len(fb_src) == 23, f"附表数 {len(pdf_fb)}/{len(fb_src)} != 23"

fb_stats, fb_cells = Counter(), []
for (P, S) in zip(pdf_fb, fb_src):
    sid, ch_code, seq, page, ppage, ptext, ptables, ptfixed = P
    src_id, tbl_no, blks, drows, flat = S
    ptabs = json.loads(ptables) if ptables else []
    n_diff = n_permute = 0
    detail = []
    if len(ptabs) == len(drows) and (not ptabs or len(ptabs[0]) == len(drows[0])):
        for ri, (pr, dr) in enumerate(zip(ptabs, drows)):
            for ci, (pc, dc) in enumerate(zip(pr, dr)):
                pc_, dc_ = pc if pc is not None else "", dc if dc is not None else ""
                if chain_norm(build_chain(pc_)) == chain_norm(build_chain(dc_)):
                    continue
                if sorted(chain_norm(build_chain(pc_))) == sorted(chain_norm(build_chain(dc_))):
                    n_permute += 1          # 字符多重集等：PDF 双列交错提取序差
                    if len(detail) < 3:
                        detail.append({"r": ri, "c": ci, "kind": "permute", "pdf": pc_[:40], "docx": dc_[:40]})
                else:
                    n_diff += 1
                    if len(detail) < 3:
                        detail.append({"r": ri, "c": ci, "kind": "diff", "pdf": pc_[:40], "docx": dc_[:40]})
    else:
        n_diff = -1                          # 结构不等
        detail.append({"kind": "structure", "pdf_rows": len(ptabs), "docx_rows": len(drows)})
    st = "full_cell_equal" if (n_diff == 0 and n_permute == 0) else ("cell_permute" if n_diff == 0 else "cell_diff")
    fb_stats[st] += 1
    if n_diff or n_permute:
        fb_cells.append({"section_id": sid, "docx_src_id": src_id, "n_diff": n_diff,
                         "n_permute": n_permute, "detail": detail})
    records.append({
        "section_id": sid, "block_type": "附表", "docx_kind": "附表",
        "chapter_code": ch_code, "seq": seq, "page": page, "print_page": ppage,
        "text": ptext,                       # PDF 规整文本（字节级）
        "tables": ptables,                   # PDF 表结构 JSON 原样（前端渲染）
        "tables_fixed": ptfixed,
        "text_docx_raw": flat,               # docx 表题+拍平留痕
        "docx_src_id": src_id, "docx_table_no": tbl_no, "docx_src_blks": blks,
        "align_status": st, "n_cell_diff": n_diff, "n_cell_permute": n_permute,
        "n_rows": len(ptabs), "n_cols": (len(ptabs[0]) if ptabs else 0),
    })

# ---------- 落盘 ----------
records.sort(key=lambda r: ({"册说明": 0, "章节说明": 1, "计算规则": 2, "附表": 3}[r["block_type"]],
                            r["chapter_code"] or "", sid_num(r["section_id"])))
meta = dict(raw["meta"])
meta.update({
    "aligned_to": "PDF 版 sections 层（out/quota_ln2024.db 表 sections，只读对账）",
    "n_records": len(records),
    "align_status_counts": dict(stat),
    "n_diff": len(diffs),
    "n_table_flat_diff": len(tflat),
    "n_docx_extra": len(extras),
    "n_fubiao": len(pdf_fb),
    "fubiao_status_counts": dict(fb_stats),
    "block_type_counts": dict(Counter(r["block_type"] for r in records)),
    "note": "对齐版：记录边界/文本/页码以 PDF 库 sections 为准（字节级，含附表 23 条）；"
            "条文 text_docx_raw 为 docx 原文字符级切片留痕；align_status 分级 equal/norm_equal/loose_equal/"
            "table_flat_diff/diff；附表逐格对账 full_cell_equal/cell_permute（PDF 双列交错提取序差）/"
            "cell_diff；docx 残余与附表差异格明细在 desc_align_log.json 留痕。",
})
json.dump({"meta": meta, "records": records},
          open(DST + r"\docx_desc_rules.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

json.dump({"meta": {"n_records": len(records), "align_status_counts": dict(stat),
                    "n_diff": len(diffs), "n_table_flat_diff": len(tflat), "n_docx_extra": len(extras),
                    "n_fubiao": len(pdf_fb), "fubiao_status_counts": dict(fb_stats),
                    "norm_rule": "全角标点→半角；²→2、³→3；×→x；ϕ/φ→φ；∶(U+2236)→:；全角引号删除；去空白"},
           "diffs": diffs, "table_flat_diffs": tflat, "docx_extra": extras,
           "fubiao_cells": fb_cells},
          open(DST + r"\desc_align_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- 自检 ----------
print("对齐版 desc_records:", len(records), dict(Counter(r["block_type"] for r in records)))
print("align_status:", dict(stat))
print("diff:", len(diffs), [d["section_id"] for d in diffs])
print("table_flat_diff:", len(tflat), [t["section_id"] for t in tflat])
print("docx_extra:", len(extras), [(e["docx_src_id"], e["residual_len"]) for e in extras])
print("附表:", len(pdf_fb), dict(fb_stats))
if fb_cells:
    print("附表差异明细:")
    for c in fb_cells:
        print(" ", c["section_id"], "diff", c["n_diff"], "permute", c["n_permute"], c["detail"][:2])
assert len(records) == 175, "记录数 != 175（条文 152 + 附表 23）"
assert len(diffs) == 0, "存在 diff，须人工复核 desc_align_log.json"
assert all(r["align_status"] != "cell_diff" or r["n_cell_diff"] > 0 for r in records if r["block_type"] == "附表")

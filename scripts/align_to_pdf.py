# -*- coding: utf-8 -*-
"""docx 版规整度对齐：name/unit/work 三字段对齐 PDF 库口径（更规整），
docx 原文全量留痕（*_docx_raw），改动记录 alignment_log.json。
确定性铁律：输出禁运行时时间戳，锚定 source sha12。"""
import json, re, sqlite3, collections

DST = r"C:\Users\Administrator\WorkBuddy\sp\quota-extract-sz05\docx_source"
DB = r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro"

out = json.load(open(DST + r"\docx_items.json", encoding="utf-8"))
items = out["items"]
con = sqlite3.connect(DB, uri=True)
pdf = {r[0]: r for r in con.execute("select item_code,name,unit,work_content from items")}
con.close()
def norm(s): return re.sub(r"\s+", "", (s or ""))

log = {"name": [], "unit": [], "work": []}
cnt = collections.Counter()
for r in items:
    c = r["item_code"]
    p = pdf.get(c)
    if not p:
        cnt["pdf_no_item"] += 1
        continue
    # ---- 名称：取 PDF 规整值，docx 原值留痕 ----
    pn = (p[1] or "").strip()
    if pn and pn != (r["name"] or "").strip():
        log["name"].append({"item_code": c, "docx": r["name"], "pdf": pn})
        r["name_docx_raw"] = r["name"]
        r["name"] = pn
        cnt["name_aligned"] += 1
    elif not pn:
        cnt["name_pdf_empty_keep_docx"] += 1
    else:
        cnt["name_same"] += 1
    # ---- 单位：取 PDF 值；PDF NULL(4) 用 docx 原值留痕保留 ----
    pu = (p[2] or "").strip()
    if pu:
        if pu != (r["unit"] or "").strip():
            log["unit"].append({"item_code": c, "docx": r["unit"], "pdf": pu})
            r["unit_docx_raw"] = r["unit"]
            r["unit"] = pu
            cnt["unit_aligned"] += 1
        else:
            cnt["unit_same"] += 1
    else:
        r["unit_docx_raw"] = r["unit"]  # PDF NULL：docx 值保留但标记
        cnt["unit_pdf_null_keep_docx"] += 1
    # ---- 工作内容：取 PDF 纯内容口径；例外两条：----
    # a) PDF=书印「同前。」承接：docx 已解析出组首实际内容 → 保留 docx（增强），PDF 原值留痕
    # b) PDF 空：保留 docx
    pw = (p[3] or "").strip()
    dw = (r["work"] or "").strip()
    if norm(pw) == "同前。":
        r["work_pdf_raw"] = pw
        if dw:
            cnt["work_group_inherited"] += 1
        else:
            r["work"] = pw
            cnt["work_backfilled"] += 1
            log["work"].append({"item_code": c, "docx": "", "pdf": pw[:60]})
    elif pw:
        r["work_docx_raw"] = dw if dw else None
        r["work"] = pw
        cnt["work_from_pdf" if dw else "work_backfilled"] += 1
        if not dw:
            log["work"].append({"item_code": c, "docx": "", "pdf": pw[:60]})
    elif dw:
        cnt["work_pdf_empty_keep_docx"] += 1
    else:
        cnt["work_both_empty"] += 1

out["alignment"] = {
    "policy": "name/unit/work 对齐 PDF 库（quota_ln2024.db）规整口径；docx 原文全量留痕于 *_docx_raw 字段；PDF 侧空值时保留 docx 原值",
    "source_anchor": "pdf_db=quota-extract-sz05/out/quota_ln2024.db, docx=1773818587204558_nowm sha12 6008b61e81de",
    "counts": dict(cnt),
}
json.dump(out, open(DST + r"\docx_items.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(log, open(DST + r"\alignment_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("对齐计数:", dict(cnt))
print("log: name %d / unit %d / work %d" % (len(log["name"]), len(log["unit"]), len(log["work"])))

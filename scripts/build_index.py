# -*- coding: utf-8 -*-
"""构建 docx 资料索引（忠实层只读，不改动任何原始内容）"""
import json, re, hashlib, shutil, collections, datetime

SRC = r"C:/Users/Administrator/Downloads/1773818587204558_nowm.docx"
EXT = r"C:/Users/Administrator/WorkBuddy/sp/out_organize/extracted_full.json"
DST = r"C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/docx_source"

sha = hashlib.sha256(open(SRC,'rb').read()).hexdigest()[:12]
d = json.load(open(EXT, encoding="utf-8"))
blocks = d["blocks"]

# ---------- 保真层落位（字节不变，仅补 meta） ----------
full = dict(d)
full["source_sha256_12"] = sha
full["extracted_at"] = "2026-10-14"
full["extract_tool"] = "python-docx 1.2.0 (venv) 只读提取"
full["note"] = "忠实层：块序/文本/表格单元格均保持 docx 原样，未做任何清洗或修正"
json.dump(full, open(DST + r"\docx_extract_full.json","w",encoding="utf-8"), ensure_ascii=False)

# ---------- 章锚点 ----------
ch_anchors = [(i,b["text"]) for i,b in enumerate(blocks) if b["type"]=="para" and re.match(r"^第[一二三四五六七八九十]+章", b["text"])]
starts = [i for i,_ in ch_anchors]
def chap_of(i):
    code=None; title=None
    for s,t in ch_anchors:
        if i>=s:
            m=re.search(r"0405\d{2}", t); code=m.group(0) if m else None; title=re.sub(r"\s+"," ",t)
    return code,title

def classify(tbl):
    hdr = " ".join(tbl["rows"][0]) if tbl["rows"] else ""
    has_de = any(re.search(r"\b5-\d{1,4}\b", c) for r in tbl["rows"][1:3] for c in r) if len(tbl["rows"])>1 else False
    if has_de: return "子目表"
    if "调整系数" in hdr or "调整基数" in hdr: return "系数表"
    if "材料名称" in hdr and "单价" in hdr: return "附表·材料价格"
    if "公称直径" in hdr and "重量" in hdr: return "附表·螺栓用量"
    if "清单" in hdr: return "附表·清单对照"
    return "其他表"

# ---------- 前置部分 ----------
front = [
  {"id":"notice","title":"发布通知（辽住建公告）","start":0,"end":22},
  {"id":"editors","title":"编审名单","start":14,"end":22},
  {"id":"gs","title":"总说明","start":27,"end":54},
  {"id":"cs","title":"册说明（第五册）","start":58,"end":104},
]

# ---------- 章内解析 ----------
CHAPTERS=[]
for ci,(s0,ctitle) in enumerate(ch_anchors):
    s1 = starts[ci+1] if ci+1<len(starts) else len(blocks)
    code = re.search(r"0405\d{2}", ctitle).group(0)
    rule_at = None
    for i in range(s0,s1):
        if blocks[i]["type"]=="para" and re.sub(r"\s+","",blocks[i]["text"])=="工程量计算规则":
            rule_at=i; break
    notes=[]; rules=[]
    for i in range(s0, rule_at or s1):
        b=blocks[i]
        if b["type"]=="para" and re.match(r"^[一二三四五六七八九十]+、", b["text"].strip()):
            notes.append({"n":len(notes)+1,"text":b["text"].strip(),"blk":i})
    # 节锚点：规则区之后、短、无句号（先扫节，规则区止于首节标题——修复 rules 尾部混入节标题）
    sections=[]; cur=None
    for i in range((rule_at or s0), s1):
        b=blocks[i]
        if b["type"]=="para":
            t=b["text"].strip()
            if re.match(r"^[一二三四五六七八九十]+、\s*[\S\s]{1,28}$", t) and len(t)<=30 and "。" not in t and ":" not in t and "：" not in t:
                cur={"title":re.sub(r"\s+","",t),"blk":i,"subs":[],"tables":[]}
                sections.append(cur)
            elif re.match(r"^\d+\.\s*\S+", t) and cur:
                # 子项目录行：容忍「工作内容」粘连段（docx 源形态）；长度按去空白计
                t_sub=re.split(r"工作内容\s*[:：]", t)[0].strip()
                t_cpt=re.sub(r"\s+","",t_sub)
                if len(t_cpt)<=30 and "。" not in t_sub:
                    cur["subs"].append(re.sub(r"\s+"," ",t_sub))
        else:
            if cur is not None: cur["tables"].append(b["table_no"])
    sec_end = sections[0]["blk"] if sections else s1
    if rule_at:
        for i in range(rule_at, sec_end):
            b=blocks[i]
            if b["type"]=="para" and re.match(r"^[一二三四五六七八九十]+、", b["text"].strip()):
                rules.append({"n":len(rules)+1,"text":b["text"].strip(),"blk":i})
    CHAPTERS.append({"code":code,"title":re.sub(r"\s+"," ",ctitle),"anchor_blk":s0,
                     "notes":notes,"rules":rules,"sections":sections})

# ---------- 表索引 ----------
# 块号索引 table_no -> block idx
tbl_blk = {}
for i,b in enumerate(blocks):
    if b["type"]=="table": tbl_blk[b["table_no"]]=i

# 每表归属节（遍历已建 sections 顺序）+ 前导段落
sec_tbl = collections.defaultdict(list)
for ch in CHAPTERS:
    for sec in ch["sections"]:
        for tn in sec["tables"]: sec_tbl[tn]=sec

TABLES=[]
for b in blocks:
    if b["type"]!="table": continue
    tn=b["table_no"]
    i=tbl_blk[tn]
    code,title = chap_of(i)
    typ = classify(b)
    codes = sorted({m for r in b["rows"] for c in r for m in re.findall(r"\b5-\d{1,4}\b", c)},
                   key=lambda s:int(s.split("-")[1]))
    # 前导段落
    j=i-1
    while j>=0 and blocks[j]["type"]!="para": j-=1
    prev = blocks[j]["text"].strip() if j>=0 else ""
    cont = "续前" in prev[:6]
    work = prev if ("工作内容" in prev or "续前" in prev[:6]) else ""
    unit = ""
    mw = re.search(r"计量单位\s*[:：]\s*(\S+)$", work)
    if mw: unit = mw.group(1)
    sec = sec_tbl.get(tn)
    TABLES.append({"no":tn,"type":typ,"chapter":code,"codes":codes,"cont":cont,
                   "work":work[:160],"unit":unit,"rows":b["rows"],
                   "src_blk":i,"src_title":title if False else (sec["title"] if sec else "")})

# ---------- 质量取证 ----------
flags=[]
# 1 覆盖对账
import sqlite3
con = sqlite3.connect(r"file:C:/Users/Administrator/WorkBuddy/sp/quota-extract-sz05/out/quota_ln2024.db?mode=ro", uri=True)
db_codes={r[0] for r in con.execute("select item_code from items")}; con.close()
docx_codes={c for t in TABLES for c in t["codes"]}
missing=sorted(db_codes-docx_codes,key=lambda s:int(s.split("-")[1]))
extra=sorted(docx_codes-db_codes,key=lambda s:int(s.split("-")[1]))
n_space=sum(len(re.findall(r"\d+\.\s+\d", " ".join(" ".join(r) for r in t["rows"]))) for t in TABLES)
n_m3=sum(" ".join(" ".join(r) for r in t["rows"]).count("m3") for t in TABLES)
cont_tbls=[t["no"] for t in TABLES if t["cont"]]
no_work=[t["no"] for t in TABLES if t["type"]=="子目表" and not t["work"] and not t["cont"]]
# 子目首表缺基价行
no_jijia=[]
for t in TABLES:
    if t["type"]=="子目表" and not t["cont"]:
        if not any(("基" in c and "价" in c) for r in t["rows"][:8] for c in r[:3]):
            no_jijia.append(t["no"])

type_cnt = collections.Counter(t["type"] for t in TABLES)

meta = {
  "source_file": SRC, "source_size_bytes": 4671948,
  "source_sha256_12": sha,
  "source_core_props": "docx 模板占位（title=标题/creator=作者，创建 2025-07-08）",
  "extracted_at": "2026-10-14", "extract_tool": "python-docx 1.2.0 本地只读提取",
  "volume": "辽宁省建设工程计价依据·市政工程定额 第五册 市政管网工程 (0405)",
  "effective": "2025-05-01 起执行（通知第一条，blk4）",
  "coverage_check": {"db_items": len(db_codes), "docx_codes": len(docx_codes),
                     "missing": missing, "extra": extra},
  "type_counts": dict(type_cnt),
  "para_count": d["n_paras"], "table_count": d["n_tables"], "image_count": d["n_images"],
  "index_built_at": "2026-10-14",
}

INDEX = {"meta": meta, "front": front, "chapters": CHAPTERS, "tables": TABLES}
json.dump(INDEX, open(DST + r"\docx_index.json","w",encoding="utf-8"), ensure_ascii=False)

print("sha12:", sha)
print("章:", [(c["code"], len(c["notes"]), len(c["rules"]), len(c["sections"]), len(c["sections"]) and sum(len(s['tables']) for s in c['sections'])) for c in CHAPTERS])
print("表类型:", dict(type_cnt))
print("覆盖: db", len(db_codes), "docx", len(docx_codes), "缺", len(missing), "增", len(extra))
print("数值空格:", n_space, "m3:", n_m3, "续前:", len(cont_tbls), "子目表无前导:", len(no_work), no_work[:15])
print("子目首表缺基价行:", len(no_jijia), no_jijia[:15])
# 存取证数据供报告用
json.dump({"n_space":n_space,"n_m3":n_m3,"cont_tbls":cont_tbls,"no_work":no_work,
           "no_jijia":no_jijia,"type_cnt":dict(type_cnt),"missing":missing,"extra":extra},
          open(DST + r"\_flags.json","w",encoding="utf-8"), ensure_ascii=False)

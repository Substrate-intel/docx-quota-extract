# -*- coding: utf-8 -*-
"""卷参数残留扫描器（防混用守卫）—— docx-quota-extract skill v1.1+

用途：新卷开工时，把 skill scripts/ 复制到【卷工作目录】并替换卷参数后，
运行本脚本扫描工作副本中的旧卷（sz05 基准卷）特征残留。零残留才允许开工。

用法：
  python check_volume_params.py <卷工作目录的scripts路径>   # 扫描工作副本
  python check_volume_params.py <目录> --allow 模式名       # 豁免某检查项（须在 CHANGELOG 说明理由）

退出码：0=零残留可开工；1=存在残留，逐条列出后拒绝开工。

设计原则：
  - skill 目录内的原版脚本永远保留 sz05 默认值（作为参考实现基准），本脚本只扫【工作副本】；
  - 检查项覆盖六类硬编码：路径/文件名、sha12 锚定、册码与章码正则、页码偏移、
    数量断言、卷特有记录 ID 与文案；
  - CHECKS 可按卷扩展：新卷沉淀出的新检查项应回写 skill（见 references/iteration-protocol.md）。
"""
import re
import sys
import os

# ---------- 检查项清单（基准卷 sz05 特征；新卷发现新形态的检查项请回写 skill） ----------
# 每项：(模式名, 正则, 类别, 说明)
CHECKS = [
    # ① 路径与文件名（sz05 卷目录 / 脚本目录 / 源 docx 文件名）
    ("path_sz05_dir",   r"quota-extract-sz05",            "路径", "sz05 成果目录路径"),
    ("path_out_org",    r"out_organize",                  "路径", "sz05 脚本目录路径"),
    ("path_src_docx",   r"1773818587204558",              "路径", "sz05 源 docx 文件名"),
    ("path_template",   r"sp\\+template\.html|web[/\\]template\.html.*sz05", "路径", "模板路径残留"),
    # ② sha12 锚定（新卷必须换成新源文件的 sha256 前 12 位；保留 assert 但换值）
    ("sha12_sz05",      r"6008b61e81de",                  "sha锚定", "sz05 源文件 sha12"),
    # ③ 册码与章码（0405 册码 / 5- 章码正则 / 定额编号前缀）
    ("vol_code_0405",   r"0405(?!\d)",                    "册码", "册码 0405（含 040501-R-02 等 ID 前缀）"),
    ("code_re_5dash",   r"\\b5-\\d|5-\\s\*|5-\\\\s\*",   "章码正则", "定额编号 5- 前缀正则"),
    ("code_prefix_5",   r"[\"']5-[A-Za-z0-9]",            "章码字面", "5-xxx 字面编码"),
    # ④ 页码偏移（sz05 口径 +15；新卷必须替换为本卷偏移或参数化）
    ("offset_plus15",   r"\+\s*15\b",                     "页码偏移", "物理页=印刷页+15"),
    ("offset_field",    r"\"offset\":\s*15",              "页码偏移", "meta.offset=15"),
    # ⑤ 数量断言（sz05 卷规模；新卷须按本卷实测改断言）
    ("count_items",     r"==\s*3014\b|\b3014\b.*items|items.*\b3014\b",  "数量断言", "子目数 3014"),
    ("count_toc257",    r"==\s*257\b",                    "数量断言", "目录行数 257"),
    ("count_desc175",   r"==\s*175\b|!=\s*175\b",         "数量断言", "条文记录数 175"),
    ("count_desc152",   r"==\s*152\b",                    "数量断言", "条文数 152"),
    ("count_h_pass",    r"\b2997\b|\b2238\b|\b868\b",     "数量断言", "H2/H3/H4 sz05 pass 计数"),
    # ⑥ 卷特有记录 ID 与文案（附表源定位 / 单位修正表 / 卷标题）
    ("fb_anchor_ids",   r"040501-R-02|040502-N-05",       "附表锚点", "sz05 附表源记录 ID（附表定位整段须按本卷重写）"),
    ("unit_fix_table",  r"5-626|5-624|5-627|5-470|5-471|5-472", "单位修正", "sz05 单位修正清单编码"),
    ("vol_title_text",  r"市政管网|市政五册|第五册 市政管网", "卷文案", "sz05 卷标题文案"),
    ("h1_scope_codes",  r"5-133~141|5-396~399|5-430~435|5-1015~1020", "卷特有", "sz05 待复核区段编码"),
]

SKIP_FILES = {"check_volume_params.py"}   # 本脚本自身不扫


def scan(scripts_dir, allow=None):
    allow = set(allow or [])
    findings = []
    for fn in sorted(os.listdir(scripts_dir)):
        if not fn.endswith(".py") or fn in SKIP_FILES:
            continue
        path = os.path.join(scripts_dir, fn)
        with open(path, encoding="utf-8") as f:
            for ln, line in enumerate(f, 1):
                for name, pat, cat, desc in CHECKS:
                    if name in allow:
                        continue
                    if re.search(pat, line):
                        findings.append((fn, ln, name, cat, desc, line.strip()[:80]))
    return findings


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow = []
    if "--allow" in sys.argv:
        i = sys.argv.index("--allow")
        allow = [x.strip() for x in sys.argv[i + 1].split(",")] if i + 1 < len(sys.argv) else []
    if not args:
        print("用法: python check_volume_params.py <卷工作目录的scripts路径> [--allow 模式1,模式2]")
        sys.exit(2)
    scripts_dir = args[0]
    if not os.path.isdir(scripts_dir):
        print("❌ 目录不存在:", scripts_dir)
        sys.exit(2)
    findings = scan(scripts_dir, allow)
    if not findings:
        print("✅ 卷参数零残留（检查项 %d 类）—— 允许开工" % len(CHECKS))
        sys.exit(0)
    print("🔴 检出 %d 处旧卷参数残留，禁止开工（逐条替换后再扫描）：" % len(findings))
    seen = set()
    for fn, ln, name, cat, desc, line in findings:
        key = (fn, ln, name)
        if key in seen:
            continue
        seen.add(key)
        print("  %s:%d [%s/%s] %s" % (fn, ln, cat, name, desc))
        print("      → %s" % line)
    cats = sorted({f[3] for f in findings})
    print("\n残留类别: %s\n如确认某检查项在本卷语境合法，可用 --allow <模式名> 豁免并记录理由。" % ", ".join(cats))
    sys.exit(1)


if __name__ == "__main__":
    main()

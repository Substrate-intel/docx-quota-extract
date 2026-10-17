---
name: docx-quota-extract
description: 定额/规范类 docx 原件 → 结构化数据库 + 前端章节树的确定性提取管线（辽宁省2024定额 sz05 全书 3014 子目验证定版；v1.3.0 起含 md 源变体，适用于只有无水印 PDF、无 docx 源的卷，lvse 绿色建筑卷 487 子目验证）。当用户拿到无水印 Word 版定额（或类似表格密集型工程标准文档）、需要提取定额子目/说明/计算规则/目录并落库、核验、建前端时使用本 skill；docx 提取已裁定为**主力提取方案**（相对 PDF 提取：无字体基线漂移、表格结构天然保真、token 消耗低）。触发词：docx 提取、Word 版结构化、定额子目提取、双源对齐、造价逻辑核、PDF 转 markdown 后结构化提取。
agent_created: true
version: 1.5.2
---

# docx-quota-extract：定额 docx → 结构化库 确定性提取管线

## Overview

把 Word 版定额原件一步到位提取为：保真层 JSON → 子目结构化（SQLite 17 表模式）→ 条文/目录每条一记录（向量索引用）→ 与 PDF 版字节级对齐 → 造价逻辑核验 → 前端章节树 → 九门门控。全程**确定性可复现**（字节级，基线指纹锚定 source sha256），疑点一律留痕、禁静默修正。

**经辽宁2024市政第五册全书验证**：3014 子目 / 257 目录行 / 175 条文记录（含 23 附表）双源逐格对账 cell_diff=0，端到端重跑字节级复现。

## 使用纪律（防参数混用，机械强制）

1. **复制改造，禁直接运行**：skill 目录内脚本保留 sz05 基准卷参数（约 40 处硬编码，含数量断言/编码正则/附表源定位）。新卷开工 = 复制 scripts/ 到卷工作目录 → 按 `references/volume_params.md` 替换点地图逐项换参 → 跑 `scripts/check_volume_params.py <工作目录>/scripts` **零残留（退出码 0）才开工**。
2. **三类高危混用点**（漏改后果最重）：数量断言（门控恒红）、编码正则前缀（**静默错配**）、align_desc 附表源定位段（整段按本卷重写，每卷附表清单不同）。
3. **sha12 断言保留**：`assert sha12 == "<新卷源文件sha12>"` 是防串源的护身符，换值不删行。

## 迭代协议（skill 自我进化，每卷收官强制执行）

每卷门控全绿后，**禁止"用完就走"**：按 `references/iteration-protocol.md` 执行强制回写清单（新坑入 pitfalls、新检查项入扫描器、新参数形态入地图）+ 三件准入制（根因/根治/验证证据，禁只记症状）+ bump 版本记 CHANGELOG。跨用户使用者的迭代按回流协议（git PR 或 zip+CHANGELOG）回到作者处合并，作者按审核 checklist 把关。**这一节是 skill 的一部分，对任何使用它的实例同等生效。**

## 核心原则（违反即返工）

1. **docx 优先为主力提取源**：字体基线漂移类缺陷（PDF 版 E-BZ 下沉 7.7pt 根因）天然不存在；表格为结构化 rows/cols，免坐标拼装。
2. **保真层只读**：`docx_extract_full.json` 是唯一事实源；一切语义修正走 overlay/留痕字段（`*_raw` 后缀），不回改保真层。
3. **确定性复现**：所有产物禁运行时时间戳（禁 `generated_at`），锚定 source docx 的 sha256 前 12 位；有意变更后须 `gate.py --make-manifest` 刷基线再复核。
4. **疑点留痕不静默**：任何差异/残余/跳过必须进 log/DB 留痕表并过门控对账，禁止静默去重、静默修正、静默丢弃。
5. **双源对齐口径**：有 PDF 版库时，记录边界/规整文本/页码以 PDF 库为骨架（字节级），docx 原文做**字符级切片留痕**（`text_docx_raw`）。

## 管线总纲（十阶段，顺序执行）

```
extract_docx → parse_items → build_index → align_to_pdf(如有PDF库) → finalize
→ cost_check → parse_desc → align_desc → build_docx_front_pdf_style → gate
```

**md 源变体（v1.3.0，lvse 验证）**：只有官方无水印 PDF、拿不到 docx 源的卷，走
`scripts/md_source/` 变体（convert 转换层 + extract_md 链，无 align 阶段，双源锚定：
提取 nowm/校验官方 wm），成果契约与本管线完全对标。详见 `scripts/md_source/README.md`
与 `references/pitfalls.md` 坑 25-33。选型：**有 docx 源必走 docx 链**。

| # | 脚本（scripts/） | 职责 | 关键验收 |
|---|---|---|---|
| 1 | extract_docx.py | 保真层：iter_block_items 全量段落+表格，禁语义过滤 | 块数=原文块数；sha12 锚定 |
| 2 | parse_items.py | 子目解析：**列=子目、行=费用/消耗**，行首字分类（基/其=费用行，人/材/机=消耗行），续前链继承，三刀根治工作内容 | 子目数与书印连续编号零缺失；unit/work 零空 |
| 3 | build_index.py | 章节索引：notes/rules 止于首节标题；subs 容忍「工作内容」粘连段 | 与目录层集合全等 |
| 4 | align_to_pdf.py | 子目名称/单位/工作内容与 PDF 库字节级对齐，`*_docx_raw` 留痕 | 对账 N/N 零缺失零新增 |
| 5 | finalize.py | SQLite 落库（items/labors/materials/machines/toc/desc_rules/desc_docx_extra） | 行数=json 计数 |
| 6 | cost_check.py | H1 恒等式±0.02 / H2 单价聚类 / H3 机械费=Σ台班×价 / H4 材料费 / H5 量纲 / H6 结构 / P1 原版 PDF 取证 | H1/H6/P1 fail=0 |
| 7 | parse_desc.py | 目录（**document.xml 段落流穿透 w:sdt**）+ 说明/规则按「条」切分（续行直拼/子项换行/内嵌表拍平），产 `*_raw.json` 中间产物 | 目录每行有页码、章内单调 |
| 8 | align_desc.py | 条文层与 PDF 库 sections 一一同构对齐；宽容链归一 + `norm_index_map` 切片 + 附表逐格（cell_permute 判 PDF 交错） | 152/152 或 175/175 全命中 diff=0 |
| 9 | build_docx_front_pdf_style.py | 前端：复用 PDF 版 template.html，`/*__DATA__*/null` 注入；卷自适应 | 冒烟锚点全绿 |
| 10 | gate.py | 九门门控 + 基线指纹（--make-manifest）+ 端到端重跑验证 | 九门全绿 + 字节级复现 |

## 详细工作流

### 阶段 0：新卷预检（1 小时收官模板）

- 计算源 docx sha256 前 12 位；确定册结构（册说明/章/节/子目/附表边界）。
- **页码口径**：docx 无页码时，子目页码锚定原书物理页（与 PDF 版对账一致）；目录行页码按卷偏移换算。
- 全自测扫描：逐脚本跑通再放大，禁止边放大边改。

### 阶段 1：保真层（extract_docx.py）

- python-docx `iter_block_items` + `qn`，段落与表格按文档序全量落块。
- **⚠️ 最大坑：Word 目录/自动编号常包于 `w:sdt` 内容控件，python-docx 块级迭代（body 直接子元素）整体跳过**。目录恢复须直接正则解析 `document.xml` 段落流（`<w:p` + 全 `<w:t>` 串联），见 parse_desc.py。
- 表格存 `rows`（二维字符串数组），保真层不做任何清洗。

### 阶段 2：子目解析（parse_items.py）——本管线最核心认知

**定额表结构 = 列=子目、行=费用/消耗**（与直觉相反）：

- 定额编号行（`5-xxxx`）定位列 → 每列一个子目；
- 行首字分类判定：`基`=基价行、`其`=其他（综合费等）费用行；`人/材/机`=消耗行——**禁用表头开关式状态机**（续前表无「名称/消耗」表头行，开关式整批丢行）；
- 续前链：跨页续表靠 `chain_unit`/`chain_work` 继承上一表上下文；
- **工作内容三刀根治**：①组首工作内容段隔表不可达→跳表回溯（跳过中间表+续前段，节标题停）②少数排表后③书印「同前」承接→级联展开（清洗须同时去「工作内容:」前缀**和「计量单位:」后缀**，漏后缀则展开静默失效）；
- 机械规格数字核防污染：规格串含数字（如 `10m3/min`）时禁朴素数字抽取（会变 `103` 撞错价档），用三级匹配（全数字→前导整数→唯一前缀）。

### 阶段 3：索引与目录（build_index.py + parse_desc.py）

- rules 区**必须止于 sections[0].blk**，否则节标题混入规则条目；
- 子项目录行容忍「工作内容」粘连段：`t_sub = re.split(r'工作内容\s*[:：]', t)[0]`，去空白计长 ≤30；
- **目录层是权威反证源**：目录子目行集合 vs 正文索引 subs 集合必须全等；目录多出的行=正文漏采（sz05 救回 4 条）；
- 孤儿页码行：源 docx 个别目录项标题与页码 `(NNN)` 拆成两段→纯页码行回填前一条并重排序号。

### 阶段 4：对齐层（align_to_pdf.py / align_desc.py）

- 有 PDF 版库时：**PDF 库为骨架**（记录边界/文本/页码字节级），docx 原文留痕；
- 宽容链归一集（字符级 1:1 映射）：全角标点→半角、`²→2 ³→3 ×→x ∶→:`、`ϕ/φ→φ`、全角引号删除、去空白；
- **切片必须用 `norm_index_map`（norm→链下标严格映射）**——直接把 norm 字符串下标当链下标用会因空白/删除字符占位而整体漂移；
- 附表逐格对账：`full_cell_equal` / `cell_permute`（字符多重集 sorted 相等→证明 PDF 双列交错提取序差而非内容差）/ `cell_diff`（必须=0）；
- 附表锚点须**精确纯表题匹配且取最后一个命中段**（目录行「材料预算价格取定表……(809)」带省略号页码，从头扫会错取子目表）；
- 表体拍平差异（PDF 表直拼 vs docx「〔内嵌表〕」标记）：引子前缀贪心匹配 + 双尾巴留痕；docx 残余文本进 `desc_docx_extra` 表，不丢弃。

### 阶段 5：核验（cost_check.py）

- **校核≠重做**：核验只交付取证+缺陷清单，修复走独立门控工序；
- H1 恒等式 `基价 = 人工+材料+机械` ±0.02——None 一律 `(l or 0)`，禁把 None 当 0 跳过或混用；
- H3/H4 中 unpriced（括号未计价主材 `(100.000)`）跳过并留痕 `is_unpriced=True`；「其他材料费」直计不乘消耗；
- P1 原版 PDF 取证：`item_code+基价` 在对应页文本命中；页码 **1 起算**（`doc[p-1]`）；编码判定用原始文本数字边界 `(?<!\d)5-\s*N(?!\d)` 防「5-15-2」粘连误杀。

### 阶段 6：落库/前端/门控（finalize + build_docx_front + gate）

- SQLite 表：items/item_labors/item_materials/item_machines/toc/desc_rules/desc_docx_extra/check_summary；
- 前端复用既有 PDF 版 template.html（DATA 契约注入），**分卷自适应**：读 DATA.meta 动态生成，null 安全降级，冒烟锚点分卷适配（照搬他卷锚点=没跑）；
- 九门门控：覆盖对账/恒等式/P1/DB 行数/目录条文对齐/附表逐格/基线指纹；**门8 基线失配的文件必须逐个确认是有意变更**才能刷指纹；
- 端到端重跑全部阶段 → 基线指纹全一致 → 字节级复现验证。

## 验收基准（一个卷收官的定义；计数以本卷实测为准，下列数字为 sz05 基准示例）

- 子目连续编号零缺失、unit/work 零空、H1/H6/P1 fail=0；
- 目录行级形态：每行有页码、章内单调、与正文集合全等（sz05 基准：257 行）；
- 条文记录与 PDF sections 全量同构、text 字节级全等、diff=0、附表 cell_diff=0（sz05 基准：175 条）；
- 九门全绿 + 端到端重跑字节级复现 + 前端冒烟全过。

## 成果回流与悬赏协同（metal 站接单场景）

提取成果回流全国库（`china-quota-volumes` 双仓）→ webhook 自动协同 → 悬赏自动核销发分，
接单者 8 步闭环见 `references/contribution.md`（md 源卷与 docx 卷通用）。要点：db 不走
公开仓 PR（收私有仓+sha256 门禁）、官方源永不回流（版权）、九门全绿才有提 PR 资格。

## Resources

### scripts/（sz05 全书验证过的参考实现，须按卷参数化适配）

脚本内 DST/SRC 路径、章码、页码偏移、正则锚点均为 sz05 卷参数，新卷必须按 `references/volume_params.md` 替换并过 `check_volume_params.py` 扫描。

### references/

- `pipeline.md`：十阶段管线详解（各阶段输入/输出/验收/复用要点）
- `pitfalls.md`：**全部踩坑清单**（20 坑，含根因与根治代码要点）——新卷开工前必读，可按坑名 grep
- `volume_params.md`：逐脚本卷参数替换点地图 + 三类高危混用点
- `iteration-protocol.md`：迭代协议（强制回写清单/三件准入制/版本管理/跨用户回流与作者审核）

### CHANGELOG.md

版本历史（语义化版本 + 来源标识 + 验证状态）；任何迭代必须先读后记，作者合并前过审核 checklist。

# 十阶段管线详解（输入/输出/验收/复用要点）

> 脚本均为 sz05 卷（辽宁省2024市政第五册，3014 子目）验证版；新卷须逐项替换卷参数：DST/SRC 路径、章码前缀（如 `5-`）、页码偏移、条目正则、材料/机械价格源、册结构特征。替换后先全自测再放大。

## 数据流总图

```
source.docx ──(1)extract_docx──> docx_extract_full.json [保真层·只读]
      │
      ├─(2)parse_items──> docx_items.json          ┐
      ├─(3)build_index──> docx_index.json          │ 子目层
      ├─(4)align_to_pdf─> docx_items.json(对齐版)  ┘ + alignment_log.json
      │
      ├─(7)parse_desc──> docx_toc.json + docx_desc_rules_raw.json [docx视角中间产物]
      ├─(8)align_desc──> docx_desc_rules.json(对齐版) + desc_align_log.json
      │
      ├─(5)finalize──> docx_quota.db (items/labors/materials/machines/toc/desc_rules/desc_docx_extra)
      ├─(6)cost_check──> cost_check_report.json
      ├─(9)build_docx_front──> index.html (template 注入 DATA)
      └─(10)gate──> manifest.json (基线指纹) → 九门全绿
```

## 阶段 1｜extract_docx.py —— 保真层

- **输入**：源 docx（先算 sha256 前 12 位作全链锚）。
- **输出**：`docx_extract_full.json`：`{"meta": {sha12, n_blocks}, "blocks": [{type: para|table, text, style, table_no, rows(表格)}...]}`。
- **要点**：
  - `iter_block_items(doc)` + `qn` 遍历 body 直接子元素，段落+表格按文档序；
  - **w:sdt 不可见**（坑1）——保真层可不含目录，目录在阶段 7 由 document.xml 段落流单独恢复；
  - 表格 rows 二维字符串数组原样保存，零清洗。
- **验收**：块数稳定、表格 rows 非空、sha12 锚定；重跑字节级一致。

## 阶段 2｜parse_items.py —— 子目解析（最核心）

- **输入**：保真层 json。
- **输出**：`docx_items.json`：`{item_code: {name, unit, work_content, base_price, labor_cost, material_cost, machine_cost, labors[], materials[], machines[], *_docx_raw(留痕)}}`。
- **结构认知**：定额表 = **列=子目、行=费用/消耗**。定额编号行 `5-xxxx` 定位列；行首字分类：`基`→基价、`其`→综合费等费用行；`人/材/机`→消耗行（坑4/5：禁表头开关式状态机）。
- **三刀根治工作内容**（坑8/9）：①组首工作内容段隔表不可达→跳表回溯 ②排表后形态 ③「同前」级联展开（清洗去前缀+计量单位后缀）。
- **防污染**：机械规格三级匹配（坑6）、单位沿用仅限续前链（坑7）。
- **验收**：子目编号连续零缺失；unit/work 零空；`同前`残留 0；H1 预跑全过。

## 阶段 3｜build_index.py —— 章节索引

- **输出**：`docx_index.json`：`{front:[发布通知/总说明/册说明], chapters:[{code, title, anchor_blk, notes[], rules[], sections:[{title, blk, subs[], tables[]}]}]}`。
- **要点**：rules 区止于 sections[0].blk（坑10）；subs 容忍「工作内容」粘连段（坑11，去空白计长≤30）。
- **验收**：subs 集合与目录子目行集合全等（目录反证，阶段 7 后复验）。

## 阶段 4｜align_to_pdf.py —— 子目层对齐（有 PDF 版库时）

- **输入**：docx_items.json + PDF 库（SQLite 只读，`?mode=ro` + uri）。
- **口径**：名称/单位/工作内容取 PDF 库规整值（字节级），docx 原文存 `*_docx_raw`；PDF 空值时 docx 保底。
- **验收**：对账 N/N 零缺失零新增；alignment_log.json 全量留痕。

## 阶段 5｜finalize.py —— SQLite 落库

- **表**：items / item_labors / item_materials / item_machines / toc / desc_rules / desc_docx_extra / check_summary。
- **验收**：门7 DB 对账（每表行数 = json 计数）；自测严禁在真实 out/ 写删（tempfile 隔离）。

## 阶段 6｜cost_check.py —— 造价逻辑核

| 项 | 逻辑 | 验收 |
|---|---|---|
| H1 | 基价 = 人工+材料+机械 ±0.02（`(l or 0)` 坑16） | fail=0 |
| H2 | 人工费反推单价聚类（离群留痕） | 离群留痕可解释 |
| H3 | 机械费 = Σ台班×价（未匹配 skip 留痕） | fail=0 |
| H4 | 材料费 = Σ消耗×价（unpriced 跳过；「其他材料费」直计） | fail=0 |
| H5 | 量纲可疑扫描 | 留痕 |
| H6 | 结构完整性（基价/单位/工作内容/人材机） | 全零 |
| P1 | 原版 PDF 取证：编码+基价页文本命中（`doc[p-1]`、数字边界正则，坑17） | N/N |

## 阶段 7｜parse_desc.py —— 目录 + 条文每条一记录（docx 视角）

- **目录**：document.xml 段落流穿透 w:sdt（坑1）；行级分类（章/说明/规则/节/子目/附录）；孤儿页码行回填（坑2）；每行带印刷页+物理页（卷偏移）。
- **条文**：按「条」切分（`一、二、…` 条号锚），合并规则：
  - 折行续行**直拼**（前段以标点/汉字结尾且后段非子项/单位行）；
  - 子项（`1.`）/单位行**换行**追加；
  - 前段以 ASCII 字母数字结尾（如 `1.6MPa`）→ 判档位并列行**换行**；
  - 内嵌表拍平为「〔内嵌表 N〕」标记 + 结构化表留痕。
- **输出**：`docx_toc.json` + `docx_desc_rules_raw.json`（中间产物，防对齐版被重建链覆盖）。
- **验收**：目录每行有页码、章内单调；条文条号连续、条首自含；**全量直拼点目检**（枚举每条内相邻块直拼点逐个人工核验，sz05 仅 2 处且均真折行）。

## 阶段 8｜align_desc.py —— 条文层对齐 PDF 库 sections

- **骨架**：PDF 库 sections 为准（记录边界/文本/页码字节级）；152 条文（册说明21=总说明+册说明合并口径/章节说明86/计算规则45，子项单列）+ 23 附表 = 175 全量同构。
- **宽容链**：build_chain(text)（字符→(char, start, end) 三元组链）+ 归一（坑14 归一集）→ 在 docx 条文中 find PDF 条 norm 串 → **norm_index_map** 切片原文（坑13）。
- **附表逐格**：docx 表 rows vs PDF tables 逐格归一比对；`full_cell_equal` / `cell_permute`（sorted 多重集）/ `cell_diff`（=0）。
- **align_status 分级**：equal(逐字节) / norm_equal(去空白) / loose_equal(字形) / table_flat_diff(引子等+双尾巴留痕) / diff(=0 必须)。
- **验收**：175/175 全命中、diff=0、docx 残余全留痕（desc_docx_extra 表）。

## 阶段 9｜build_docx_front_pdf_style.py —— 前端

- 复用 PDF 版 `web/template.html`，读 DATA 渲染；`html.replace('/*__DATA__*/null', json)` 注入。
- **DATA 契约**：meta/stats/chapters/nodes/sections(175 每条一记录，附表带 tables JSON)/toc(257)/items/details。
- **分卷自适应**（坑19）：读 DATA.meta.offset/toc_pages 动态生成标题与目录；null 安全降级（labor_tiers 等）。
- **验收**：分卷冒烟锚点集全绿（每卷写自己的锚点，禁照搬）。

## 阶段 10｜gate.py —— 九门门控 + 基线指纹

| 门 | 内容 |
|---|---|
| 1 | 保真层存在 + sha12 锚定 |
| 2 | 子目数/结构对账 |
| 3 | 对齐留痕完备 |
| 4 | 覆盖对账（docx ↔ PDF 库） |
| 5 | H1 恒等式 / P1 取证 fail=0 |
| 6 | H2-H6 核验汇总 |
| 7 | DB 行数对账（含 toc/desc_rules/desc_docx_extra） |
| 8 | 基线指纹（manifest.json，sha256 全清单文件；`--make-manifest` 刷） |
| 9 | 目录/条文双对账（集合/页码/单调 + 175 条字节级全等 + 附表逐格 cell_diff=0） |

- **收官动作**：门1-7/9 绿 → 刷指纹 → 复核九门全绿 → **端到端全链重跑 → 基线指纹全一致**（字节级复现）→ 冒烟 → 交付报告。
- 基线文件清单应包含全部可复现工件（json/db/html），有意变更后须确认失配文件逐个归属。

## 新卷标准动作（1-2 小时收官模板）

1. 预检：sha12、册结构、页码口径、目录行数预估；
2. 换卷参数（路径/章码/偏移/正则锚点/价格源）→ 逐脚本全自测；
3. 十阶段顺序跑 → 疑点逐条取证（禁静默）；
4. 九门全绿 + 刷指纹 + 端到端字节级复现；
5. 分卷冒烟 + 交付报告（覆盖清单+人工复核项）。

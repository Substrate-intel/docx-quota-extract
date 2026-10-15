# md 源管线参考实现（lvse·绿色建筑卷验证版，v1.3.0）

> 适用场景：**有官方无水印 PDF、但拿不到 docx 源**的卷。PDF→md 转换层 + md 解析层，
> 成果对标 docx 版输出契约（lvse_quota.db schema 同构 sz05 docx_quota.db + src_page 列，
> 前端复用 sz05 web/template.html 注入链，九门门控同构）。
> 基准卷：辽宁2024《绿色建筑工程定额》269 页 / 487 子目（20-1~20-487）/ 目录 77 行 /
> 条文 53 条 / 九门全绿 + 端到端重跑字节级复现 + P1 官方原版取证 487/487（2026-10-15）。

## 数据流（与 docx 链的阶段对应关系）

```
nowm.pdf ──(0) convert_greenbuilding.py ──> source.md [含 <!-- Pn --> 页锚]
      │
      ├─(1) extract_md.py        ──> md_extract_full.json + md_index.json   [保真层]
      ├─(2) parse_items_lvse.py  ──> lvse_items.json                        [子目层]
      ├─(7) parse_desc_lvse.py   ──> lvse_toc.json + lvse_desc_rules.json   [目录/条文层]
      ├─(5) finalize_lvse.py     ──> lvse_quota.db
      ├─(6) cost_check_lvse.py   ──> cost_check_report.json（H1 四项制 + P1 对官方 wm 原版取证）
      ├─(9) build_front_lvse.py  ──> web/index.html  ← ⚠️ 必须 PDF 长键契约（坑 34）
      ├─(9b) smoke_front_lvse.mjs ──> 渲染级冒烟（node DOM stub：启动链+13 视图路由）
      └─(10) gate_lvse.py        ──> baseline_manifest.json（10 文件指纹 + 双源锚定）
```

**⚠️ 坑 34（v2 教训）**：build_front 必须产出 **PDF 版 template.html 的长键契约**
DATA（meta.book_name/stats.h/sections[].block_type/toc/items[].item_code+node_id/
details/validate/nodes/REVIEW 两源），**不是 docx 短键契约**——错配则首页永远「加载中」。
前端完成态=**渲染级冒烟全绿**（`node smoke_front_lvse.mjs`），文件产出不算完成。
卷适配硬编码点：itemPrefix（章码→子目前缀推导）→ 读 `DATA.meta.code_prefix`；
节印页 `-27` → `-DATA.meta.offset`；搜索示例/卡片副标题/标题按卷替换。

**与 docx 链的结构差异**：
- 无 align_to_pdf/align_desc 阶段——md 即权威提取源（docx 链需 PDF 库对齐；md 源没有 PDF 库）；
- 阶段 0（转换层）是新增前置：裸 fitz（**禁 pymupdf4llm**，坑 25），产出必须字节级可复现；
- 目录不走 md（md 表格化会破坏双栏坐标），由 parse_desc_lvse 从 nowm.pdf 的 P5-9 dict
  **双栏重组**直接重建（坑 31）；
- 双源架构：**提取用 nowm 干净源、校验用官方 wm 原版**（用户裁定口径），manifest 同时
  锚定两者 sha12 + convert 脚本 sha12。

## 卷参数替换点（lvse 实测，复制后必查）

| 脚本 | 参数点 | lvse 值 | 新卷动作 |
|---|---|---|---|
| convert_greenbuilding.py | SRC/OUT 路径 / 字号分级（19.7/13.7/10.3/8.8）/ 水印字符集 / 页码标定区间 | 绿色建筑卷全套 | 字号分级须按本卷字体实测重标；水印字符集按本卷水印文字重写；页码 offset 分区重标定 |
| extract_md.py | SRC md 路径 / OUT 两 json / 章码正则 `012\d{3}` / 表类型判别 | lvse 全套 | 章码正则按本卷册码改 |
| parse_items_lvse.py | 编码正则 `^20-\d{1,3}$` / 6位清单码 / 单位白名单 / 行判别阈值 | lvse 全套 | 编码前缀必改（高危：静默错配） |
| parse_desc_lvse.py | nowm.pdf 路径 / 目录物理页区间 / 双栏分界 x=280 / 章码正则 / 条文计数断言 | lvse 全套 | 双栏分界按本卷版式实测 |
| finalize_lvse.py | DST / source_file+sha12 / 卷名 / 表计数断言 | lvse 全套 | 断言按本卷实测 |
| cost_check_lvse.py | 官方 wm PDF 路径 / 编码正则 / 基价灵活正则 / H2 费率带宽 / H5 单位白名单 | lvse 全套 | H1 恒等式项数先按已知好卷校准（坑 32） |
| build_front_lvse.py | ROOT / 模板路径 / DATA 计数 / 冒烟锚点 | lvse 全套 | 模板可复用 sz05/web/template.html |
| gate_lvse.py | SRC_DB / 数量断言（487/77/53）/ 硬锚点 / manifest 文件清单 | lvse 全套 | 断言全按本卷实测 |

**使用纪律**：新 md 源卷只复制本目录 8 脚本到卷工作目录（勿混入上级 sz05 docx 脚本）；
`check_volume_params.py` 对 md_source 变体的检查基准=本目录文件（扫描前把 CHECKS 里的
sz05 基准值理解为"上一卷残留"，lvse 值同理——新卷复制后两者都是待替换残留）。

## 坑位速查（详见 references/pitfalls.md 坑 25-34）

- 转换层：pymupdf4llm 段错误 / 旋转水印 redact 整页抹除 / E-BZ 页码散字（坑 25/26）；
- md 解析层：章标题前缀剥离致 kind 判界失效（坑 27）/ 合并单元格形态差异（坑 28）/
  工作内容拆行双遍扫描（坑 29）/ 节标题跟表验证（坑 30）；
- 校验层：目录双栏重组（坑 31）/ H1 四项制（坑 32）/ P1 未去空白原文正则（坑 33）；
- 前端层：契约错配致「加载中」假死 + 渲染级冒烟（坑 34）。

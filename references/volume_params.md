# 卷参数替换点地图（新卷开工必查 + check_volume_params.py 机械复核）

> skill 目录内的脚本是 **sz05 基准卷参考实现**，永远保留 sz05 默认值。
> 正确使用姿势：**复制 scripts/ 到卷工作目录 → 逐项替换下表参数 → 跑 `check_volume_params.py` 零残留 → 才开工**。
> 禁止直接运行 skill 目录内脚本处理新卷（会把 sz05 参数混进新卷产物）。

## 逐脚本替换点（sz05 实测定位，2026-10-15 全量扫描）

| 脚本 | 参数点 | sz05 默认值 | 新卷动作 |
|---|---|---|---|
| extract_docx.py | SRC 源文件 / OUT 保真层路径 | Downloads/1773818587204558_nowm.docx → out_organize | 换新卷源路径与输出路径 |
| parse_items.py | DST 成果目录 / 章码前缀 / 续前链锚定正则 | docx_source；`5-` 编号 | 换路径；编码正则按本卷前缀 |
| build_index.py | SRC/EXT/DST 三路径 / 册码正则 `0405\d{2}` / 章码 `\b5-\d{1,4}\b` / 卷名元数据 | sz05 全套 | **册码与章码正则是必改项**（其他册是 04xx / N- 形态） |
| align_to_pdf.py | DST / DB（PDF 库只读 uri）/ source_anchor 文案 | sz05 全套 | 换路径与锚定文案 |
| finalize.py | DST / source_file+sha12 / 卷名 / **待复核区段编码（h1_scope 等 sz05 编码硬写进 findings 文案）** | sz05 全套 | **findings 文案里的编码区段须按本卷重写**，不可沿用 |
| cost_check.py | DST/OUT / 原版 PDF 路径 / PDF 库 uri / 编码数字边界正则 `(?<!\d)5-\s*N` / P1 页码口径 | sz05 全套 | 编码正则前缀按本卷改；页码 1 起算口径通常通用 |
| parse_desc.py | SRC/DST/EXT 三路径 / **`assert sha12 == "6008b61e81de"`（新卷必炸点，属防护性，须换新源 sha12）** / 物理页偏移 `pg + 15` / 条文切分锚（章号/节标题正则） | sz05 全套 | 换 sha12 断言值（保留断言！）；偏移按本卷口径（az10/az12=17、sz10=11…） |
| align_desc.py | ROOT / **docx 侧 ID 前缀 `startswith("0405"+ch)`** / **附表源定位整段（040501-R-02 井表、040502-N-05 螺栓6表、材料表题锚 max() 段）** / 条文计数断言 `assert len(records)==175` | sz05 全套 | **⚠️ 附表源定位段整段按本卷重写**（每卷附表清单完全不同）；计数断言按本卷 PDF 库 sections 实测值改 |
| build_docx_front_pdf_style.py | ROOT / 模板路径 / **单位修正清单（5-626 等 sz05 编码硬写）** / meta.offset=15 / 书名标题文案 / stats sz05 计数 / 章 start_page 偏移 `+15` | sz05 全套 | 单位修正清单按本卷单位存疑清单重建（若无可清空）；文案/偏移/计数全套替换 |
| gate.py | SRC_DB uri / 源文件 sha 文案 / **数量断言（门1/2/3 的 3014、门9 的 257/175）** / 硬对账锚点（首节行页 15/307/579/589） | sz05 全套 | 断言值全部按本卷实测改；锚点按本卷目录重算 |

## 三类高危混用点（历史上最容易漏改）

1. **数量断言**（gate/align_desc/finalize 里的 3014/257/175/152）：漏改 → 新卷门控恒红（危害=可见，能暴露）；
2. **编码正则前缀**（`\b5-\d`、`0405\d{2}`）：漏改 → **静默错配**（危害最大：他卷编码形态不同，正则匹配 0 条或错条，产物悄悄缺失）；
3. **align_desc 附表源定位段**：漏改 → KeyError 直接炸（危害=可见）。且该段本卷逻辑须重写，不可参数化——每卷附表清单是书结构，只能按卷侦察后重写。

## 机械复核（开工门）

```bash
# 复制并替换参数后，在卷工作目录执行：
python check_volume_params.py <卷工作目录>/scripts
# 退出码 0 = 零残留可开工；非 0 = 逐条列出残留，禁止开工
```

检查项六类：路径/文件名、sha12 锚定、册码与章码正则、页码偏移、数量断言、卷特有 ID 与文案。
新卷沉淀出的新检查项形态，须回写 skill 的 CHECKS 清单（见 iteration-protocol.md）。

## md 源管线变体（v1.3.0，lvse 实证）

**适用**：有官方无水印 PDF、无 docx 源的卷。参考实现与逐脚本参数表见
`scripts/md_source/README.md`（8 脚本：convert → extract_md → parse_items_lvse →
parse_desc_lvse → finalize_lvse → cost_check_lvse → build_front_lvse → gate_lvse）。

- **与 docx 链差异**：无 align_to_pdf/align_desc（md 即权威提取源）；新增阶段 0 转换层
  （裸 fitz，禁 pymupdf4llm）；目录由 parse_desc 从 nowm.pdf dict 双栏重建（不经 md）；
  **双源锚定**：提取用 nowm 干净源、P1 校验用官方 wm 原版，manifest 同锚两者 sha12 +
  convert 脚本 sha12。
- **高危混用点新增**：④ 转换层字号分级与水印字符集（漏改 → md 源本身错，下游全链带错）；
  ⑤ H1 恒等式项数（坑 32：三项式/四项制因卷而异，开工前用已知好卷校准）；
  ⑥ P1 正则输入文本口径（坑 33：必须未去空白原文）。
- **扫描纪律**：md 源卷工作目录只放 md_source 变体 8 脚本；check_volume_params 扫描时
  docx 链与 md 链的卷参数基准值互为"待替换残留"，任一残留都须清零才开工。

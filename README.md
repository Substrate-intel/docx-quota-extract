# docx-quota-extract

定额/规范类 Word（.docx）原件 → 结构化数据库的**确定性提取管线**。

经《辽宁省建设工程计价依据·市政工程定额》第五册（市政管网 0405）全书验证：
**3014 子目 / 257 目录行 / 175 条文+附表记录**，与 PDF 提取版双源逐格对账 cell_diff=0，
九门门控全绿，端到端重跑字节级复现。

## 核心能力

| 能力 | 说明 |
|---|---|
| 十阶段管线 | 保真层提取 → 子目解析（列=子目/续前链/同前级联）→ PDF 字节级对齐 → 造价逻辑核验（H1-H6+P1）→ 条文/目录每条一记录（向量索引用）→ 门控 → 前端章节树 |
| 防混用守卫 | `check_volume_params.py` 扫描旧卷参数残留（路径/sha12/章码正则/偏移/数量断言/卷特有 ID），**退出码 0 才允许新卷开工** |
| 自我迭代协议 | 每卷收官强制回写：新坑入 pitfalls（编号续接）、新检查项入扫描器、新参数形态入地图；三件准入制（根因 + 根治 + 验证证据，禁只记症状） |
| 版本管理 | 语义化版本 + `CHANGELOG.md` 来源标识 + git tag；外部迭代经 PR 回流，作者按审核清单合并 |

## 使用

- **总纲**：[SKILL.md](SKILL.md)
- **十阶段详解**：[references/pipeline.md](references/pipeline.md)（各阶段输入/输出/验收）
- **踩坑清单**：[references/pitfalls.md](references/pitfalls.md)（20 坑全清单：症状→根因→根治）
- **卷参数替换地图**：[references/volume_params.md](references/volume_params.md)（新卷开工必读）
- **迭代与回流协议**：[references/iteration-protocol.md](references/iteration-protocol.md)

WorkBuddy 用户：解压至 `~/.workbuddy/skills/docx-quota-extract/` 即可被自动发现；
其他 AI 助手（Claude Code / Codex 等）将本目录放入对应 skills 目录亦可。

新卷使用纪律：**复制改造、禁直接运行参考脚本**；sha12 断言换值不删行；换卷参数后先过
`check_volume_params.py`，全自测（含子目数、目录行数、对账锚点）再放大到全书。

## 版本

- **v1.1.0**：混用守卫扫描器 + 自我迭代协议 + 版本管理与回流机制
- **v1.0.0**：sz05 全书验证定版（十阶段管线 + 20 坑沉淀 + 10 参考脚本）

## 贡献（回流协议）

用本 skill 完成新卷后，请按 [iteration-protocol.md](references/iteration-protocol.md)
回写经验（三件准入制），以 PR 或 zip+CHANGELOG 形式回流；作者审核合并。

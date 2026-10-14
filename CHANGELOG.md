# CHANGELOG — docx-quota-extract

格式：`- 版本 | 日期 | 来源 | 变更摘要`；来源=贡献者标识/卷名；合并须经作者过审（iteration-protocol.md 第四节）。

## v1.2.0 · 2026-10-15 · 爪哥（作者）· sz01（市政第一册 土石方工程）卷验证回写

- **第二卷全链验证**：sz01 全册 258 子目（1-1~1-258 连续零缺失）/ 84 目录行 / 57 条文记录（总说明10/册说明7/章节说明22/计算规则17/附表1），九门全绿 + 端到端重跑字节级复现 + 前端冒烟 PASS；官方原版 PDF（132页）P1 取证 258/258；
- **新形态坑 4 条入 pitfalls**：坑21 目录 sdt 半泄漏污染章锚（册说明锚过滤根治）；坑22 附录区无条首显式成条；坑23 无 PDF 对照库时 P1 页映射内建法（编码+基价联合首中页）；坑24 portal docx_quota 卷型适配；
- **卷参数差异实测补充**：offset 13（三点验证法：册说明/计算规则/附表 TOC 页 ↔ 物理页）；章码正则 `0401\d{2}`/`^1-\d{1,3}$`；册级说明/规则（章内无说明）→ build_index notes/rules 恒空 + parse_desc 册级成条（front.sm/gcl）；无 align 阶段 → desc 终版由 parse_desc 直产（docx_native 口径）+ docx_extra.json 替代 desc_align_log；
- **check_volume_params 豁免先例**：跨卷只读引用（模板复用/省统一价格库）用 --allow path_sz05_dir 豁免并在交付报告记录理由；
- align_to_pdf/align_desc 不适用卷从工作副本删除（保留 skill 原版参考实现）。

## v1.1.0 · 2026-10-15 · 爪哥（作者）· sz05 基准卷收官回写

- 新增 `scripts/check_volume_params.py`：卷参数残留扫描器（防混用守卫，六类 17 项检查，自测对参考原版检出 85 处/11 类全覆盖）；
- 新增 `references/volume_params.md`：逐脚本参数替换点地图（10 脚本 × sz05 硬编码全清单，三类高危混用点标注）；
- 新增 `references/iteration-protocol.md`：强制回写清单 + 迭代三件准入制（根因/根治/验证证据）+ 语义化版本 + 跨用户回流协议与作者审核门槛；
- 新增 CHANGELOG.md（本文件）：版本历史与来源标识；
- skill 目录 git 化：`git init` + tag `v1.1.0`；
- 动机：作者识别三类风险——①脚本 sz05 参数硬编码约 40 处，复制即混用；②skill 无自我迭代机制，新卷经验流失；③无版本管理，跨用户使用后迭代无法回流。

## v1.0.0 · 2026-10-15 · 爪哥（作者）· 初始版本

- 初始管线：SKILL.md（十阶段总纲）+ references/pipeline.md + references/pitfalls.md（20 坑）+ scripts/（sz05 验证 10 脚本参考实现，约 2000 行）；
- 基准：辽宁2024市政第五册（sz05）全书 3014 子目 / 257 目录行 / 175 条文+附表 cell_diff=0 / 九门全绿 / 字节级复现；
- 打包验证：13 文件全合规（package_skill.py）。

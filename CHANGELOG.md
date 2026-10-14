# CHANGELOG — docx-quota-extract

格式：`- 版本 | 日期 | 来源 | 变更摘要`；来源=贡献者标识/卷名；合并须经作者过审（iteration-protocol.md 第四节）。

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

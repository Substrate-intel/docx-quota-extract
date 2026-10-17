# CHANGELOG — docx-quota-extract

格式：`- 版本 | 日期 | 来源 | 变更摘要`；来源=贡献者标识/卷名；合并须经作者过审（iteration-protocol.md 第四节）。

## v1.5.2 · 2026-10-17 · 爪哥（作者）· 悬赏自动发分加「交付记录硬门槛」（同步 md-quota-extract v1.8.2）

- 用户裁定：**必须有 QuotaSubmission 交付记录才自动发分**（杜绝「他人交付、认领人领分」的不可逆错配）；
- contribution.md 第 8 条补硬门槛四判据（bountyId 归属 / account==claimBy / 非 rejected / 有实体凭据）+ 五个原因码（no-submission / submission-not-from-claimer / submission-rejected / submission-empty / no-claimer）+ 人工核销端点同口径拦截（admin 例外 force=true+reason 留痕）。

## v1.5.1 · 2026-10-17 · 爪哥（作者）· 悬赏回流自动核销（同步 md-quota-extract v1.8.1）

- references/contribution.md 第 8 条同步新口径：协同升级为 verified→settled **自动发分**（points.earn pool='bounty' 幂等；QUOTA_AUTO_SETTLE=off 留人工闸）+ 匹配三通道（targetVol 精确绑卷 / 文本窗口 / 关键词实体，价格册与消耗量册互斥）；
- SKILL.md frontmatter version 补正 1.1.0→1.5.1（历史遗留未随 CHANGELOG 升版）。

## v1.5.0 · 2026-10-15 · 爪哥（作者）· 补成果回流与 metal 悬赏协同协议（与 md-quota-extract v1.1.0 同步）

- **缺口**：skill 只有自身迭代回流，未覆盖「提取成果回流全国库 → metal 站悬赏自动核销」的接单者闭环；
- **新增 `references/contribution.md`**（与 md-quota-extract 同源，交叉引用适配）：悬赏接单者 8 步闭环、PR 内容纪律（db 不入公开仓 PR、官方源永不回流）、维护者双仓入库操作、悬赏自动核销口径（open→closed / claimed|submitted→verified 待发分）；
- SKILL.md 增「成果回流与悬赏协同」节引用。

## v1.4.0 · 2026-10-15 · 爪哥（作者）· lvse 前端契约错配修复回写（用户实证反馈）

- **用户报告**：绿色建筑卷成果库首页永远「加载中…」——门控全绿但前端假死；
- **根因（坑 34）**：md_source 参考实现 v1 的 build_front_lvse 产出 docx 短键契约 DATA，与 PDF 版 template.html 渲染契约错配（`DATA.stats.h`/`DATA.sections.some` 相继 TypeError）；冒烟只验文件未验渲染（坑 19 高阶形态）；
- **build_front_lvse.py v2**：按 sz05 docx 版 build_docx_front_pdf_style.py 成熟契约映射重写（stats/sections/toc/items 长键/details/validate/nodes/REVIEW 两源全套）；卷适配点显式替换（itemPrefix→读 meta.code_prefix、节印页 -27→-meta.offset、搜索示例/卡片副标题/标题全套）；
- **新增 smoke_front_lvse.mjs**：渲染级冒烟机械化（node + 最小 DOM stub 执行内联脚本：启动链零异常 + main 非「加载中」+ 13 视图路由真跑），前端完成态=渲染级冒烟全绿；
- 验证：冒烟 22/22；端到端重跑字节级一致；门控 8 绿→刷指纹→九门 9/9。

## v1.3.0 · 2026-10-15 · 爪哥（作者）· lvse（绿色建筑工程定额）md 源管线变体验证回写

- **第三卷全链验证 + 新管线变体**：绿色建筑卷（269 页官方 PDF，无 docx 源）以 **md 为权威提取源**完成结构化——487 子目（20-1~20-487 连续零缺失）/ 目录 77 行（双栏重组）/ 条文 53 条，九门全绿 + 端到端重跑字节级复现 + P1 对**官方带水印原版**取证 487/487；
- **新增 `scripts/md_source/`**（8 脚本 + README）：convert（裸 fitz 转换层）→ extract_md → parse_items_lvse → parse_desc_lvse → finalize_lvse → cost_check_lvse → build_front_lvse → gate_lvse；成果契约与 docx 链完全对标（lvse_quota.db schema 同构 sz05 docx_quota.db + src_page 列，前端复用 sz05 template，九门同构）；
- **双源架构定版**：提取用 nowm 干净源、P1 校验用官方 wm 原版，baseline_manifest 同锚两者 sha12 + convert 脚本 sha12；
- **新形态坑 9 条入 pitfalls（坑 25-33）**：转换层三连（pymupdf4llm 段错误/旋转水印 redact 整页抹除/E-BZ 小数空格）、页码散字外侧边分区 offset、章标题前缀剥离致 kind 判界失效、md 合并单元格形态差异（行判别三法）、工作内容拆行双遍扫描、节标题跟表验证、目录双栏重组、H1 四项制因卷校准、P1 未去空白原文正则；
- **volume_params/pipeline 增补**：md 源变体章节 + 高危混用点 ④⑤⑥（转换层字号分级/H1 项数/P1 文本口径）；
- 与 docx 链关系：**有 docx 源优先 docx 链**（token 更低、无转换层误差）；md 链用于"只有 PDF"的卷。

## v1.2.1 · 2026-10-15 · 爪哥（作者）· 自动回流机制化（sz01 断点根治）

- **新增 `scripts/sync_skill_remote.py`**：skill 仓自动回流（dirty 检测→commit→打 tag→push，幂等）。根治 sz01 实证断点：v1.2.0 回写完成但停留工作区，用户查问才发现未推远程；
- **新增项目级 `sync_remote.py`（sp/sync_remote.py）**：提取成果自动回流 GitHub 公开仓 `china-quota-volumes`（db/前端/交付报告/门控基线 35 文件，自动发现新卷零维护；源文件/中间产物永不回流；2026-10-15 升级全国架构：仓改名+转公开+地区层 `<region>/卷名/`，REGION_MAP 注册新地区一行接入）；
- **iteration-protocol.md 收官清单固化「回流两连」**：回写完成动作从"人工记得推"升级为机械步骤（协议 v1.2.1 起强制）；
- 修复成果回流 rel 路径覆盖 bug：双前端卷（sz05 PDF 版 + docx 版）并存时分名 `index.html` / `index_docx.html`。

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

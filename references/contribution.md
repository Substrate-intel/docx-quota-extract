# 成果回流全国库与 metal 悬赏协同协议

> 与 `iteration-protocol.md` 的分工：那边管 **skill 自身的迭代回流**（改 skill → PR）；
> 本文档管 **提取成果的数据回流**（一卷 db → 全国库 → 悬赏自动核销发分）。
> 两条回流通道独立，悬赏接单者两个都要走。

## 一、双向回流总览

```
                    ┌─ skill 迭代回流（fork 本 skill 仓 → PR → 作者审核 → 合并）
使用者完成一卷提取 ─┤
                    └─ 数据成果回流（本文档：PR 全国库 → webhook 自动协同 → 悬赏核销）
```

## 二、悬赏接单者完整闭环（8 步）

1. **领悬赏**：metal 工程人工具包站点「定额悬赏」tab（http://134.175.50.9:3001，quota.html）领取任务，记录 地区+卷名+悬赏编号；
2. **获取官方源**：从发布平台（如省住建厅 fwpt）下载该卷官方 PDF（无 Word 源只有 PDF 时改用姊妹 skill `md-quota-extract`）；
3. **提取**：复制本 skill scripts/（md 源卷用 md-quota-extract 的 scripts/md_source/ 变体） → 按 volume_params.md 换参 → `check_volume_params.py` 零残留 → 11 阶段 → 九门全绿 + 渲染级冒烟全绿；
4. **本地自验交付三件套**：`<卷目录>/out/*.db`（SQLite 七表）+ `web/index.html`（成果库）+ 交付报告（覆盖清单+人工复核项）；
5. **fork 全国库**：fork `Substrate-intel/china-quota-volumes`（公开仓）；
6. **提 PR**（内容纪律见下表）：

| PR 包含（公开仓路径 `<地区>/<卷目录>/`） | 不入 PR |
|---|---|
| `index.html`（前端成果库） | **db（收私有仓，见下）** |
| 交付报告 `*.md` | 官方源 PDF（**版权，永不回流**） |
| `baseline_manifest.json`（基线指纹） | 中间产物 json（指纹已锚定可复现） |
| `cost_check_report.json`（核验报告） | |

   PR 描述必须附：**db 的 sha256 + 体积 + 获取方式**（网盘/附件等私下通道交维护者）；若该卷在 VOLUME_META 无注册条目，附一行注册建议（key/label/kind）。

7. **维护者审核**：基线指纹复跑核验、九门报告比对、db sha256 校验 → 合并公开仓 PR + db 验收入私有仓 `china-quota-volumes-data`；
8. **自动协同（零人工，含自动发分）**：公开仓 push → GitHub webhook → 服务器（134.175.50.9:3001）拉取 volumes.json + 私有仓 db（sha256 门禁）→ **悬赏自动核销发分**：
   - `open` 状态悬赏 → 匹配 → 自动 `closed`；
   - `claimed/submitted` 状态 → 自动 `verified` → **自动 `settled` 发分**（`points.earn` pool='bounty'，refId=`quota-bounty:<id>` 唯一索引幂等，重复协同不重发；SystemSetting `QUOTA_AUTO_SETTLE=off` 可关自动发分、退回人工闸）。
   - **匹配三通道**（2026-10-17 根治，xj01 实证）：① `targetVol` 精确绑卷（悬赏发布时选定目标卷，最高优先，不受书名文本差异影响）；② 原文本双向包含 / ≥3 字连续窗口；③ 关键词实体匹配（专业词 ≥1 **且** 泛词 ≥1，治「建筑专业定额最新版」↔「房屋建筑与装饰消耗量定额」类近义不同表述）；另价格册类词（价目表/单价册/单价表/价格表）与消耗量定额卷**互斥**（防价目表悬赏误命中消耗量卷、反之亦然）。
   - **悬赏发布建议**：书名尽量含目标卷 label 的 ≥3 字窗口（注意「装饰工程」不命中「装饰消耗量」），或直接用 `targetVol` 绑卷最稳。

## 三、维护者侧入库操作（接单者勿动）

- PR 合并后：卷目录放入本地 `sp/`，`python sync_remote.py` 自动发现（glob `quota-extract*`）双仓同步——**私有仓先推**（保 webhook 时序：db 先就位，volumes.json 后触发协同）；
- 双仓纪律：公开仓=元数据+前端+报告（无 db）；私有仓=仅 db，路径与 volumes.json 同构，sha256 门禁；
- 站点 `quota-db.js` 动态注册表**随进程重启生效**：协同入库后 kill node → watchdog 自动拉起；
- git 直连 github.com 间歇 502 时：走 Git Data API 通道（`git_api_push.py` / `api_push_public.py`，坑：ls-tree 必须 `core.quotepath=off`，防中文路径转义损坏）。

## 四、铁律（违反即打回）

1. **官方源文件永不回流**（版权：input/ 的 PDF/docx 不进任何远程仓）；
2. **db 不走公开仓 PR**——数据收私，PR 只交元数据+前端+报告，db 经私下通道 + sha256 校验入私有仓；
3. 中间产物（out/*.json 过程态、取证 jpg）不回流——基线指纹已锚定字节级可复现；
4. 九门未全绿/冒烟未过的卷不得提 PR（审核第一关即查 manifest 与核验报告）。

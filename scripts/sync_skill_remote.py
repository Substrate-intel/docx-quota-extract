#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_skill_remote.py — skill 仓自动回流（收官清单步骤 ⑩）

作用：检测 skill 仓工作区改动 → 自动 commit + push。解决"回写完成但
停留工作区未推送"的断点（sz01 v1.2.0 曾实证踩过：用户查问才发现未回流）。

用法：
  python sync_skill_remote.py            # dirty 则自动 commit+push
  python sync_skill_remote.py -m "msg"   # 指定 commit 主题（推荐，含版本号）
  python sync_skill_remote.py --tag vX.Y.Z -m "msg"   # commit+打 tag+push（收官用）

纪律：commit message 必须含版本号或卷名；tag 只在收官回写时由人工/主控指定，
脚本不自动猜版本号。
"""
import os
import sys
import subprocess

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, check=True):
    r = subprocess.run(cmd, cwd=SKILL, capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=120, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print(r.stdout); print(r.stderr)
        raise SystemExit(f"FAIL: {' '.join(cmd)}")
    return r


def main():
    args = sys.argv[1:]
    tag = None
    if "--tag" in args:
        i = args.index("--tag")
        tag = args[i + 1]
        del args[i:i + 2]
    msg = None
    if "-m" in args:
        i = args.index("-m")
        msg = args[i + 1]
        del args[i:i + 2]

    st = run(["git", "status", "--porcelain"])
    dirty = [l[3:].strip() for l in st.stdout.splitlines() if l.strip()]
    if not dirty:
        # 工作区干净：只补推未推的提交/tag
        r = run(["git", "push", "origin", "main", "--tags"], check=False)
        pushed = r.stdout + r.stderr
        print("工作区干净；", "远程已同步" if "up-to-date" in pushed or "Everything" in pushed
              else pushed.strip())
        return

    run(["git", "add", "-A"])
    if not msg:
        msg = "skill 迭代自动回流: " + ", ".join(dirty[:5]) + \
              (" 等" if len(dirty) > 5 else "")
    run(["git", "-c", "user.name=zhuage", "-c", "user.email=zhuage@local",
         "commit", "-m", msg])
    if tag:
        run(["git", "-c", "user.name=zhuage", "-c", "user.email=zhuage@local",
             "tag", "-a", tag, "-m", msg])
    push = run(["git", "push", "origin", "main", "--tags"], check=False)
    head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    if push.returncode != 0:
        print(push.stderr.strip() or "push 失败（网络间歇）——commit 已落本地，网络恢复后重跑本脚本自动补推")
        raise SystemExit(1)
    print(f"已回流 {len(dirty)} 个文件 -> commit {head}" + (f" + tag {tag}" if tag else ""))
    for f in dirty:
        print("  +", f)


if __name__ == "__main__":
    main()

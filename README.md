# 老人电视直播列表（自动每日更新）

给小米电视（my-tv-0 直播 App）用的**精简频道表**：陕西（含西安）→ 央视 CCTV1–17 → 各省卫视 → 戏曲故事。
每天自动从公开直播源（vbskycn/iptv、iptv-org、suxuang/myIPTV）重新抓取、按 `channels.txt` 挑选排序，
同一频道最多保留 4 条线路，自动去掉“盗版提示/打赏”等占位画面和 4K 线路（老电视解不了）。

电视上填的地址（发布后把 `用户名/仓库名` 换成真实的）：
- 国内首选（Gitee）：`https://gitee.com/用户名/仓库名/raw/main/output/elderly.m3u`
- 备用（jsDelivr CDN，最长约 12 小时缓存）：`https://cdn.jsdelivr.net/gh/用户名/仓库名@main/output/elderly.m3u`
- 原始（GitHub，国内可能打不开）：`https://raw.githubusercontent.com/用户名/仓库名/main/output/elderly.m3u`

## 怎么改频道顺序（最常用）
1. 在 GitHub 网页打开 `channels.txt` → 点右上角铅笔（编辑）。
2. 剪切/粘贴整行调整顺序；不想要的频道在行首加 `#`；分组用 `[分组名]` 一行开始。
3. 点 **Commit changes**。几分钟后 Actions 自动重新生成 `output/elderly.m3u`，并同步到 Gitee。
4. 电视：下次打开直播 App 时自动拉取新列表（App 设置里“應用啟動後更新視頻源”需为开启）。
文件开头有详细中文说明（别名写法、自动收录 `*` 行、换省份等）。

> 只在 Gitee 改的话会被下一次 GitHub 同步覆盖——**请只在 GitHub 上改**。

## 第一个频道 / 打开 App 先播哪个
- 列表第一个分组的第一个频道是“陕西卫视”。
- my-tv-0 默认会回到**上次看的频道**；想固定开机先播陕西卫视：手机打开 `http://电视IP:34567` →
  “默認播放頻道號” 填 `1` → 確認。

## 线路说明
- 一个频道多条线路时，my-tv-0 只显示一个频道；当前线路连续失败约 10 次（约 30–60 秒）后**自动切到下一条**。
- my-tv-0 **没有手动切线路的按键**；所以生成时线路顺序很重要（vbskycn → iptv-org → suxuang）。

## 文件
| 文件 | 作用 |
|---|---|
| `channels.txt` | 频道表：选哪些、什么顺序、分哪组（**平时只改它**） |
| `config.json` | 直播源地址、每频道最多几条线路、过滤规则（一般不用改） |
| `build.py` | 生成脚本（Python 3，`--slate-check` 需要 ffmpeg + Pillow） |
| `slates/` | 占位画面参考图（盗版提示、打赏页），画面指纹相近的线路会被丢掉 |
| `output/elderly.m3u` | 生成结果（电视读取这个） |
| `output/report.json` | 每个频道的线路与检测结果 |
| `.github/workflows/build.yml` | 每天北京时间 04:30 自动生成；改 channels.txt 后也会立即生成；可手动运行 |

本地运行：`pip install pillow && python3 build.py --slate-check`

## Gitee 同步（二选一）
- **A. Actions 推送（推荐，全自动）**：在 Gitee 建同名空仓库（公开）→ Gitee「设置 → 私人令牌」生成令牌（勾选 projects）→
  GitHub 仓库「Settings → Secrets and variables → Actions」：Secret `GITEE_TOKEN`=令牌；Variables `GITEE_USER`=Gitee 用户名，`GITEE_REPO`=仓库名。
  之后每次生成都会 `git push --force` 到 Gitee 的 main 分支。
- **B. Gitee 自带“从 GitHub 导入 / 仓库镜像”**：Gitee 新建仓库时选“导入已有仓库”填 GitHub 地址；之后在仓库页点「强制同步」，
  或在「管理 → 仓库镜像管理」配置自动拉取（是否可用以 Gitee 当前政策为准）。

## 注意
- 直播源均来自网络公开列表，可用性每天变化，国外机房（GitHub）无法判断国内能否播放，所以不按“能否播放”删线路，只删确认的占位/录播。
- 本仓库不提供任何节目内容，仅整理公开链接。

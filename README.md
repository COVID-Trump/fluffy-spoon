Minecraft Decompiled Git Repo Automator

本仓库包含一套自动化工作流（GitHub Actions），用于持续反编译 Minecraft 各个版本，并将结果自动推送到一个私有目标仓库中。

该工作流支持断点续传、时间控制（防止超时）、动态依赖获取，并严格按照时间戳顺序处理版本。

📁 项目结构

.
├── .github/workflows/decompile_loop.yml   # 核心工作流定义
├── scripts/
│   ├── logic.py                           # 主逻辑：版本筛选、时间控制、Git操作
│   └── LatestNeoForm.py                   # 辅助脚本：获取对应版本的 NeoForm 映射
├── versions.properties                    # 配置：定义 min_version 和 max_version
└── nfrt-url.txt                           # 配置：nfrt.jar 的下载链接

⚙️ 前置准备 (必须配置)

为了让工作流能够正常运行并写入你的私有目标仓库，你必须在 本仓库 (Script Repo) 的 Settings -> Secrets and variables -> Actions 中配置以下两个 Repository Secrets：

GH_PAT (GitHub Personal Access Token)
作用: 授权工作流读取和写入目标私有仓库。默认的 GITHUB_TOKEN 无法跨仓库操作。
如何获取:
    访问 GitHub Personal access tokens (classic)。
    点击 "Generate new token (classic)"。
    注意范围 (Scopes): 必须勾选 repo (Full control of private repositories)。这是必须的，否则无法推送代码到私有仓库。
    生成后复制 Token。
配置: 在本仓库的 Secrets 中新建名为 GH_PAT 的条目，粘贴 Token。

TARGET_REPO (目标仓库标识)(注：原需求中提到 TARGET_REPO_PATH 为路径，但通常仓库名更灵活。此处修正为配置目标仓库的全名，路径在工作流中固定)
更正: 根据工作流设计，我们实际上需要配置的是目标仓库的名称。
Secret 名称: TARGET_REPO_NAME
值格式: OwnerName/RepoName (例如: MyOrg/Minecraft-Decompiled)
作用: 告诉工作流将反编译后的代码推送到哪个仓库。

注意: 如果你的目标仓库不在同一个 Organization 下，请确保上面生成的 GH_PAT 所属的用户对目标仓库有 Write 权限。

📝 配置文件说明

在运行工作流前，请修改根目录下的以下文件：

versions.properties
定义需要反编译的版本范围。
起始版本 (可选)。如果目标仓库中的 version.txt 版本比这个新，则优先从 version.txt 继续。
min_version=1.20.1
结束版本 (可选)。不填则默认到最新。
max_version=1.20.4

nfrt-url.txt
填入 nfrt.jar 的直接下载链接。
https://example.com/path/to/nfrt.jar

scripts/LatestNeoForm.py
确保此脚本能接受一个 Minecraft 版本号作为参数，并输出对应的 NeoForm 版本字符串到标准输出 (stdout)。

🚀 工作流程逻辑

环境初始化: 设置 Python 3.13 和 Java 25。
状态检查:
   读取目标仓库中的 version.txt 获取上次成功处理的版本。
   结合 versions.properties 中的配置，确定本次任务的起始版本（取两者中较新的一个）。
版本列表生成:
   调用 Mojang API，获取指定范围内的所有版本。
   严格依据时间戳 (releaseTime) 排序，而非版本号字符串。
循环处理:
   时间监控:
     运行超过 4小时: 处理完当前版本后停止，推送并退出。
     运行超过 4.5小时: 立即强制停止，推送已有成果并退出。
   反编译:
     调用 LatestNeoForm.py 获取依赖。
     运行 nfrt.jar 生成源码包。
     解压源码到目标仓库目录，覆盖旧文件（保留 .git 和 version.txt）。
   提交:
     更新 version.txt 为当前版本。
     git add, commit, tag (标签格式: mc-)。
推送: 将 commits 和 tags 推送到目标私有仓库。

🔒 安全提示

Token 安全: GH_PAT 拥有对目标仓库的完全控制权。请勿将其泄露给他人，也不要提交到代码库中。
最小权限: 建议专门为这个任务创建一个专用的 GitHub 账号或使用限制范围的 Token，仅授予必要的仓库权限。

🛠️ 手动触发

除了定时任务（默认每天 UTC 00:00），你也可以在 GitHub Actions 页面手动触发工作流：
进入 Actions 标签页。
选择 MC Decompiler Loop。
点击 Run workflow。

❓ 常见问题

Q: 为什么工作流失败了？
A: 常见原因包括：
GH_PAT 未配置或权限不足（缺少 repo scope）。
TARGET_REPO_NAME 配置错误，导致仓库找不到。
目标仓库不是私有的或者 Token 所有者没有写入权限。
nfrt.jar 下载链接失效。

Q: 如何重置进度从头开始？
A: 在目标私有仓库中，修改或删除 version.txt 文件（例如改为空或非常旧的版本），然后重新触发工作流。

Q: 支持 Java 25 吗？
A: 是的。

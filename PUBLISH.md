# 将这份独立材料公开到 GitHub

> 此包没有自动发布；下面命令需要在你**自己已登录 GitHub CLI** 的终端运行。

推荐目标：`chengong-art/a7m4-lut-log-shooting`。

1. 解压后进入根目录，不要把私有研究仓库放进这个目录。
2. **人工核对**所有文件，确认没有秘密数据和未经授权的二进制。此包默认不包含任何 FDAT/固件/私有证据。
3. 如已安装并登录 `gh`，在这个新目录中执行：

```sh
# 在新解压的文件夹（含 README.md）中运行
GH_PROMPT_DISABLED=1 gh auth status
git init
git add .
git commit -m "docs: publish A7M4 6.02 offline research and test call"
GH_PROMPT_DISABLED=1 gh repo create chengong-art/a7m4-lut-log-shooting --public --source=. --remote=origin --push
```

如果 `git` 没有设置用户信息、仓库名已被占用或当前 GitHub 登录账户无权限，命令会报错并应停止排查。**切勿**改用 `git remote add` 把私有研究仓库整体推送。

或打开 https://github.com/new ，Repository name 输入 `a7m4-lut-log-shooting`，选择 Public，在空仓库建立后只上传此包中的公开文件。

公开成功后，再在招募帖中放入仓库的**实际** URL。

注意 GitHub 中新仓库的 Issues 默认一般可用，但 Issue 模板里的标签 `offline-test` 如果尚未建立，提交时标签可能无法自动应用；可手动创建对应标签。

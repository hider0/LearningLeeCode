# LeetCode 刷题训练器

一个**零第三方依赖**的本地刷题 Web 应用：按章节浏览 LeetCode 经典题目，在线提交
Python 代码并由本地判题器运行测试用例判题，提交后展示讲解；做错的题自动记入错题本，
不明之处可以继续追问或让 AI 诊断思路（支持接入大模型 API，未配置时回退为本地内容）。

> 📖 配套教程见 [学习指南.md](学习指南.md) 和 [guide/](guide/README.md)：当前包含
> 7 个章节、27 道题，建议按「读一章、刷一章、隔天重做错题」的节奏学习。

## 快速开始

只需要 **Python 3.9+**，无需 pip 安装任何依赖：

```bash
git clone https://github.com/hider0/LearningLeeCode.git
cd LearningLeeCode
python app.py        # Windows 也可以直接双击“启动刷题训练器.bat”
```

然后浏览器打开 <http://127.0.0.1:8000> 即可开始刷题。

- Windows：双击 `启动刷题训练器.bat` 最简单——自动检测可用的 Python
  （会跳过微软商店占位 stub）、启动服务并自动打开浏览器，关闭窗口即停止服务。
- macOS / Linux：使用命令行方式，若系统只有 `python3` 命令，把 `python` 换成 `python3`。
- 指定端口：`python app.py 9000`。

如果还没有 Python：

- Windows：从 [python.org](https://www.python.org/downloads/) 下载安装（勾选
  “Add python.exe to PATH”），或 `winget install Python.Python.3.12`。
- macOS：`brew install python@3.12` 或使用系统自带 `python3`。
- Linux：`sudo apt install python3` 等。
- 验证：终端执行 `python --version`，显示 3.9+ 即可。

## 功能一览

- **分章节刷题**：左侧边栏按章节组织题目，标注难度与完成状态（○ 未做 / ✓ 已通过 / ✗ 错题）。
- **在线判题**：在页面中编写 `Solution` 类代码，点击“提交判题”，后端会在子进程中
  运行你的代码并对拍全部测试用例（含链表、二叉树的自动构造与序列化比对），
  逐条展示每个用例的输入、期望输出、实际输出或报错。
- **题解讲解**：提交后自动展开本题的详细讲解、提示与参考实现。
- **草稿恢复**：编辑器内容自动保存在浏览器；刷新或切换题目后会恢复草稿，错题还会回填最近提交代码。
- **错题本**：未通过的提交自动记录（错误次数、最近提交时间、错误摘要），
  通过后自动移出。点击顶部“错题本”查看。
- **追问**：对题目或判题结果有不明白的地方，可在题目页的追问框继续提问。
  - 已配置大模型：由 AI 结合题目与你当前的代码针对性作答。
  - 未配置大模型：返回本地预置讲解，同时把问题记入笔记，配置后可获得针对性回答。
  所有问答按题目保存在 `data/progress.json` 中。
- **AI 思路诊断**：判题失败后可点击“AI 诊断我的思路”，大模型会分析你的代码并输出
  结论。诊断会同时读取本题的标准实现与参考复杂度，对比用户实现的数据结构、控制流程、
  正确性和性能，而不是只看测试是否通过；通过后也可继续点击“AI 评估复杂度与思路”。
  未配置大模型时回退为基于判题结果的
  粗略本地诊断（如“X/Y 用例通过，思路大概率正确，检查边界情况”）。
  诊断记录同样保存在笔记中。

## 配置大模型（可选）

复制 `config.example.json` 为 `config.json`，填写任意 **OpenAI 兼容接口**：

```json
{
  "api_key": "sk-你的密钥",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "timeout_seconds": 120
}
```

- 国产模型同样适用，例如 DeepSeek：`base_url` 填 `https://api.deepseek.com/v1`，
  `model` 填 `deepseek-chat`；Kimi：`https://api.moonshot.cn/v1` + `moonshot-v1-8k`。
- 也可以用环境变量代替配置文件：`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` /
  `OPENAI_TIMEOUT_SECONDS`
  （配置文件优先于环境变量）。
- `timeout_seconds` 控制单次大模型请求的最长等待时间，可配置为 5～600 秒。
- 不配置 `api_key` 时一切功能照常，只是追问/诊断回退为本地内容。

### API Key 安全保障

- **Key 不出本机**：只从本地 `config.json`（已被 `.gitignore` 排除，不会进版本库）
  或环境变量读取，只会在调用时放入发往 `base_url` 的请求头中，不会发送到任何其他地方。
- **前端拿不到 Key**：所有接口只返回脱敏标识（如 `sk-****1234`）和接口域名，
  页面顶部的状态栏显示的也是脱敏信息。
- **外发内容边界**：追问会发送题目描述、参考讲解、当前代码、当前问题及最近 6 轮本题问答；
  思路诊断会发送题目描述、当前代码和判题摘要。不会读取或发送本机其他文件和环境信息。
- **错误信息已清洗**：网络或接口异常的提示中不会携带 Key。
- 建议使用 `https://` 的接口地址；若配置了 `http://` 地址，页面状态栏会给出风险提示。

## 隐私与使用边界

- **仓库不含任何个人数据**：`config.json`（API Key）与 `data/`（做题进度、错题本、
  追问笔记）均被 `.gitignore` 排除，clone 本仓库得到的是纯净的项目本身；
  每位使用者的 AI 功能使用**各自自己的 Key**，互不影响。
- **这是一个本地工具**：判题器会真实执行页面中提交的 Python 代码，
  请只在本地（127.0.0.1）使用，**不要部署成公网服务**，也不要粘贴运行来路不明的代码。
- 判题进程设置了 CPU、内存、文件大小、打开文件数、子进程数和输出上限，并在超时时清理进程组；
  这些措施用于降低误操作影响，**不等同于容器或虚拟机安全沙箱**，也不能阻止所有文件或网络访问。
- 数据完全存放在你自己的机器上（`data/progress.json`），删除该文件即可清空全部记录。
  写入采用线程锁和临时文件原子替换；若发现损坏 JSON，旧文件会被保留为 `progress.corrupt-*.json`。

## 目录结构

```
启动刷题训练器.bat   # Windows 双击启动脚本（自动打开浏览器）
app.py                 # 后端服务（题目/判题/错题/追问/诊断 API，仅标准库）
runner.py              # 判题运行器：子进程中执行用户代码并对拍用例
problems/*.json        # 题库，一个文件一章，按文件名排序
guide/*.md              # 面向初学者的分章详细教程
static/index.html      # 前端单页（内联 CSS/JS）
config.example.json    # 大模型配置示例，复制为 config.json 后填写
data/progress.json     # 运行时生成：通过记录、错题本、追问笔记（不入库）
tests/                  # 标准库 unittest 自动化测试
```

## 如何添加新题

在 `problems/` 下编辑或新增 JSON 文件，一题的完整字段：

```json
{
  "id": "unique-kebab-id",
  "title": "编号. 题名",
  "difficulty": "简单 | 中等 | 困难",
  "description": "题面（支持 `代码` 与 **加粗** 标记）",
  "examples": [{"input": "...", "output": "...", "explanation": "可选"}],
  "entry": "methodName",
  "starter": "class Solution:\n    def methodName(self, ...):\n        pass\n",
  "tests": [{"args": ["参数1", "参数2"], "expected": "期望输出"}],
  "compare": "exact",
  "hints": ["提示1", "提示2"],
  "explanation": "讲解（支持 ```python 代码块）"
}
```

特殊机制：

- **链表/二叉树题**：加 `"codec"` 字段，判题器自动在数组与数据结构间转换。
  链表用 `"linked"`，二叉树（层序数组，`null` 表示空节点）用 `"tree"`。
  例如 `{"codec": {"args": ["linked"], "result": "linked"}}`。
  判题器已预置 `ListNode` / `TreeNode` 类，用户代码直接使用即可。
- **答案顺序无关**：`"compare": "sorted"`（顶层排序，如两数之和）或
  `"sorted_deep"`（内外层都排序，如字母异位词分组）。

改完后重启 `app.py` 即可生效。

## 判题原理与说明

- 提交后，`app.py` 把你的代码与测试用例发给子进程 `runner.py` 执行，
  单次判题墙钟限时 15 秒，并在支持的系统上进一步限制 CPU、内存、文件和进程资源。
- 判题只看**输出对拍**：你的代码真实运行后，各用例的实际输出与期望输出逐一比较，
  全部一致才算通过；与参考实现的写法、思路无关（暴力解只要结果对、不超时就判对）。
- 代码中的 `print` 输出会被捕获并显示在判题结果里，方便调试。

## 运行测试

项目测试同样只使用 Python 标准库：

```bash
python -m unittest discover -s tests -v
```

测试覆盖题库结构、全部参考答案、判题异常与输出限制、进度原子写入和并发更新。

# Codex 本地 Skill 改造教程

## 目标

把一个本地 Python 项目改造成 Codex 可用的本地 skill，并满足下面这套使用方式：

- Codex 只调用你封装好的命令
- skill 只描述任务规则，不暴露代码细节
- 项目真实代码、环境变量、运行路径由你自己控制
- 后续你可以把同样的方法复制到别的项目

本文按 3 部分写：

1. 代码本身如何写
2. skill 如何写
3. 整台电脑如何配置

---

## 第一部分：代码本身如何写

目标：把项目写成一个“命令行工具”，让外部只需要调用命令，不需要接触源码。

### 1. 项目结构

推荐结构：

```text
my-project/
  .env
  pyproject.toml
  uv.lock
  src/
    my_tool/
      __init__.py
      cli.py
      config.py
      models.py
      xxx.py
  output/
```

说明：

- `.env`：运行配置
- `pyproject.toml`：项目声明与命令入口
- `src/my_tool/cli.py`：统一命令入口
- `output/`：缓存、摘要、导出产物

### 2. 统一命令入口

必须把项目封成一个明确的 CLI。

`pyproject.toml` 里写：

```toml
[project.scripts]
my-tool = "my_tool.cli:main"
```

这样项目内部所有能力都通过一个命令暴露，例如：

```bash
uv run my-tool collections
uv run my-tool items <id>
uv run my-tool extract
```

不要让 Codex 直接调用散落的 Python 文件。

### 3. 命令设计原则

只暴露原子命令。

推荐保留这种粒度：

- `collections`
- `items <id>`
- `attachments <id>`
- `extract-pdfs <id>`
- `summaries --collection-key <id>`
- `save-summary ...`

不要一开始就做一个巨大的一键命令，除非流程已经完全稳定。

### 4. 配置读取

配置统一从 `.env` 读取。

例如：

```env
DB_PATH=...
STORAGE_DIR=...
OUTPUT_DIR=...
```

代码里统一在 `config.py` 读取，不要把路径硬编码到业务逻辑里。

### 5. 输出目录设计

输出目录只保留真正需要复用的内容。

推荐区分：

- 正式缓存：后续流程会再次使用
- 一次性导出：仅用于调试

正式缓存应保留，例如：

```text
output/pdf_text_cache/
output/analysis_summaries/
```

一次性导出如果不是流程必须，就不要自动生成。

### 6. 数据安全原则

如果项目读的是本地数据库或其他核心数据源：

- 默认只读
- 不提供删除接口
- 不提供修改源数据库接口
- 所有写入都写到你自己的 `output/` 目录

如果用 sqlite，建议连接层就做只读限制。

### 7. 摘要与缓存设计

如果项目涉及“AI 读内容再判断”，推荐至少保留两层缓存：

1. 原始文本缓存
2. 面向当前需求的摘要缓存

例如：

```text
output/pdf_text_cache/<attachment_key>.txt
output/analysis_summaries/<attachment_key>/<requirement_hash>.json
```

这样下次 Codex 不必重复读取整篇内容。

---

## 第二部分：skill 如何写

目标：让 Codex 只知道“应该调用哪些命令做什么”，而不是知道代码路径和实现细节。

### 1. skill 目录结构

推荐最小结构：

```text
my-skill/
  SKILL.md
  agents/
    openai.yaml
  references/
    commands.md
```

不要把安装说明、环境变量说明、部署过程说明塞进 skill 目录。

### 2. SKILL.md 写法

`SKILL.md` 只写 4 类内容：

1. 触发条件
2. 可用命令
3. 编排顺序
4. 输出约束

示例：

```md
---
name: my-skill
description: 用已经可直接调用的 `my-skill` 命令，按原子步骤完成本地数据检索、缓存复用和结果写入。
---

# My Skill

前提：`my-skill` 命令已可直接调用。

读取 [references/commands.md](references/commands.md)。

## 顺序

1. 先查对象列表。
2. 再查对象详情。
3. 先查历史摘要。
4. 摘要不够再查正文缓存。
5. 必要时再做提取。
6. 有新判断再写摘要。
```

### 3. references/commands.md 写法

这里只写命令和编排，不写路径、不写底层实现。

示例：

```md
# 原子命令

```bash
my-skill list
my-skill items <id>
my-skill extract <id>
my-skill summaries --id <id>
my-skill save-summary ...
```

## 编排

1. `list`
2. `items <id>`
3. `summaries --id <id>`
4. 必要时 `extract <id>`
5. 必要时 `save-summary`
```

### 4. openai.yaml 写法

只写简短元数据。

示例：

```yaml
display_name: My Skill
short_description: 用封装好的命令按步骤处理本地项目数据。
default_prompt: 帮我用 my-skill 命令按步骤完成查询、缓存复用和结果整理。
```

### 5. skill 的边界

skill 里不要写这些内容：

- 真实项目路径
- 虚拟环境路径
- `.env` 路径
- 安装步骤
- bat/cmd/ps1 细节
- 源码解释

skill 只假定一个事实：

```bash
my-skill ...
```

已经存在且可直接调用。

### 6. 关于“Codex 看不到代码”的真实含义

如果你把源码和 skill 放在同一个可读工作区里，Codex 理论上仍然可以访问源码。

真正的“黑盒使用”依赖的是这套约束：

- skill 文本里不暴露代码路径
- 只给 Codex 一个封装好的命令
- 测试和使用时只按命令调用，不向下展开

这是一种工程上的封装，不是系统级隔离。

如果你需要更强隔离，应该把真实代码放在 Codex 当前工作区之外，只通过命令暴露能力。

---

## 第三部分：整台电脑如何配置

目标：让 Codex 在任意目录都只用一个命令，例如：

```bash
my-skill ...
```

### 1. 项目本体

你的真实项目放在你自己决定的位置，例如：

```text
D:\path\to\my-project
```

项目根目录中保留：

- `.env`
- `pyproject.toml`
- `src/`
- `uv.lock`

### 2. 封装命令

新建一个你自己的工具目录，例如：

```text
C:\Users\<username>\bin
```

把这个目录加入用户 `PATH`。

然后创建命令文件，例如：

```text
C:\Users\<username>\bin\my-skill.cmd
```

内容：

```cmd
@echo off
uv run --project "D:/path/to/my-project" --env-file "D:/path/to/my-project/.env" my-tool %*
```

解释：

- `my-skill`：给 Codex 的黑盒命令名
- `my-tool`：项目真实 CLI 名

以后 Codex 只看到：

```bash
my-skill ...
```

看不到底层项目结构。

### 3. 环境变量

项目运行配置仍放在项目自己的 `.env` 里。

例如：

```env
DB_PATH=...
STORAGE_DIR=...
OUTPUT_DIR=...
```

不要把这些细节写进 skill。

### 4. 测试顺序

先测试底层项目 CLI：

```bash
uv run --project "D:/path/to/my-project" --env-file "D:/path/to/my-project/.env" my-tool --help
```

再测试黑盒命令：

```bash
my-skill --help
my-skill list
my-skill items <id>
```

最后测试 skill：

- 把 `my-skill/` 复制到 Codex skills 目录
- 在对话里只让 Codex 使用 `my-skill`
- 不再给它源码路径

### 5. 推荐最终形态

最终推荐结构：

- 真实代码：放你自己的项目目录
- `.env`：放项目根目录
- `my-skill.cmd`：放 `PATH` 目录
- `my-skill/`：放 Codex skills 目录

对应关系：

- 真实项目负责实现能力
- `.cmd` 负责封装命令
- skill 负责告诉 Codex 如何调用命令

---

## 最终模板

### 项目命令入口

```toml
[project.scripts]
my-tool = "my_tool.cli:main"
```

### 黑盒命令脚本

```cmd
@echo off
uv run --project "D:/path/to/my-project" --env-file "D:/path/to/my-project/.env" my-tool %*
```

### skill frontmatter

```md
---
name: my-skill
description: 用已经可直接调用的 `my-skill` 命令，按原子步骤完成本地项目处理。
---
```

### skill 最小原则

- skill 只写任务规则
- 不写真实路径
- 不写部署细节
- 不写代码解释
- Codex 只调用 `my-skill ...`

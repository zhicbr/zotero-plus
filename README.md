# Zotero Plus

本项目是一个本地优先的 Zotero 论文探索工具，数据来源完全依赖本地 `zotero.sqlite` 和本地附件存储目录，不依赖云端 API。

它当前的定位不是“一条命令直接完成所有论文筛选”，而是提供一组稳定的、可被 AI 编排调用的步骤化命令，让一个会运行代码的 AI 代理可以自动完成以下流程：

1. 找到目标分类。
2. 获取该分类下的论文条目。
3. 获取这些条目对应的附件 PDF。
4. 将 PDF 提取为文本并缓存。
5. 根据用户需求，在标题、摘要、PDF 文本中筛选候选论文。
6. 输出结果、原因和后续可继续深挖的论文列表。

## 现在能否自动找论文

可以，但当前是“AI 编排式自动化”，不是“项目内置单条语义检索命令”。

这句话的意思是：

- 现在已经能自动完成分类、条目、附件、PDF 文本缓存这几步。
- 一个具备代码执行能力的 AI，可以基于这些现成命令自动串联完整找论文流程。
- 目前“某某需求”的匹配逻辑，还没有固化成单独的 `find-papers` 命令，而是由 AI 在运行现有命令后，用脚本、关键词规则或直接阅读缓存文本来完成筛选。

所以，假设你对 AI 说：

`请帮我在某某分类里找满足某某需求的论文。`

这个 AI 现在已经可以自动做事了，只是它做法是：

- 先调用本项目已有命令拿到结构化数据；
- 再利用缓存好的 PDF 文本做筛选和归纳；
- 最终把候选论文及理由返回给你。

## 配置

项目从根目录的 `.env` 读取配置：

```env
ZOTERO_SQLITE_PATH=D:/path/to/zotero_storage/zotero.sqlite
ZOTERO_STORAGE_DIR=D:/path/to/zotero_storage/storage
ZOTERO_CACHE_DIR=D:/path/to/zotero_storage/zotero_plus_cache
ZOTERO_OUTPUT_DIR=output
```

说明：

- `ZOTERO_SQLITE_PATH`：本地 Zotero 数据库。
- `ZOTERO_STORAGE_DIR`：本地 Zotero 附件存储根目录。
- `ZOTERO_CACHE_DIR`：持久化缓存根目录（PDF 提取文本、AI 分析摘要），独立存放在 Zotero 数据旁，不污染项目目录。
- `ZOTERO_OUTPUT_DIR`：临时/手动导出文件的默认目录。

## 当前命令

```bash
uv run zotero-plus collections
uv run zotero-plus items <collection_key>
uv run zotero-plus attachments <collection_key> --pdf-only
uv run zotero-plus extract-pdfs <collection_key>
```

可选输出：

```bash
uv run zotero-plus items <collection_key> --json-output output/items-<collection_key>.json
uv run zotero-plus attachments <collection_key> --pdf-only --json-output output/attachments-<collection_key>.json
uv run zotero-plus extract-pdfs <collection_key> --json-output output/extract-<collection_key>.json
```

## AI 代理的标准工作流

下面的流程，适用于一个“能力和 Codex 类似、可以运行命令和读写文件”的 AI。

### 场景输入

用户对 AI 说：

`请帮我在 <某个分类> 里找满足 <某个需求> 的论文。`

例如：

- `请帮我在 IoT 分类里找边缘智能与模型压缩相关的论文。`
- `请帮我在 2 这个分类里找适合毕业设计综述的论文。`
- `请帮我在中文分类里找涉及剪枝、量化、TinyML 的论文。`

### 步骤 1：定位目标分类

AI 先运行：

```bash
uv run zotero-plus collections
```

然后：

- 在分类列表中找到用户说的分类名。
- 取到对应的 `collection_key`。
- 如果分类名有歧义，就向用户说明候选项并确认。

### 步骤 2：列出分类下的论文条目

AI 运行：

```bash
uv run zotero-plus items <collection_key> --json-output output/items-<collection_key>.json
```

此时 AI 可以拿到每篇论文的：

- 标题
- 年份
- 摘要
- DOI
- 作者
- 附件列表

这一步的作用是先做“粗筛”。

通常 AI 会先根据以下信息初筛：

- 标题是否与需求相关
- 摘要是否提到目标主题
- 年份是否符合要求
- 是否属于用户想要的论文类型

### 步骤 3：列出可用 PDF 附件

AI 运行：

```bash
uv run zotero-plus attachments <collection_key> --pdf-only --json-output output/attachments-<collection_key>.json
```

此时 AI 可以知道：

- 哪些条目有本地 PDF
- PDF 的 Zotero 附件 key 是什么
- PDF 在本地的实际路径是什么

这一步的作用是把“只有元信息的条目”和“可以进一步深入阅读的条目”区分开。

### 步骤 4：提取并缓存 PDF 文本

AI 运行：

```bash
uv run zotero-plus extract-pdfs <collection_key> --json-output output/extract-<collection_key>.json
```

这一步会：

- 使用 PyMuPDF 提取 PDF 文本
- 把文本缓存到 `output/pdf_text_cache/`
- 下次重复运行时直接复用缓存，不再重复转换

缓存文件结构：

- `output/pdf_text_cache/<attachment_key>.txt`
- `output/pdf_text_cache/<attachment_key>.json`

其中：

- `.txt` 保存正文文本
- `.json` 保存元信息，例如页数、文本长度、原始 PDF 路径

### 步骤 5：按需求做匹配和筛选

到了这一步，AI 已经拿到了三层信息：

1. 分类信息
2. 条目元信息
3. PDF 文本缓存

然后 AI 可以根据用户需求执行筛选。

当前推荐的筛选顺序是：

1. 先看标题和摘要，做第一轮候选集收缩。
2. 对候选论文读取对应的缓存文本 `.txt`。
3. 在缓存文本中检索需求相关关键词、同义表达、任务目标、方法名、限制条件。
4. 对命中的论文给出理由，而不是只返回文件名。

例如，用户说：

`帮我找边缘智能里和剪枝、量化、TinyML 相关，适合做综述的论文。`

AI 可以这样判断：

- 标题或摘要是否包含 `pruning`、`quantization`、`TinyML`、`model compression`
- PDF 正文是否讨论方法综述、对比实验、部署限制、边缘设备、IoT 场景
- 是否是综述、比较研究、系统性分析，而不是单一非常窄的算法论文

### 步骤 6：输出给用户

AI 最终应该返回的不是“原始 JSON”，而是整理后的结果，例如：

- 最相关论文 3 到 10 篇
- 每篇论文的标题、年份、作者
- 推荐理由
- 命中的关键词或相关段落摘要
- 是否已有本地 PDF 文本缓存
- 如果需要进一步深读，应该优先看哪几篇

## AI 代理的最小自动化策略

如果现在就让一个 AI 代理自动执行，推荐采用下面的最小策略：

1. 运行 `collections` 找到分类 key。
2. 运行 `items` 获取论文条目。
3. 运行 `attachments --pdf-only` 获取有 PDF 的论文。
4. 运行 `extract-pdfs` 生成或复用缓存文本。
5. 优先根据标题和摘要初筛。
6. 对初筛候选读取 `output/pdf_text_cache/*.txt`。
7. 依据用户需求做关键词和语义层面的二次筛选。
8. 返回结果和理由。

这已经能支持 AI 自动完成“找论文”的主体工作。

## 当前能力边界

当前项目已经支持：

- 本地读取 Zotero 分类
- 本地读取分类下论文条目
- 本地读取附件信息和 PDF 路径
- 本地提取 PDF 文本
- 文本缓存复用

当前项目还没有内置：

- 按分类名直接搜索分类 key 的专门命令
- 按需求一条命令输出匹配论文的专门命令
- 更复杂的语义检索、重排序、摘要生成命令

因此，现在的自动化方式是：

- 项目提供稳定的数据获取和文本缓存能力
- AI 负责把这些能力编排成论文探索流程

## 为什么要拆成多个命令

这是有意设计的，因为 AI 探索论文时通常不是一步到位，而是分阶段推进：

1. 先确认分类是否正确。
2. 再看分类下是否真的有足够相关条目。
3. 再看哪些条目有本地 PDF。
4. 再把 PDF 转成可重复利用的文本缓存。
5. 最后才进入需求匹配与总结。

这样拆开后，AI 和人都可以随时中断、检查、复用已有结果，避免重复劳动。

## 目前最推荐的使用方式

如果你把这个项目交给一个会运行代码的 AI，最推荐的提示方式是：

`请帮我在 <分类名> 里找满足 <需求> 的论文。先定位分类，再列出条目，再找 PDF，再使用已有缓存或提取 PDF 文本，最后给我一个带理由的候选列表。`

这类请求，已经能基于当前项目稳定执行。

## 后续可以继续增强的方向

后续如果继续开发，建议优先加下面三类能力：

1. `find-collection <name>`：按分类名直接找 key。
2. `search-papers <collection_key> --query <需求>`：把需求匹配固化成一个正式命令。
3. `show-cache <attachment_key>` 或 `preview-paper <attachment_key>`：快速查看缓存文本摘要。

这三步做完后，这个项目就会从“AI 可编排工具集”进一步升级成“更完整的 AI 论文探索后端”。

## 需求相关分析摘要缓存

除了缓存 PDF 正文文本，现在项目还支持缓存“针对某个需求的 AI 分析摘要”。

这个摘要不是论文自带 abstract 的复制，而是 AI 在看过标题、摘要、正文缓存后，写下的一段工作笔记，至少包含：

- 这篇论文大致讲什么
- 它是否符合当前需求
- 为什么符合或不符合
- 后续是否值得继续深入看

### 为什么要单独缓存这个摘要

只缓存 PDF 正文还不够，因为下次 AI 再接到类似需求时，仍然可能要重新读整篇正文，浪费 token。

加入这个摘要层后，AI 的工作会变成两层缓存：

1. `output/pdf_text_cache/`：原始正文文本缓存
2. `output/analysis_summaries/`：面向具体需求的判断摘要缓存

这样下次 AI 可以先读需求摘要，如果摘要已经足够回答问题，就不必再读整篇 PDF。

### AI 如何写入摘要

当 AI 完成某篇论文的分析后，应该运行：

```bash
uv run zotero-plus save-summary \
  --attachment-key <attachment_key> \
  --requirement "<当前需求>" \
  --verdict match|maybe|not_match|unknown \
  --summary-file <summary_file>
```

例如：

```bash
uv run zotero-plus save-summary \
  --attachment-key WEQXE2ZM \
  --requirement "边缘智能、模型压缩、适合综述筛选" \
  --verdict maybe \
  --summary-file output/demo-summary-WEQXE2ZM.txt \
  --evidence "正文讨论 sparse fine-tuning 与 pruning" \
  --evidence "更像方法论文，不是综述论文"
```

这条命令会自动把摘要和以下信息关联起来：

- `attachment_key`
- 对应论文标题与年份
- 作者
- 所属 collection key
- 原始 PDF 路径
- 对应的 PDF 文本缓存路径
- 当前需求文本
- AI 给出的 verdict

### 摘要如何与 PDF 关联

摘要不是按“论文标题”关联，而是按 `attachment_key` 关联。

原因是：

- 标题可能改动
- 标题可能重复或相似
- `attachment_key` 是 Zotero 附件层最稳定的标识

实际存储路径类似：

- `output/analysis_summaries/<attachment_key>/<requirement_fingerprint>.json`

例如：

- `output/analysis_summaries/WEQXE2ZM/bdbb2b206bb6.json`

其中：

- 目录名对应具体 PDF 附件
- 文件名对应具体需求的指纹

这意味着：

- 同一篇 PDF 可以针对多个不同需求保存多份摘要
- 同一个需求再次分析时会更新原有记录，而不是新建一堆重复记录

### 下次 AI 如何知道已经有摘要

AI 下次进入同一任务时，不应该直接重新读 PDF，而应该先运行：

```bash
uv run zotero-plus summaries --collection-key <collection_key>
```

如果要只看某个具体需求的摘要，可以运行：

```bash
uv run zotero-plus summaries --collection-key <collection_key> --requirement "<当前需求>"
```

如果想先找相似需求留下的历史笔记，可以运行：

```bash
uv run zotero-plus summaries --collection-key <collection_key> --search "模型压缩"
```

这样 AI 就能先知道：

- 这个分类里哪些 PDF 已经被分析过
- 是针对什么需求分析过
- 当时的 verdict 是什么
- 摘要是否已经足够支撑当前回答

### AI 的新推荐流程

当用户说：

`请帮我在某个分类里找满足某个需求的论文。`

AI 推荐按下面顺序执行：

1. 先运行 `collections` 找分类 key。
2. 再运行 `items` 和 `attachments --pdf-only` 获取候选论文和 PDF。
3. 再运行 `summaries --collection-key <key> --requirement "<需求>"` 看有没有现成摘要。
4. 如果已有摘要足够，就直接基于摘要筛选和回答。
5. 如果摘要不足，再运行 `extract-pdfs` 并读取对应的 `pdf_text_cache/*.txt`。
6. 完成新的分析后，马上运行 `save-summary` 写回摘要缓存。
7. 最后向用户输出结果。

### 这个机制解决了什么问题

这个机制解决的是“AI 每次都重复读长 PDF”的问题。

现在同一篇论文有三层可复用信息：

1. Zotero 条目元信息
2. PDF 文本缓存
3. 面向具体需求的 AI 分析摘要

其中第 3 层是最省 token 的复用层，也是最适合 AI 在下一轮任务中优先查看的层。

## 项目文档导航

更多详细专项文档已统一收拢在 [docs/](docs/) 目录：

- [快速配置与安装指南 (docs/setup.md)](docs/setup.md)：环境变量、CLI 快捷方式配置与 Agent 技能同步说明。
- [开发者开发指南 (docs/development.md)](docs/development.md)：项目结构约定、二次开发关注文件与测试检查清单。
- [待办事项与进度记录 (docs/todo.md)](docs/todo.md)：已完成特性与待开发功能路线图。
- [Codex 本地 Skill 改造方法论教程 (docs/codex-skill-guide.md)](docs/codex-skill-guide.md)：将本地 Python 工具封装为 Agent 原子技能的通用架构指南。
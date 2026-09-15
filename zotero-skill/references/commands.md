# 原子命令

本文件只说明命令本身，不预设具体任务场景。

## 命令总表

```bash
zotero-skill doctor
zotero-skill collections
zotero-skill items <collection_key>
zotero-skill abstract <paper_key>
zotero-skill attachments <collection_key>
zotero-skill attachments <collection_key> --pdf-only
zotero-skill toc <attachment_key>
zotero-skill toc-from-paper <paper_key>
zotero-skill extract-pdfs <collection_key>
zotero-skill summaries --collection-key <collection_key>
zotero-skill summaries --collection-key <collection_key> --requirement "<需求>"
zotero-skill summaries --attachment-key <attachment_key>
zotero-skill save-summary --attachment-key <attachment_key> --requirement "<需求>" --verdict match|maybe|not_match|unknown --summary-file <文件>
```

## 1. doctor

```bash
zotero-skill doctor
```

用途：

- 检查命令本身是否可运行。

适用时机：

- 初次使用。
- 怀疑环境失效时。

## 2. collections

```bash
zotero-skill collections
```

用途：

- 列出全部分类。
- 提供层级定位所需字段。

关键输出字段：

- `key`：分类 key。
- `name`：分类名。
- `parent_name`：直接父分类名。
- `path`：完整路径。
- `path_keys`：完整路径对应的 key 列表。
- `depth`：层级深度。
- `item_count`：该分类当前条目数。

定位规则：

- 优先按 `key`。
- 否则按完整 `path`。
- 若用户说“分类 A 下的分类 B”，优先匹配 `parent_name=A` 且 `name=B`。

## 3. items

```bash
zotero-skill items <collection_key>
```

用途：

- 查看一个分类中的论文条目。
- 同时返回每篇论文的附件信息。

输入：

- `collection_key`：来自 `collections` 的分类 key。

关键输出字段：

- `key`：论文 key。
- `title`
- `year`
- `abstract`
- `authors`
- `attachments`

附件字段重点：

- `key`：附件 key。
- `title`
- `is_pdf`
- `exists_locally`
- `local_path`

用途边界：

- `items` 负责看论文和附件清单。
- 不负责读取 PDF 目录。
- 不负责提取正文文本。

## 4. abstract

```bash
zotero-skill abstract <paper_key>
```

用途：

- 读取 Zotero 数据库中存储的论文摘要。

输入：

- `paper_key`：来自 `items` 结果。

关键输出字段：

- `paper_key`
- `title`
- `year`
- `abstract`
- `doi`
- `authors`
- `collection_keys`

适用时机：

- 需要快速判断论文主题。
- 需要先做轻量筛选。

## 5. attachments

```bash
zotero-skill attachments <collection_key>
zotero-skill attachments <collection_key> --pdf-only
```

用途：

- 列出一个分类中的全部附件。
- 用 `--pdf-only` 仅保留 PDF。

输入：

- `collection_key`

关键输出字段：

- `key`
- `title`
- `is_pdf`
- `exists_locally`
- `local_path`
- `parent_item_id`

适用时机：

- 需要从分类层面快速看哪些 PDF 可用。
- 需要拿到附件 key，再继续 `toc`。

## 6. toc

```bash
zotero-skill toc <attachment_key>
```

用途：

- 按附件 key 读取一个 PDF 的目录。

输入：

- `attachment_key`：来自 `items` 或 `attachments`。

关键输出字段：

- `attachment_key`
- `file_path`
- `has_toc`
- `toc_count`
- `toc`

`toc` 每项包含：

- `level`
- `title`
- `page`

行为约定：

- 若 PDF 有书签目录，返回目录列表。
- 若 PDF 没有目录，返回 `has_toc=false` 和空列表。

## 7. toc-from-paper

```bash
zotero-skill toc-from-paper <paper_key>
```

用途：

- 按论文 key 自动选择本地 PDF，并读取目录。

输入：

- `paper_key`

自动选择规则：

- 只在该论文自己的附件中选择。
- 只考虑 PDF 附件。
- 优先选择本地存在的第一个 PDF。

关键输出字段：

- `paper_key`
- `title`
- `year`
- `selected_attachment_key`
- `selected_attachment_title`
- `pdf_attachment_keys`
- `has_toc`
- `toc_count`
- `toc`
- `file_path`

适用时机：

- 一般只有一个 PDF 附件。
- 你只有 `paper_key`，不想先自己挑附件。

## 8. extract-pdfs

```bash
zotero-skill extract-pdfs <collection_key>
```

用途：

- 提取并缓存一个分类中所有本地 PDF 的正文文本。

输入：

- `collection_key`

关键输出字段：

- `attachment_key`
- `file_path`
- `cache_text_path`
- `cache_json_path`
- `text_length`
- `page_count`
- `cached`
- `error`

适用时机：

- 摘要和目录都不够。
- 需要继续看正文。

约束：

- 不要默认对所有分类大规模执行。
- 先缩小候选范围，再提取。

## 9. summaries

```bash
zotero-skill summaries --collection-key <collection_key>
zotero-skill summaries --collection-key <collection_key> --requirement "<需求>"
zotero-skill summaries --attachment-key <attachment_key>
```

用途：

- 查看历史分析摘要。
- 复用过去已经写过的结论。

常见输入方式：

- 按分类查看。
- 按分类 + 需求查看。
- 按附件查看。

关键输出字段：

- `attachment_key`
- `paper_key`
- `paper_title`
- `requirement`
- `verdict`
- `summary`
- `evidence`
- `pdf_cache_text_path`
- `storage_path`

适用时机：

- 优先复用已有分析。
- 避免重复阅读 PDF 或重复消耗 token。

## 10. save-summary

```bash
zotero-skill save-summary --attachment-key <attachment_key> --requirement "<需求>" --verdict match|maybe|not_match|unknown --summary-file <文件>
```

用途：

- 写入一条新的需求摘要。

输入：

- `attachment_key`
- `requirement`
- `verdict`
- `summary-file` 或 `summary`
- 可选 `--evidence`

`verdict` 取值：

- `match`
- `maybe`
- `not_match`
- `unknown`

写入原则：

- 只有在实际看过摘要、目录、正文缓存或 PDF 后再写。
- 摘要应写成“论文内容概述 + 对当前需求是否匹配”。
- 同一篇 PDF 可以针对不同需求写不同摘要。

## 11. export-abstracts

```bash
zotero-skill export-abstracts <collection_key> [<collection_key2> ...] [--format md|json|both] [--output <path>]
```

用途：

- 将一个或多个分类下的论文标题和摘要导出为 Markdown 或 JSON。
- 每篇论文只含标题、年份（可选）、摘要三字段。

输入：

- `collection_keys`：来自 `collections` 的分类 key，可传多个。

输出格式：

- `--format md`（默认）：Markdown，含分类面包屑路径（`# 父 / 子`）。
- `--format json`：JSON。
- `--format both`：同时导出 .md 和 .json（后缀由 `with_suffix` 处理）。

输出目标：

- 不指定 `--output`：输出到 stdout。`--format md` 输出 Markdown，`--format json/both` 输出 JSON。
- 指定 `--output <path>`：写入文件。`--format both` 时路径后缀被替换为 .md / .json。

JSON 结构：

```json
[
  {
    "collection_path": "父 / 子",
    "papers": [
      {"title": "...", "year": "2024", "abstract": "..."}
    ]
  }
]
```

Markdown 结构：

```markdown
# 父 / 子

## Title (2024)
abstract text

---
```

适用时机：

- 需要将某几个分类下的论文摘要落地为文件。
- 需要 AI 快速浏览一批论文的标题和摘要。

## 最小工作流

最小分类定位：

1. `collections`
2. 用 `path` 或 `key` 选中分类

最小论文定位：

1. `items <collection_key>`
2. 取 `paper_key`

最小结构查看：

1. `toc-from-paper <paper_key>`
2. 若已知附件则直接 `toc <attachment_key>`

最小内容查看：

1. `abstract <paper_key>`
2. 不够再 `extract-pdfs <collection_key>`

最小复用流程：

1. `summaries ...`
2. 没有可复用摘要时再继续读摘要、目录或正文
3. 最后 `save-summary`
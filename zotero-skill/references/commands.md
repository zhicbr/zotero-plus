# 原子命令

本文件只说明命令本身，不预设具体任务场景。

## 命令总表

```bash
zotero-skill doctor
zotero-skill backup [--max-keep <count>]
zotero-skill auth [--app-name <name>]
zotero-skill cache-status <collection_key> [-r]
zotero-skill collections
zotero-skill items <collection_key> [-r]
zotero-skill abstract <paper_key>
zotero-skill attachments <collection_key> [--pdf-only] [-r]
zotero-skill toc <attachment_key>
zotero-skill toc-from-paper <paper_key>
zotero-skill extract-pdfs <collection_key> [-r] [--force]
zotero-skill summaries [--collection-key <collection_key> [-r]] [--requirement "<需求>"] [--attachment-key <attachment_key>]
zotero-skill save-summary --attachment-key <attachment_key> --requirement "<需求>" --verdict match|maybe|not_match|unknown --summary-file <文件>
zotero-skill export-abstracts <collection_key...> [-r] [--format md|json|both] [--output <path>]
zotero-skill search <collection_key> --keywords <kw1> [kw2...] [-r] [--paper-key <paper_key>] [--exclude <excl...>] [--scope all|pdf|abstract]
zotero-skill create-collection <name> [--parent <collection_key>] [--dry-run]
zotero-skill rename-collection <collection_key> <new_name> [--dry-run]
zotero-skill delete-empty-collection <collection_key> [--dry-run]
zotero-skill add-to-collection <paper_key> <collection_key> [--dry-run]
zotero-skill remove-from-collection <paper_key> <collection_key> [--dry-run]
zotero-skill move-paper <paper_key> --to <target_collection_key> [--from <source_collection_key>] [--dry-run]
zotero-skill add-tag <paper_key> <tag> [--dry-run]
zotero-skill remove-tag <paper_key> <tag> [--dry-run]
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

## 2. backup

```bash
zotero-skill backup [--max-keep <count>]
```

用途：

- 手动为 `zotero.sqlite` 数据库及 WAL 事务日志创建一份一致的热快照备份。
- 在任何实际写操作（归类、改名、移动等）执行前，系统底层也会自动执行此备份。
- 默认自动轮转并保留最新的 10 份快照。

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
zotero-skill items <collection_key> -r
```

用途：

- 查看一个分类中的论文条目。
- 同时返回每篇论文的附件信息。
- 添加 `-r` / `--recursive` 可穿透检索该分类及其所有子分类中的论文条目（自动去重）。

输入：

- `collection_key`：来自 `collections` 的分类 key。
- `-r` / `--recursive`：可选，递归包含所有子分类文献。

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
zotero-skill attachments <collection_key> -r
```

用途：

- 列出一个分类中的全部附件。
- 用 `--pdf-only` 仅保留 PDF。
- 添加 `-r` / `--recursive` 可聚合该分类及其所有子分类下的附件清单（自动按附件 key 去重）。

输入：

- `collection_key`
- `-r` / `--recursive`：可选，穿透子分类。

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
zotero-skill extract-pdfs <collection_key> -r
zotero-skill extract-pdfs <collection_key> --force
```

用途：

- 提取并缓存一个分类中所有本地 PDF 的正文文本。
- 添加 `-r` / `--recursive` 可递归提取其所有子分类下的本地 PDF。

输入：

- `collection_key`
- `-r` / `--recursive`：可选，递归提取子分类。
- `--force`：可选，已存在缓存时强制重新提取。

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
- 先用 `cache-status` 评估缺口，或先缩小候选范围后再提取。

## 9. summaries

```bash
zotero-skill summaries --collection-key <collection_key>
zotero-skill summaries --collection-key <collection_key> -r
zotero-skill summaries --collection-key <collection_key> --requirement "<需求>"
zotero-skill summaries --attachment-key <attachment_key>
```

用途：

- 查看历史分析摘要。
- 复用过去已经写过的结论。
- 添加 `-r` / `--recursive` 可在指定分类及其所有子分类中匹配历史摘要。

常见输入方式：

- 按分类查看（支持 `-r` 递归）。
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
zotero-skill export-abstracts <collection_key> [<collection_key2> ...] [-r] [--format md|json|both] [--output <path>]
```

用途：

- 将一个或多个分类下的论文标题和摘要导出为 Markdown 或 JSON。
- 每篇论文只含标题、年份（可选）、摘要三字段。
- 添加 `-r` / `--recursive` 可递归导出各个分类及其所有子分类下的论文条目。

输入：

- `collection_keys`：来自 `collections` 的分类 key，可传多个。
- `-r` / `--recursive`：可选，递归包含所有子分类。

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

## 12. search

```bash
zotero-skill search <collection_key> --keywords <kw1> [kw2...]
zotero-skill search <collection_key> --keywords <kw1> [kw2...] -r
zotero-skill search <collection_key> --paper-key <paper_key> --keywords <kw1> [kw2...]
zotero-skill search <collection_key> --keywords <kw1>... --scope abstract|pdf|all
zotero-skill search <collection_key> --keywords <kw1>... --exclude <excl1>...
zotero-skill search <collection_key> --keywords <kw1>... --snippet-radius 100 --all-papers
```

用途：

- 在指定分类中，快速检索论文摘要与已缓存的 PDF 正文文本。
- 提取关键词出现的频次、位置上下文片段（Snippet）以及排除词过滤。
- 添加 `-r` / `--recursive` 可穿透检索该分类及其所有子分类下的论文与全文缓存。
- 避免为了确认关键词而将整篇 PDF 全文读入大模型上下文。

输入参数：

- `collection_key`：分类 key（必填）。
- `-r` / `--recursive`：可选，递归搜索所有子分类。
- `--paper-key`：可选，限定在单篇论文中检索。
- `--keywords`：待检索的一个或多个关键词（不区分大小写，必填）。
- `--exclude`：可选，排除包含这些关键词的论文。
- `--scope`：检索范围，可选 `all`（默认）、`abstract`（仅摘要）、`pdf`（仅已缓存 PDF）。
- `--snippet-radius`：上下文截取字符半径（默认 100 字符）。
- `--all-papers`：是否在结果中包含 0 命中的论文（默认仅返回命中论文）。
- `--json-output`：可选，将搜索结果 JSON 写入文件。

关键输出字段：

- `paper_key`：论文 key。
- `title`：论文标题。
- `matched`：是否匹配成功（命中关键词且未被排除）。
- `total_hits`：命中的总关键词频次。
- `hit_keywords`：命中的关键词列表。
- `abstract_hits`：摘要中各关键词的命中数与前后文片段。
- `pdf_hits`：各 PDF 附件中关键词的命中数与前后文片段。
- `pdf_cache_status`：`cached`（已有正文缓存）、`not_cached`（未提取缓存）、`no_pdf`（无本地 PDF）。
- `excluded`：是否因命中排除词被剔除。
- `exclude_reason`：剔除原因。

适用时机：

- 用户提出具体技术点、算法名或研究对象过滤时（如 `剪枝`、`LoRA`、`TinyML`）。
- 快速判断某篇论文是否真正讨论了目标技术，而不是仅在参考文献里提了一句。

## 13. cache-status

```bash
zotero-skill cache-status <collection_key>
zotero-skill cache-status <collection_key> -r
```

用途：

- 快速评估某个分类（或整棵子树）的数据就绪度。
- 一目了然查看：文献总数、本地 PDF 存在情况、正文缓存就绪率、已有 AI 摘要数及未缓存附件列表。
- 给出精准的下一步操作建议（如缺失本地文件提醒、一键提取命令建议等）。

输入参数：

- `collection_key`：分类 key（必填）。
- `-r` / `--recursive`：可选，穿透体检该分类及其所有子分类。
- `--json-output`：可选，保存诊断结果为 JSON。

关键输出字段：

- `collection_name` / `collection_path`：分类名与完整层级路径。
- `is_recursive`：是否为递归层级体检。
- `subcollection_count`：子分类总数。
- `total_papers`：论文条目总数。
- `papers_with_pdf` / `papers_without_pdf`：含/不含 PDF 的论文数。
- `papers_with_abstract`：有摘要记录的论文数。
- `total_pdf_attachments` / `local_pdf_attachments` / `missing_pdf_attachments`：PDF 附件总数及本地文件存在/缺失数。
- `cached_pdf_texts` / `uncached_pdf_texts`：已提取正文缓存数与未提取数。
- `cache_percentage`：本地 PDF 提取完成百分比（0.0% - 100.0%）。
- `status`：状态码，`ready`（全部就绪）、`partially_cached`（部分缓存）、`no_cache`（未缓存）、`empty`（无条目）。
- `suggestions`：根据现状自动生成的下一步指引与命令建议列表。
- `uncached_attachments`：未缓存的附件列表清单（含 `attachment_key`、`attachment_title`、`has_local_file`）。

适用时机：

- 在开始大规模文献分析或综述前，快速摸底数据状态。
- 判断是否需要先执行 `extract-pdfs`，避免盲目全文提取。

## 14. auth

```bash
zotero-skill auth [--app-name <name>]
```

用途：

- 向运行中的 Zotero 桌面端发起本地写入权限申请。
- 会唤起 Zotero 界面弹窗提示用户授权，用户点击“始终允许”后持久化保存本地 API Key。

## 15. create-collection

```bash
zotero-skill create-collection <name> [--parent <collection_key>] [--dry-run]
```

用途：

- 创建一个新分类。可指定父分类 key（来自 `collections`）。
- `--dry-run` 支持预演。

## 16. rename-collection

```bash
zotero-skill rename-collection <collection_key> <new_name> [--dry-run]
```

用途：

- 重命名现有分类。

## 17. delete-empty-collection

```bash
zotero-skill delete-empty-collection <collection_key> [--dry-run]
```

用途：

- 安全删除**完全为空**的分类。
- 底层强校验：若分类下包含任何论文条目或子分类，拒绝删除并报错，防止误删文献。

## 18. add-to-collection

```bash
zotero-skill add-to-collection <paper_key> <collection_key> [--dry-run]
```

用途：

- 将指定论文条目关联进目标分类。

## 19. remove-from-collection

```bash
zotero-skill remove-from-collection <paper_key> <collection_key> [--dry-run]
```

用途：

- 将指定论文条目从某分类中移出（不删除文献本身）。

## 20. move-paper

```bash
zotero-skill move-paper <paper_key> --to <target_collection_key> [--from <source_collection_key>] [--dry-run]
```

用途：

- 将论文从一个分类迁移至另一分类。
- 若省略 `--from` 且论文当前仅位于一个分类，自动将该分类作为来源。

## 21. add-tag & remove-tag

```bash
zotero-skill add-tag <paper_key> <tag_name> [--dry-run]
zotero-skill remove-tag <paper_key> <tag_name> [--dry-run]
```

用途：

- 为论文添加或移除标签（Tag）。

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
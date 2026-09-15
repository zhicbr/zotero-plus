---
name: zotero-skill
description: 用已经可直接调用的 `zotero-skill` 命令，按原子步骤完成本地 Zotero 分类定位、条目查看、论文摘要读取、PDF 目录读取、PDF 文本提取、历史摘要复用与新摘要写入。适用于用户要求按分类找论文、查看某篇论文摘要、查看某个 PDF 的目录、读取正文缓存或写回分析摘要的任务。
---

# Zotero Skill

前提：`zotero-skill` 命令已可直接调用。

读取 [references/commands.md](references/commands.md)。

## 核心原则

- 只使用已经封装好的 `zotero-skill ...` 命令。
- 本地数据随时可能变化，任何需要数据的场景或者用户提出质疑时，都应即时运行命令获取最新结果，不依赖之前命令的输出记忆或历史缓存。
- 优先使用已有结构化信息，再决定是否读取 PDF。
- 原子操作之间可以自由编排，但每一步都应有明确目的。
- 不要为了保险起见批量提取全部 PDF。
- 没有实际依据，不写摘要。

## 分类定位

`collections` 结果已经显式包含以下字段：

- `key`：分类唯一标识。
- `name`：分类名称。
- `parent_name`：直接父分类名称。
- `path`：完整层级路径，例如 `毕业设计 / 开题报告 / 新增`。
- `path_keys`：对应的层级 key 列表。
- `depth`：层级深度。

父分类与子分类仅起归类作用，各自独立包含论文，不存在论文继承关系：子分类的论文不属于父分类，父分类的论文也不属于子分类。`item_count` 只反映该分类自身的条目数。

定位分类时，优先级如下：

1. 优先使用用户明确给出的 `key`。
2. 否则优先匹配完整 `path`。
3. 若用户说“分类 A 下的分类 B”，优先匹配 `parent_name=A` 且 `name=B`。
4. 若仅给出一个可能重复的分类名，不要自行假定唯一结果。

## 原子操作概览

- `collections`：列出全部分类，并返回可直接用于定位层级的结构化字段。
- `items <collection_key>`：列出一个分类中的论文条目及其附件。
- `abstract <paper_key>`：读取 Zotero 中存储的论文摘要。
- `attachments <collection_key>`：列出分类中的附件；`--pdf-only` 可仅保留 PDF。
- `toc <attachment_key>`：按附件 key 读取一个 PDF 的目录。
- `toc-from-paper <paper_key>`：按论文 key 自动选择首个本地 PDF，并读取目录。
- `extract-pdfs <collection_key>`：提取并缓存分类内 PDF 正文文本。
- `summaries ...`：查看历史分析摘要。
- `save-summary ...`：写入新的需求摘要。
- `export-abstracts <collection_key...>`：将一个或多个分类下的论文标题和摘要导出为 Markdown 或 JSON。

## 推荐顺序

1. 先 `collections`，明确分类。
2. 再 `items`，明确候选论文。
3. 先读 `abstract`。
4. 需要了解结构时读 `toc-from-paper` 或 `toc`。
5. 需要看本地 PDF 时再用 `attachments`。
6. 先查 `summaries`。
7. 摘要不够时才 `extract-pdfs`。
8. 有明确判断后再 `save-summary`。
9. 需要将批量论文摘要落地为文件时，用 `export-abstracts`。

## 输出要求

默认输出应尽量整理为人可读结果，而不是直接抛原始 JSON。

至少优先整理这些信息：

- 分类
- 论文标题
- 年份
- 命中理由
- 使用了哪一种依据：摘要、目录、正文缓存、历史摘要
- 下一步建议
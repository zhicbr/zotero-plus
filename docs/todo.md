# TODO

## 已完成

### 原始目标与需求

- [x] 明确整体目标：从 Zotero 获取论文，到定位 PDF、提取文本、做基础判断，再逐步整理成可供 AI 调用的能力。
- [x] 明确当前阶段不是直接做完整 skill，而是先搞清需求、边界、实现方式，再逐步编码。
- [x] 明确数据来源与处理链路。
- [x] 明确非目标：不做图片 OCR、不做表格抽取、不做复杂版面理解、不先接复杂大模型流程。

### Zotero 数据获取

- [x] 能读取 Zotero 分类列表。
- [x] 能根据指定分类获取论文条目。
- [x] 能获取论文基础元信息：标题、作者、年份、条目 key、所属分类、附件信息。
- [x] 能识别分类层级关系，并显式输出 `parent_name`、`path`、`path_keys`、`depth`。
- [x] 已从原先的云端 API / PyZotero 方向切换为本地 SQLite 方案，并跑通当前实现。

### 本地 PDF 定位

- [x] 能根据附件信息定位本地 PDF。
- [x] 能识别附件是否为 PDF。
- [x] 能识别 PDF 是否存在于本地。
- [x] 能处理没有 PDF、附件不是 PDF、路径不存在等情况。

### PDF 文本提取

- [x] 已使用 PyMuPDF 提取 PDF 文本。
- [x] 已保存 PDF 文本缓存。
- [x] 已保存 PDF 文本元数据缓存。
- [x] 已能在重复执行时复用已提取缓存。

### 论文内容辅助读取

- [x] 已支持读取 Zotero 中存储的论文摘要：`abstract <paper_key>`。
- [x] 已支持读取 PDF 目录：`toc <attachment_key>`。
- [x] 已支持按论文自动选 PDF 并读取目录：`toc-from-paper <paper_key>`。

### 分析与缓存复用

- [x] 已支持查看历史分析摘要：`summaries ...`。
- [x] 已支持写入需求相关摘要：`save-summary ...`。
- [x] 已将“论文摘要 + 当前需求匹配概述”作为可复用缓存保存。

### 自动化与接口

- [x] 已提供原子命令：`collections`、`items`、`attachments`、`abstract`、`toc`、`toc-from-paper`、`extract-pdfs`、`summaries`、`save-summary`、`doctor`。
- [x] 已整理为可被 AI 调用的本地 skill。
- [x] 已让 skill 文档只围绕原子操作展开。
- [x] 已让分类定位更适合 AI：优先按 `path` 或 `key`。

### 原始阶段性路径

- [x] 阶段 1：跑通“分类 -> 论文 -> PDF 可用性”最小闭环。
- [x] 阶段 2：加入 PDF 文本提取与缓存。
- [x] 阶段 3：加入基础筛选与摘要复用能力。
- [x] 阶段 4：整理为清晰命令与可被 AI 调用的 skill。
- [x] 阶段 5：完成当前这版 skill 化落地。

### 路径与缓存复用

- [x] 拆分“稳定缓存目录”和“临时导出目录”，不要再共用一个 `output` 概念。
- [x] 为稳定缓存增加单独配置项，例如 `ZOTERO_CACHE_DIR`。
- [x] 让 `pdf_text_cache` 与 `analysis_summaries` 永远从同一个固定目录读写，不受当前工作目录影响。
- [x] 保留“当前执行目录写文件”的能力，但仅用于一次性导出或临时中间文件。
- [x] 明确 `--json-output`、未来可能新增的 `--output-dir`、缓存目录三者的职责边界。
- [x] 让 `doctor` 显式输出实际生效的缓存目录、导出目录解析结果。
- [x] 设计并实现现有缓存迁移方案，避免旧 `output/` 下的数据失效或丢失。
- [x] 更新 skill 文档，写清“缓存找哪里”“临时文件写哪里”“AI 不需要关心哪一层路径”。

### 正文与摘要关键词搜索

- [x] 激活并完善 `src/zotero_plus/paper_filter.py`，接入 CLI 原子命令 `search`。
- [x] 明确搜索范围：支持在指定分类（`collection_key`）或单篇论文（`--paper-key`）中检索。
- [x] 支持正文全文检索与纯摘要检索（优先匹配已缓存的 PDF 纯文本，未提取标明状态，避免重复提取）。
- [x] 返回结构化结果：命中关键词、频次统计、前后文上下文 Snippet 片段（默认前后 100 字）、来源缓存路径。
- [x] 支持包含词（`--keywords`）与排除词（`--exclude`）布尔逻辑过滤。

### 分类层级递归检索

- [x] 为 `items`、`attachments`、`extract-pdfs`、`export-abstracts`、`search`、`summaries`、`cache-status` 子命令增加 `--recursive` / `-r` 选项。
- [x] 自动递归聚合指定分类及其所有嵌套子孙分类中的全部论文条目、附件及搜索范围，并自动去重。
- [x] 解决深层多级分类手动逐个查询繁琐的痛点，支持层级穿透体检与穿透全文检索。

### 分类数据就绪度体检

- [x] 新增 `cache-status <collection_key> [-r]` 命令。
- [x] 统计并直观输出该分类的资产就绪状态：总文献数、本地 PDF 附件数、已完成文本提取缓存数、未提取数、已有 AI 摘要打标数、就绪百分比。
- [x] 根据分类与缓存现状自动生成下一步智能建议（如缺失本地文件排查、一键提取命令建议等）。
- [x] 供用户或 AI 在执行大规模分析任务前一键评估数据完整度与缓存缺口。

## TODO

### 本地高光划线与阅读笔记

- [ ] 从本地 `zotero.sqlite` 中查询 `itemAnnotations` 表，读取用户在 Zotero PDF 阅读器中标记的高光原文（Highlight）、便签批注（Note）、划线颜色及所在页码。
- [ ] 从 `itemNotes` 表中读取挂在条目下的独立笔记/富文本笔记内容。
- [ ] 新增对应原子命令（如 `annotations <paper_key>`、`notes <paper_key>`）。
- [ ] 让 AI 能够优先根据用户自己的阅读心血与高光做针对性总结和提炼。

### 标签检索与过滤

- [ ] 支持读取 Zotero 本地数据库的标签体系。
- [ ] 新增 `tags` 命令：列出所有 Tag 及其关联的条目数。
- [ ] 支持在 `items` 中按 Tag 过滤：`items <collection_key> --tag <tag_name>` 或跨分类查找 `items --tag <tag_name>`。

### 统一 CLI 命令入口

- [ ] 在 `pyproject.toml` 的 `[project.scripts]` 中同时声明 `zotero-plus` 和 `zotero-skill` 两个入口。
- [ ] 让两者在命令行完全等价，减少双命名带来的认知负担。
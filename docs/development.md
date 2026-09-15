# 功能开发

## 涉及文件

- `src/zotero_plus/models.py` — 新增数据结构
- `src/zotero_plus/config.py` — 配置与路径管理
- `src/zotero_plus/zotero_client.py` — 新增 SQL 查询
- `src/zotero_plus/pipeline.py` — 业务逻辑 / 格式化
- `src/zotero_plus/cli.py` — 新增子命令
- `zotero-skill/references/commands.md` — 命令参考
- `zotero-skill/SKILL.md` — 原子操作概览 + 推荐顺序

## 项目约定

- stdout 始终 JSON，文件写入由参数控制
- 缓存目录（PDF 文本与摘要）固定在 `ZOTERO_CACHE_DIR`（默认在 Zotero 数据旁），不污染工作目录
- 错误用 `ValueError`，`main()` 统一捕获输出 stderr，exit code 2
- 分类定位用 key，不用名称
- `--json-output` 为通用文件输出参数，非 JSON 格式用独立参数
- 路径分隔符用 `/`

## 测试

- 用 `zotero-skill` 命令测试（或直接运行 `bin/zotero-skill.bat`）
- 用真实数据，不构造假参数
- 覆盖正常路径和异常输入
- 写文件测试路径落到 `output/`

## 收尾	

- 若修改了 `zotero-skill/` 下的文档，同步覆盖全局 Agent 目录：
  `xcopy /E /I /Y "zotero-skill" "$env:USERPROFILE\.gemini\config\skills\zotero-skill"`
- 删除测试产物
- `git status` 确认无遗留

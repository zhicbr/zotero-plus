# Zotero Skill 配置

## 1. `.env`

项目根目录 `.env`：

```env
# 示例配置（请根据你本地 Zotero 的实际路径修改）
ZOTERO_SQLITE_PATH=D:/path/to/zotero_storage/zotero.sqlite
ZOTERO_STORAGE_DIR=D:/path/to/zotero_storage/storage
ZOTERO_CACHE_DIR=D:/path/to/zotero_storage/zotero_plus_cache
ZOTERO_OUTPUT_DIR=output
```

- `ZOTERO_CACHE_DIR`: 持久化缓存根目录（PDF 文本、AI 分析摘要），独立存放在 Zotero 数据旁。
- `ZOTERO_OUTPUT_DIR`: 临时/手动导出默认目录。

## 2. CLI 快捷脚本配置

方式一（推荐）：直接将本项目的 `bin/` 目录添加到系统 `PATH` 环境变量中。

方式二：将 `bin/zotero-skill.bat` 复制到一个已在 `PATH` 中的全局脚本目录（如 `C:\Users\<username>\bin` 或自定义工具目录）：

```cmd
@echo off
uv run --project "D:/path/to/zotero-plus" --env-file "D:/path/to/zotero-plus/.env" zotero-plus %*
```

## 3. Skill 配置同步到 Agent

项目内部的 `zotero-skill/` 目录是 Git 维护的源码版本。
当修改了 `zotero-skill/SKILL.md` 或相关参考文档后，执行以下命令同步覆盖到 Agent 的配置目录：

```powershell
xcopy /E /I /Y "zotero-skill" "$env:USERPROFILE\.gemini\config\skills\zotero-skill"
```

## 4. 测试

打开新终端后执行：

```powershell
zotero-skill --help
zotero-skill collections
```

再执行：

```powershell
zotero-skill items <collection_key>
zotero-skill attachments <collection_key> --pdf-only
zotero-skill extract-pdfs <collection_key>
zotero-skill summaries --collection-key <collection_key>
```
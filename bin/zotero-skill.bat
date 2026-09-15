@echo off
setlocal
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
set "PROJECT_DIR=%PROJECT_DIR:\=/%"
uv run --project "%PROJECT_DIR%" --env-file "%PROJECT_DIR%/.env" zotero-plus %*
endlocal

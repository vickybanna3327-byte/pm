@echo off
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :8000') do (
  if not "%%p"=="" taskkill /PID %%p /F
)

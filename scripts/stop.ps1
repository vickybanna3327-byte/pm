$ErrorActionPreference = "Stop"
$port = 8000
$processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($null -eq $processes) {
  Write-Host "No process is listening on port $port."
  exit 0
}
foreach ($process in $processes) {
  if ($process.OwningProcess) {
    Stop-Process -Id $process.OwningProcess -Force
  }
}

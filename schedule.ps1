chcp 65001 > $null

# 注册 Windows 任务计划：每小时自动爬取 XMU 待办
# 以管理员身份运行 PowerShell，执行：
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#   .\schedule.ps1

$taskName = "XMU-TronClass-Scraper"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonDir = Split-Path -Parent (Get-Command python).Source
$pythonwExe = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path $pythonwExe)) {
    $pythonwExe = (Get-Command python).Source
}

$action = New-ScheduledTaskAction `
    -Execute $pythonwExe `
    -Argument "main.py --run" `
    -WorkingDirectory $projectDir

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "每小时爬取 XMU TronClass 待办事项" `
    -Force

Write-Host "任务 '$taskName' 已注册，将每小时自动执行一次。"
Write-Host "可在任务计划程序 (taskschd.msc) 中查看和管理。"

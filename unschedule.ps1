chcp 65001 > $null

# 删除 XMU TronClass 定时爬取任务
$taskName = "XMU-TronClass-Scraper"

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

if ($?) {
    Write-Host "任务 '$taskName' 已删除。"
} else {
    Write-Host "任务 '$taskName' 不存在或已删除。"
}

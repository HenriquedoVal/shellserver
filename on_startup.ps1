$admin = ([Security.Principal.WindowsPrincipal] `
 [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
    Write-Error "Run this script as admin."
    exit 1
}

$shellserver_path = (Get-Command "shellserverw" | Select-Object -ExpandProperty Source)
if (-not $shellserver_path) {
    Write-Error "Is the '...\Python\Scripts' folder in PATH?"
    exit 1
}

$user = "$env:userdomain\$env:username"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$action = New-ScheduledTaskAction -Execute $shellserver_path -Argument "run --permanent"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 

Register-ScheduledTask -TaskName "ShellServer" -Trigger $trigger -Action $action -Settings $settings

$admin = ([Security.Principal.WindowsPrincipal] `
 [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
  Write-Error "Run this script as admin."
  exit 1
}

$user = "$env:userdomain\$env:username"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$action = New-ScheduledTaskAction -Execute "pythonw" -Argument "-m shellserver --permanent"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName "ShellServer" -Trigger $trigger -Action $action -Settings $settings

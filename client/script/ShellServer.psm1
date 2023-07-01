#
# Set port to use. It shouldn't have collisions as Udp, but user might want to change it.
# Also will have to change in __init__.py
#

# if you change the port number here, you must change below too
$Port = 5432

Register-EngineEvent PowerShell.Exiting -action {
  $Sock = New-Object System.Net.Sockets.UdpClient
  # Change port number below if you changed above. Don't use variables.
  $Sock.Connect('127.0.0.1', 5432)
  $Sock.Send([System.Text.Encoding]::UTF8.GetBytes('2Exit'))
} > $nul

#
# Create socket objects to interact with server
#

$LocalHost = '127.0.0.1'
$Encoder = [System.Text.Encoding]::UTF8
$Sock = New-Object System.Net.Sockets.UdpClient
$Sock.Client.ReceiveTimeout = 3000
$Sock.Connect($LocalHost, $Port)

$Address = [System.Net.IpAddress]::Parse($LocalHost)
$End = New-Object System.Net.IPEndPoint $Address, $Port

$buffer = $Encoder.GetBytes('2Initpwsh')
$Sock.Send($buffer) > $nul

#
# Define functions that will interact with server
#

function global:prompt {
  $origDollarQuestion = $global:?
  $origLastExitCode = $global:LASTEXITCODE

  # if venv > 0: venv == venv.length
  $venv = $env:VIRTUAL_ENV
  if ($venv) {
    $venv = ($venv.Substring($venv.LastIndexOf('\')+1)).Length + 3
  }
  else {
    Write-Host ''
    $venv = [int] [bool] $venv
  }

  $width = $Host.UI.RawUI.BufferSize.Width - $venv
  $duration = (Get-History -Count 1).Duration

  if (-Not $duration) {
    $duration = 0.0
  }
  else {
    $duration = [string]$duration.TotalSeconds
  }

  $buffer = $Encoder.GetBytes('1' + [int] $origDollarQuestion + (Get-Location).Path + ";$width;$duration")
  $Sock.Send($buffer) > $nul

  try {$response = Receive-Msg}
  catch [System.Net.Sockets.SocketException] {
    Write-Host "Server didn't respond in time."

    function global:prompt {
      "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) "
    }
    Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
      [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
    }
    "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) "
  }
  $response = $response.Substring(1)
  $ExecutionContext.InvokeCommand.ExpandString($response)

  $global:LASTEXITCODE = $origLastExitCode
  if ($global:? -ne $origDollarQuestion) {
      if ($origDollarQuestion) {
          1+1
      } else {
          Write-Error '' -ErrorAction 'Ignore'
      }
  }
}


function p {
  param(
  [switch]$o,
  [switch]$a,
  [string]$path
  )

  if ($a.IsPresent) {
    if ($path) {
      $path = (Resolve-Path $path -ErrorAction 'Stop').Path
    }
    else {
      $path = (Get-Location).Path
    }
    $buffer = $Encoder.GetBytes("9$path")
    $Sock.Send($buffer) > $nul
    return
  }

  if (-not $path) {
    Set-Location
    return
  }

  if ($args) {
    $path += ' ' + $args -join ' '
  }

  $buffer = $Encoder.GetBytes("3$path")
  $Sock.Send($buffer) > $nul
  $response = Receive-Msg

  if (($response) -and ($o.IsPresent)) {
    Write-Output $response
  }
  elseif ($response) {
    Set-Location $response
  }
  elseif ($resPath = try {(Resolve-Path $path -ErrorAction 'Stop').Path} catch {}) {
    Set-Location $resPath
  }
  else {
    Write-Output "ShellServer: No match found."
  }
}


function pz {
  $buffer = $Encoder.GetBytes('4')
  $Sock.Send($buffer) > $nul
  $response = Receive-Msg
  $query = $args -Join ' '

  if ($query) {
    $answer = Write-Output $response | fzf --height=~20 --layout=reverse -q $query
  } else {
      $answer = Write-Output $response | fzf --height=~20 --layout=reverse
    }

  # send the user choice to server to adjust precedence
  $Sock.Send($Encoder.GetBytes('4' + $answer)) > $nul
  Set-Location $answer
}


function Get-ServerListDir {
  param($opts, $path)

  if ($path) {
    try {$resPath = (Resolve-Path $path -ErrorAction 'Stop').Path}
    catch {$resPath = (Get-Error).TargetObject}
  }
  else {
    $resPath = (Get-Location).Path
  }

  $buffer = $Encoder.GetBytes("5$opts;$resPath")
  $Sock.Send($buffer) > $nul
  $response = Receive-Msg
  if ($response) {
    $ExecutionContext.InvokeCommand.ExpandString($response)
  }
}


function ll {
  Get-ServerListDir '-cil' ($args -join ' ')
}


function la {
  Get-ServerListDir '-acil' ($args -join ' ')
}


function Switch-Theme {
  param(
    [Parameter()]
    [ArgumentCompletions('all', 'terminal', 'system', 'blue', 'readline')]
    $arg
  )

  if ($arg -eq 'readline') {
    Switch-ReadlineTheme
    return
  }

  $buffer = $Encoder.GetBytes("6$arg")
  $Sock.Send($buffer) > $nul
  if (($arg -eq 'terminal') -Or (-Not $arg)) {
    Switch-ReadlineTheme
  }
}


function Search-History {
  param(
    # Is there a better way to do this?
    [switch]$c, [switch]$a, [switch]$ac, [switch]$ca
  )

  $opt = ''
  if ($c.IsPresent) {
    $opt += 'c'
  }
  if ($a.IsPresent) {
    $opt += 'a'
  }
  if (($ac.IsPresent) -or ($ca.IsPresent)) {
    $opt = 'ac'
  }

  $width = $Host.UI.RawUI.BufferSize.Width
  $height = $Host.UI.RawUI.BufferSize.Height

  $arg = $args -join ';'
  $buffer = $Encoder.GetBytes("7$width;$height;$opt;$arg")
  $Sock.Send($buffer) > $nul

  $response = Receive-Msg
  $ExecutionContext.InvokeCommand.ExpandString($response)
}


function Switch-ServerTimeout {
  param([Parameter(Mandatory=$true)]$milliSeconds)
  $Sock.Client.ReceiveTimeout = $milliSeconds
}


function Switch-ServerOpt {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)]
    [ArgumentCompletions(
      'timeit',
      'no-timeit',
      'trackdir',
      'no-trackdir',
      'fallback',
      'no-fallback',
      'watchdog',
      'no-watchdog',
      'disable-git',
      'enable-git',
      'use-gitstatus',
      'use-git',
      'use-pygit2',
      'test-status',
      'no-test-status',
      'linear',
      'no-linear',
      'read-async',
      'no-read-async',
      'let-crash'
    )]
    $option
  )

  $buffer = $Encoder.GetBytes("2Set$option")
  $Sock.Send($buffer) > $nul

}

function Get-ShellServerBuffer {
  param(
    [switch]$k
  )

  $opt = ''
  if ($k.IsPresent) {
    $opt += 'k'
  }

  $buffer = $Encoder.GetBytes("8$opt")
  $Sock.Send($buffer) > $nul

  $response = Receive-Msg
  $ExecutionContext.InvokeCommand.ExpandString($response)
  
}

function Receive-Msg {
    $answer = ''
    $iterativeAnswer = $Encoder.GetString($Sock.Receive([ref] $End))

    while ($iterativeAnswer[0] -eq '1') {
        $answer += $iterativeAnswer.Substring(1)
        $iterativeAnswer = $Encoder.GetString($Sock.Receive([ref] $End))
    }

    $answer += $iterativeAnswer.Substring(1)
    return $answer
  }


#
# Misc. Front-end only functions, etc.
#

$FirstEnterKeyPress = 1
$LastCmdId = (Get-History -Count 1).Id

Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
  $line = $cursor = $nul
  [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)

  $venv = [int](Test-Path 'ENV:VIRTUAL_ENV')
  $currentCmdId = (Get-History -Count 1).Id

  if (($currentCmdId -ne $LastCmdId) -or (-not $line) -or ($FirstEnterKeyPress)) {
    $Script:LastCmdId = $currentCmdId

    # will treat the enter after an empty line as the first enter key press
    $Script:FirstEnterKeyPress = [int](-not $line)

    [Console]::SetCursorPosition(0, [Console]::GetCursorPosition().Item2 - (2 - $venv))
    Write-Host -NoNewline "`e[J`e[34m❯`e[0m $line"
  }

  [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()

}

$LightThemeColors = @{
  Command                = "DarkYellow"
  Comment                =  "`e[90m"
  ContinuationPrompt     = "DarkGray"
  Default                = "DarkGray"
  Emphasis               = "DarkBlue"
  InlinePrediction       = "DarkGray"
  Keyword                = "Green"
  ListPrediction         = "DarkYellow"
  ListPredictionSelected = "`e[34;238m"
  Member                 = "`e[34m"
  Number                 = "`e[34m"
  Operator               = "DarkGray"
  Parameter              = "DarkGray"
  Selection              = "`e[34;238m"
  String                 = "DarkCyan"
  Type                   = "`e[32m"
  Variable               = "Green"
}

$DarkThemeColors = @{
  Command                = "`e[93m"
  Comment                = "`e[32m"
  ContinuationPrompt     = "`e[34m"
  Default                = "`e[37m"
  Emphasis               = "`e[96m"
  InlinePrediction       = "`e[38;5;238m"
  Keyword                = "`e[92m"
  ListPrediction         = "`e[33m"
  ListPredictionSelected = "`e[48;5;238m"
  Member                 = "`e[97m"
  Number                 = "`e[97m"
  Operator               = "`e[90m"
  Parameter              = "`e[90m"
  Selection              = "`e[30;47m"
  String                 = "`e[36m"
  Type                   = "`e[34m"
  Variable               = "`e[92m"
}

$IsLightThemeSelected = 0
if ((Get-ItemProperty -Path HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize).SystemUsesLightTheme) {
  Set-PSReadLineOption -Colors $LightThemeColors
  $Script:IsLightThemeSelected = 1
} else {
  Set-PSReadLineOption -Colors $DarkThemeColors
  $Script:IsLightThemeSelected = 0
}


function Switch-ReadlineTheme {
  if ($IsLightThemeSelected -eq 0){
    Set-PSReadLineOption -Colors $LightThemeColors
    $Script:IsLightThemeSelected = 1
  } else {
    Set-PSReadLineOption -Colors $DarkThemeColors
    $Script:IsLightThemeSelected = 0
  }
}

#
# The server will respond the first communication with the completions
# for the 'p' function. It's safer to keep this in the end of file.
#

$buffer = $Encoder.GetBytes('2Get')
$Sock.Send($buffer) > $nul

$raw = Receive-Msg
$completions = @($raw -split ';')
$scriptBlock = {
    param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameters)
    $completions | Where-Object {
        $_ -like "$wordToComplete*"
    } | ForEach-Object {
          $_
    }
}

Register-ArgumentCompleter -CommandName p -ParameterName path -ScriptBlock $scriptBlock

Export-ModuleMember -Function @("p", "pz", "ll", "la",  "Search-History", "Switch-Theme", "Switch-ServerTimeout", "Switch-ServerOpt", "Get-ShellServerBuffer")

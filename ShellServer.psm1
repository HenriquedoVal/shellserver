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

$Buffer = $Encoder.GetBytes('2Initpwsh')
$Sock.Send($Buffer) > $nul

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
  } else {
      Write-Host ''
      $venv = [int] [bool] $venv
    }

  $width = $Host.UI.RawUI.BufferSize.Width - $venv
  $duration = (Get-History -Count 1).Duration
  if (-Not $duration) {
      $duration = 0.0
  } else {
      $duration = [string]$duration.TotalSeconds
    }

  $Buffer = $Encoder.GetBytes('1' + [int] $origDollarQuestion + (Get-Location).Path + ";$width;$duration")
  $Sock.Send($Buffer) > $nul

  try {$response = receiver}
  catch [System.Net.Sockets.SocketException] {
    Write-Host "Server didn't respond in time."
    function global:prompt { "$(Get-Location)> " }
    Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
      [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
    }
    return "$(Get-Location)> "
  }
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
  [string]$path
  )

  if (-not $path) {
      Set-Location
      return
  }
  
  if ($args) {
    $path += ' ' + $args -join ' '
  }

  $Buffer = $Encoder.GetBytes("3$path")
  $Sock.Send($Buffer) > $nul
  $response = receiver

  if (($response) -and ($o.IsPresent)) {
      Write-Output $response
    }
  elseif ($response) {
   Set-Location $response
  }
  elseif (
    $resPath = try {(Resolve-Path $path -ErrorAction 'Stop').Path} catch {}
  ) {
      Set-Location $resPath
    }
  else {
    Write-Output "ShellServer: No match found."
  }
}


function pz {
  $Buffer = $Encoder.GetBytes('4')
  $Sock.Send($Buffer) > $nul
  $response = receiver
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


function pls {
  param($opts, $path)

  if ($path) {

    try {$resPath = (Resolve-Path $path -ErrorAction 'Stop').Path} catch {$resPath = (Get-Error).TargetObject}
  } else {
      $resPath = (Get-Location).Path
    }

  $Buffer = $Encoder.GetBytes("5$opts;$resPath")
  $Sock.Send($Buffer) > $nul
  $response = receiver
  $ExecutionContext.InvokeCommand.ExpandString($response)
}


function ll {
  pls '-cil' ($args -join ' ')
}


function la {
  pls '-acil' ($args -join ' ')
}


function Switch-Theme {
  [CmdletBinding()]
  param(
    [Parameter()]
    [ArgumentCompletions('all', 'terminal', 'system', 'blue')]
    $arg
  )

  $Buffer = $Encoder.GetBytes("6$arg")
  $Sock.Send($Buffer) > $nul
  Start-Sleep .1
  if (($arg -eq 'terminal') -Or (-Not $arg)) { PSThemeChange }
}


function Search-History {
  $width = $Host.UI.RawUI.BufferSize.Width
  $height = $Host.UI.RawUI.BufferSize.Height

  $arg = $args -join ' '
  $Buffer = $Encoder.GetBytes("7$arg;$width;$height")
  $Sock.Send($Buffer) > $nul

  $response = receiver
  $ExecutionContext.InvokeCommand.ExpandString($response)
}


function Set-ServerTimeout {
  param($arg)
  $Sock.Client.ReceiveTimeout = $arg
}


function Set-ServerOpt {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)]
    [ArgumentCompletions(
      'enable-git', 'disable-git', 'use-git', 'wait', 'verbose', 'let-crash'
    )]
    $Option
  )

  $Buffer = $Encoder.GetBytes("2Set$Option")
  $Sock.Send($Buffer) > $nul

}


function receiver {
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

$firstEnterKeyPress = 1
$lastCmdId = (Get-History -Count 1).Id

Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
  $line = $cursor = $null 
  [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)

  $venv = [int](Test-Path 'ENV:VIRTUAL_ENV')
  $currentCmdId = (Get-History -Count 1).Id

  if (($currentCmdId -ne $lastCmdId) -or (-not $line) -or ($firstEnterKeyPress)) {
    $Script:lastCmdId = $currentCmdId

    # will treat the enter after an empty line as the first enter key press
    $Script:firstEnterKeyPress = [int](-not $line)

    [Console]::SetCursorPosition(0, [Console]::GetCursorPosition().Item2 - (2 - $venv))
    Write-Host -NoNewline "`e[J`e[34m❯`e[0m $line"
  }

  [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()

}

$LightThemeColors = @{
  Command                = "DarkYellow"
  Comment                = "DarkGreen"
  ContinuationPrompt     = "DarkGray"
  Default                = "DarkGray"
  Emphasis               = "DarkBlue"
  InlinePrediction       = "DarkGray"
  Keyword                = "Green"
  ListPrediction         = "DarkYellow"
  ListPredictionSelected = "`e[30;5;238m"
  Member                 = "Black"
  Number                 = "Black"
  Operator               = "DarkGray"
  Parameter              = "DarkGray"
  Selection              = "`e[30;5;238m"
  String                 = "DarkCyan"
  Type                   = "Black"
  Variable               = "Green"
}

$DefaultThemeColors = @{
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

$SelectedLightTheme = 0
function FirstThemeCheck {
  if ((get-ItemProperty -Path HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize).SystemUsesLightTheme) {
    Set-PSReadLineOption -Colors $LightThemeColors
    $Script:SelectedLightTheme = 1
  } else {
    Set-PSReadLineOption -Colors $DefaultThemeColors
    $Script:SelectedLightTheme = 0
  }
}

FirstThemeCheck

function PSThemeChange {
  if ($SelectedLightTheme -eq 0){
    Set-PSReadLineOption -Colors $LightThemeColors
    $Script:SelectedLightTheme = 1
  } else {
    Set-PSReadLineOption -Colors $DefaultThemeColors
    $Script:SelectedLightTheme = 0
  }
}

#
# The server will respond the first communication with the completions
# for the 'p' function. It's safer to keep this in the end of file.
#

$raw = receiver
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

Export-ModuleMember -Function @("p", "pz", "pls", "ll", "la", "Switch-Theme", "Search-History", "Set-ServerTimeout", "Set-ServerOpt")

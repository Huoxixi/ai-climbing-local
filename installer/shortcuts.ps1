param([Parameter(Mandatory=$true)][string]$App, [Parameter(Mandatory=$true)][string]$Directory,
      [string[]]$Destinations = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')))
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($destination in $Destinations) {
    if (!(Test-Path -LiteralPath $destination -PathType Container)) { throw 'Shortcut destination is missing' }
    # Unicode literals are assembled explicitly for Windows PowerShell 5.1 without a BOM.
    $name = -join ([char[]](0x6500,0x5ca9,0x52a9,0x624b,0xff08,0x516c,0x5f00,0x7248,0xff09))
    $shortcut = $shell.CreateShortcut((Join-Path $destination ($name + '.lnk')))
    $shortcut.TargetPath = $App
    $shortcut.WorkingDirectory = $Directory
    $shortcut.Save()
}

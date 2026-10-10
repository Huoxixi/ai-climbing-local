param([Parameter(Mandatory=$true)][string]$App, [Parameter(Mandatory=$true)][string]$Directory,
      [string[]]$Destinations = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')),
      [string]$BackupDirectory, [switch]$Restore)
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$name = -join ([char[]](0x6500,0x5ca9,0x52a9,0x624b,0xff08,0x516c,0x5f00,0x7248,0xff09))
if ($Restore) {
    $manifest = Join-Path $BackupDirectory 'links.json'
    if (!(Test-Path -LiteralPath $manifest)) { return }
    $entries = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $entries) {
        $path = [IO.Path]::GetFullPath($entry.path)
        if (($Destinations | ForEach-Object { [IO.Path]::GetFullPath((Join-Path $_ ($name + '.lnk'))) }) -notcontains $path) { throw 'Unexpected shortcut path' }
        if (Test-Path -LiteralPath $path) {
            if ($shell.CreateShortcut($path).TargetPath -ne $App) { continue }
        }
        if ($entry.previous) {
            $backup = Join-Path $BackupDirectory $entry.backup
            if ([IO.Path]::GetFileName($entry.backup) -ne $entry.backup) { throw 'Unexpected backup path' }
            Copy-Item -LiteralPath $backup -Destination $path -Force
        } elseif (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    }
    return
}
$entries = @()
if ($BackupDirectory) {
    New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
    foreach ($destination in $Destinations) {
        $path = Join-Path $destination ($name + '.lnk')
        $previous = Test-Path -LiteralPath $path
        $backup = 'previous-' + $entries.Count + '.lnk'
        if ($previous) { Copy-Item -LiteralPath $path -Destination (Join-Path $BackupDirectory $backup) -Force }
        $entries += @{path=$path;previous=$previous;backup=$backup}
    }
    ConvertTo-Json -InputObject @($entries) | Set-Content -LiteralPath (Join-Path $BackupDirectory 'links.json') -Encoding UTF8
}
foreach ($destination in $Destinations) {
    if (!(Test-Path -LiteralPath $destination -PathType Container)) { throw 'Shortcut destination is missing' }
    # Unicode literals are assembled explicitly for Windows PowerShell 5.1 without a BOM.
    $shortcut = $shell.CreateShortcut((Join-Path $destination ($name + '.lnk')))
    $shortcut.TargetPath = $App
    $shortcut.WorkingDirectory = $Directory
    $shortcut.Save()
}

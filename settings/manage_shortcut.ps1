# Desktop shortcut manager (called by settings/shortcut.py, runs hidden)
param(
    [string]$BaseDir,
    [string]$Desktop,
    [string]$Action,
    [string]$Name,
    [string]$Target = "",
    [string]$Arguments = "",
    [string]$Icon = "",
    [string]$WorkDir = ""
)
$ErrorActionPreference = 'Stop'
$lnk = Join-Path $Desktop ($Name + '.lnk')
$ws = New-Object -ComObject WScript.Shell

switch ($Action) {
    'create' {
        $s = $ws.CreateShortcut($lnk)
        if ($Target) { $s.TargetPath = $Target }
        if ($Arguments) { $s.Arguments = $Arguments }
        if ($Icon) { $s.IconLocation = $Icon }
        if ($WorkDir) { $s.WorkingDirectory = $WorkDir }
        $s.Save()
        Write-Output 'created'
    }
    'delete' {
        if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Output 'deleted' }
        else { Write-Output 'absent' }
    }
    'read' {
        if (-not (Test-Path $lnk)) { Write-Output 'absent'; exit 0 }
        $s = $ws.CreateShortcut($lnk)
        Write-Output ("TARGET=" + $s.TargetPath)
        Write-Output ("ARGS=" + $s.Arguments)
    }
    'repair' {
        if (-not (Test-Path $lnk)) { Write-Output 'absent'; exit 0 }
        $s = $ws.CreateShortcut($lnk)
        # Up to date if Target already points into BaseDir
        if ($s.TargetPath -like "$BaseDir*") {
            Write-Output 'ok'
        } else {
            if ($Target) { $s.TargetPath = $Target }
            if ($Arguments) { $s.Arguments = $Arguments }
            if ($Icon) { $s.IconLocation = $Icon }
            if ($WorkDir) { $s.WorkingDirectory = $WorkDir }
            $s.Save()
            Write-Output 'updated'
        }
    }
    default { Write-Output 'unknown-action'; exit 1 }
}

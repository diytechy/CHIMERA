param(
    [string]$CsvPath = ".\hydraxia_vs_origen2.csv",
    [string[]]$PriorityFolders = @("structures", "features", "biomes", "biome-distribution")
)

$data = Import-Csv -Path $CsvPath

$sorted = $data | Sort-Object {
    $topFolder = ($_.RelativePathA -split '\\')[0]
    $priority = $PriorityFolders.IndexOf($topFolder)
    if ($priority -ge 0) { $priority } else { 999 }
}, RelativePathA

$copied = 0
foreach ($row in $sorted) {
    if ($row.Status -eq "FILE MISSING") {
        $source = Join-Path ${$row.RootA} (Join-Path ${$row.RelativePathA} ${$row.FileName})
        $destDir = Join-Path ${$row.RootB} ${$row.RelativePathA}
        $dest = Join-Path $destDir ${$row.FileName}
        
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        
        Copy-Item -Path $source -Destination $dest -Force
        Write-Host "Copied: $($row.FileName) -> $($row.RelativePathA)"
        
        $copied++
        if ($copied -ge 10) {
            Write-Host "`nReached 10 files copied. Exiting."
            break
        }
    }
}

Write-Host "`nTotal files copied: $copied"

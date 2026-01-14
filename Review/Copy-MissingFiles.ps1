param(
    [string]$CsvPath = ".\hydraxia_vs_origen2.csv",
    [string[]]$PriorityFolders = @("structures", "features", "biomes", "biome-distribution"),
    [hashtable]$ReplaceTable = @{
        "features/ores/distribution.yml" = "features/geological/deposits/distribution_hydraxia.yml"
        "technical_crap/" = ""
        "BASE" = "BASE_HYDRAXIA"
    }
)
$copyLim = 10
$data = Import-Csv -Path $CsvPath | ForEach-Object {
    $topFolder = ($_.RelativePathA -split '\\')[0]
    $priority = $PriorityFolders.IndexOf($topFolder)
    $_ | Add-Member -NotePropertyName Priority -NotePropertyValue $(if ($priority -ge 0) { $priority } else { 999 }) -PassThru
}

$sorted = $data | Sort-Object Priority, RelativePathA

$copied = 0
foreach ($row in $sorted) {
    if ($row.Status -eq "FILE MISSING") {
        $source = Join-Path $row.RootA (Join-Path $row.RelativePathA $row.FileName)
        $destDir = Join-Path $row.RootB $row.RelativePathA
        $dest = Join-Path $destDir $row.FileName
        
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        
        Copy-Item -Path $source -Destination $dest -Force
        
        $content = Get-Content -Path $dest -Raw
        foreach ($key in $ReplaceTable.Keys) {
            $content = $content -creplace [regex]::Escape($key), $ReplaceTable[$key]
        }
        Set-Content -Path $dest -Value $content -NoNewline
        
        Write-Host "Copied: $($row.FileName) -> $($row.RelativePathA)"
        
        $copied++
        if ($copied -ge $copyLim) {
            Write-Host "`nReached $copyLim files copied. Exiting."
            break
        }
    }
}

Write-Host "`nTotal files copied: $copied"

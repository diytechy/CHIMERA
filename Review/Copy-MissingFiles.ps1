param(
    [string]$CsvPath = ".\hydraxia_vs_origen2.csv",
    [string[]]$PriorityFolders = @("structures", "features", "biomes\equations","biomes", "biome-distribution"),
    [hashtable]$ReplaceTable = @{
        "features/ores/distribution.yml" = "features/geological/deposits/distribution_hydraxia.yml"
        "technical_crap/" = ""
        "BASE" = "BASE_HYDRAXIA"
		"ORES_COAL" = "HYDRAXIA_ORES_COAL"
		"ORES_DIAMOND" = "HYDRAXIA_ORES_DIAMOND"
		"ORES_EMERALD" = "HYDRAXIA_ORES_EMERALD"
		"ORES_GEODE" = "HYDRAXIA_ORES_GEODE"
		"ORES_GOLD" = "HYDRAXIA_ORES_GOLD"
		"ORES_MOUNTAINS" = "HYDRAXIA_ORES_MOUNTAINS"
		"ORES_REDSTONE" = "HYDRAXIA_ORES_REDSTONE"
        "CEILING_DRIPSTONE" = "CEILING_DRIPSTONE"
    }
)
$copyLim = 20
$data = Import-Csv -Path $CsvPath | ForEach-Object {
    $relPath = $_.RelativePathA
    $priority = 999
    for ($i = 0; $i -lt $PriorityFolders.Count; $i++) {
        if ($relPath.StartsWith($PriorityFolders[$i])) {
            $priority = $i
            break
        }
    }
    $_ | Add-Member -NotePropertyName Priority -NotePropertyValue $priority -PassThru
}

$sorted = $data | Sort-Object Priority, RelativePathA
$MissingFiles = $sorted | Where-Object { $_.Status -eq "FILE MISSING" }
$TotalMissing = $MissingFiles.Count
$copied = 0
foreach ($row in $MissingFiles) {
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

Write-Host "`nTotal files copied: $copied of $TotalMissing"

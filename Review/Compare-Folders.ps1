param(
    [string]$FolderA = "C:\Projects\Hydraxia2",
    [string]$FolderB = "C:\Projects\ORIGEN2",
	[string]$CompareOut = "hydraxia_vs_origen2.csv"
)

$filesA = Get-ChildItem -Path $FolderA -File -Recurse | Select-Object Name, FullName, @{N='Hash';E={(Get-FileHash $_.FullName -Algorithm MD5).Hash}}
$filesB = Get-ChildItem -Path $FolderB -File -Recurse | Select-Object Name, FullName, @{N='Hash';E={(Get-FileHash $_.FullName -Algorithm MD5).Hash}}

$groupA = $filesA | Group-Object Name
$groupB = $filesB | Group-Object Name

$results = foreach ($fileGroup in $groupA) {
    $fileName = $fileGroup.Name
    
    foreach ($fileA in $fileGroup.Group) {
        $relPathA = $fileA.FullName.Substring($FolderA.Length + 1)
        $relDirA = Split-Path $relPathA -Parent
        if ([string]::IsNullOrEmpty($relDirA)) { $relDirA = "." }
        
        $matchesB = $groupB | Where-Object Name -eq $fileName
        
        if ($fileGroup.Count -gt 1 -or ($matchesB -and $matchesB.Count -gt 1)) {
            [PSCustomObject]@{
                FileName = $fileName
                RootA = $FolderA
                RelativePathA = $relDirA
                Status = "MULTIPLE"
                RootB = $FolderB
                RelativePathB = ""
            }
        } elseif (-not $matchesB) {
            [PSCustomObject]@{
                FileName = $fileName
                RootA = $FolderA
                RelativePathA = $relDirA
                Status = "FILE MISSING"
                RootB = $FolderB
                RelativePathB = ""
            }
        } else {
            $fileB = $matchesB.Group[0]
            $relPathB = $fileB.FullName.Substring($FolderB.Length + 1)
            $relDirB = Split-Path $relPathB -Parent
            if ([string]::IsNullOrEmpty($relDirB)) { $relDirB = "." }
            
            if ($fileA.Hash -eq $fileB.Hash) {
                $status = if ($relDirA -eq $relDirB) { "EXACT MATCH" } else { "FILE MOVED" }
            } else {
                $status = "FILE DIFFERENT"
            }
            
            [PSCustomObject]@{
                FileName = $fileName
                RootA = $FolderA
                RelativePathA = $relDirA
                Status = $status
                RootB = $FolderB
                RelativePathB = $relDirB
            }
        }
    }
}

$results | Format-Table -AutoSize
$results | Export-Csv -Path "$CompareOut" -NoTypeInformation
Write-Host "`nResults exported to FolderComparison.csv"

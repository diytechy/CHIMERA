<#
.SYNOPSIS
Compares files between two Terra project roots (Hydraxia2 and ORIGEN2) for selected top-level folders and writes a CSV report.

.DESCRIPTION
Searches the specified folder categories under the source project and compares each file to files under the matching category in the target project.
The report marks each file as one of:
  - EXACT MATCH: same relative path and identical content
  - FILE MOVED: same filename exists in target (different subfolder) and content matches
  - FILE DIFFERENT: same filename exists in target but content differs
  - FILE MISSING: no file with same filename exists in target

The output CSV columns are:
  Category,FileName,State,SourceRelativePath,TargetRelativePath

.PARAMETER SourceRoot
Root folder for the source project to compare (default: C:\Projects\Hydraxia2)

.PARAMETER TargetRoot
Root folder for the target project (default: C:\Projects\ORIGEN2)

.PARAMETER Categories
List of top-level folders to compare (default: biome-distribution,biomes,features,palettes,structures)

.PARAMETER OutputCsv
Path to the output CSV file (default: compare_projects_report.csv in current folder)

.EXAMPLE
PS> .scripts\compare_projects.ps1 -SourceRoot C:\Projects\Hydraxia2 -TargetRoot C:\Projects\ORIGEN2 -OutputCsv .\hydraxia_vs_origen2.csv
#>
[CmdletBinding()]
param(
    [Parameter()]
    [string]$SourceRoot = 'C:\Projects\Hydraxia2',

    [Parameter()]
    [string]$TargetRoot = 'C:\Projects\ORIGEN2',

    [Parameter()]
    [string[]]$Categories = @('biome-distribution','biomes','features','palettes','structures'),

    [Parameter()]
    [string]$OutputCsv = '.\compare_projects_report.csv'
)

function Ensure-DirPathHasTrailingSlash([string]$p){
    if($p -and -not $p.EndsWith([System.IO.Path]::DirectorySeparatorChar)){
        return $p + [System.IO.Path]::DirectorySeparatorChar
    }
    return $p
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# If OutputCsv not explicitly set, default to the Review folder adjacent to the script's parent (e.g., ../Review/hydraxia_vs_origen2.csv)
if (-not $PSBoundParameters.ContainsKey('OutputCsv')) {
    $defaultOutput = Join-Path (Join-Path $ScriptDir '..\Review') 'hydraxia_vs_origen2.csv'
    $OutputCsv = (Resolve-Path -Path $defaultOutput -ErrorAction SilentlyContinue)?.Path ?? [System.IO.Path]::GetFullPath($defaultOutput)
}
# Ensure output directory exists
$OutputDir = Split-Path -Parent $OutputCsv
if ($OutputDir -and -not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Resolve source/target roots to absolute paths (handles relative paths when script run from ./scripts)
$SourceRoot = Ensure-DirPathHasTrailingSlash((Resolve-Path -Path $SourceRoot -ErrorAction SilentlyContinue)?.Path ?? (Resolve-Path -Path (Join-Path $ScriptDir $SourceRoot) -ErrorAction SilentlyContinue)?.Path ?? $SourceRoot)
$TargetRoot = Ensure-DirPathHasTrailingSlash((Resolve-Path -Path $TargetRoot -ErrorAction SilentlyContinue)?.Path ?? (Resolve-Path -Path (Join-Path $ScriptDir $TargetRoot) -ErrorAction SilentlyContinue)?.Path ?? $TargetRoot)

if (-not (Test-Path $SourceRoot)){
    Write-Error "Source root not found: $SourceRoot"
    return
}

if (-not (Test-Path $TargetRoot)){
    Write-Warning "Target root not found: $TargetRoot - files will be reported as FILE MISSING"
}

# Helper to compute hash
function Get-FileHashHex([string]$path){
    try{
        return (Get-FileHash -Algorithm SHA256 -Path $path).Hash
    }catch{
        return $null
    }
}

$results = @()

foreach($cat in $Categories){
    $srcCatRoot = Join-Path $SourceRoot $cat
    $tgtCatRoot = Join-Path $TargetRoot $cat

    if (-not (Test-Path $srcCatRoot)){
        Write-Verbose "Source category folder missing: $srcCatRoot - skipping"
        continue
    }

    Write-Host "Comparing category: $cat" -ForegroundColor Cyan

    $srcFiles = Get-ChildItem -Path $srcCatRoot -Recurse -File -ErrorAction SilentlyContinue
    if (-not $srcFiles){
        Write-Host "  No files found in source category: $cat"
        continue
    }

    # Pre-index target files by name for faster lookups
    $tgtFilesByName = @{}
    if (Test-Path $tgtCatRoot){
        $allTgt = Get-ChildItem -Path $tgtCatRoot -Recurse -File -ErrorAction SilentlyContinue
        foreach($tf in $allTgt){
            if (-not $tgtFilesByName.ContainsKey($tf.Name)){
                $tgtFilesByName[$tf.Name] = @()
            }
            $tgtFilesByName[$tf.Name] += $tf
        }
    }

    foreach($f in $srcFiles){
        $fileName = $f.Name
        # relative file path from category root (includes filename)
        $srcRelFile = $f.FullName.Substring($srcCatRoot.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
        # relative directory path (exclude filename). If file is at category root, this becomes empty string.
        $srcRelDir = (Split-Path -Parent $srcRelFile)
        if (-not $srcRelDir) { $srcRelDir = '' }

        # Exact path check in target (use file path)
        $expectedTarget = Join-Path $tgtCatRoot $srcRelFile
        $state = 'FILE MISSING'
        $targetPaths = @()
        $srcHash = Get-FileHashHex $f.FullName
        $targetHashes = @()

        if (Test-Path $expectedTarget){
            # exact path exists - compare hash
            $tgtHash = Get-FileHashHex $expectedTarget
            $targetRelFile = (Get-Item $expectedTarget).FullName.Substring($tgtCatRoot.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
            $targetRelDir = (Split-Path -Parent $targetRelFile)
            if (-not $targetRelDir) { $targetRelDir = '' }
            if ($targetRelDir -notin $targetPaths) { $targetPaths += $targetRelDir }
            if($srcHash -and $tgtHash -and $srcHash -eq $tgtHash){
                $state = 'EXACT MATCH'
                $targetHashes += $tgtHash
            }else{
                $state = 'FILE DIFFERENT'
                if ($tgtHash) { $targetHashes += $tgtHash }
            }
        } else {
            # look for any files with same name under target category using pre-index
            if ($tgtFilesByName.ContainsKey($fileName)){
                $candidates = $tgtFilesByName[$fileName]
                $foundSameContent = $false
                foreach($m in $candidates){
                    $mRelFile = $m.FullName.Substring($tgtCatRoot.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
                    $mRelDir = (Split-Path -Parent $mRelFile)
                    if (-not $mRelDir) { $mRelDir = '' }
                    $mHash = Get-FileHashHex $m.FullName
                    if ($mHash){ $targetHashes += $mHash }
                    # include directory path (exclude filename)
                    if ($mRelDir -notin $targetPaths) { $targetPaths += $mRelDir }
                    if ($srcHash -and $mHash -and $srcHash -eq $mHash){
                        $foundSameContent = $true
                    }
                }
                if ($foundSameContent){
                    $state = 'FILE MOVED'
                    # Keep only the matching paths with same hash to avoid confusion (directories)
                    $matchingPaths = @()
                    foreach($m in $candidates){
                        $mRelFile = $m.FullName.Substring($tgtCatRoot.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
                        $mRelDir = (Split-Path -Parent $mRelFile)
                        if (-not $mRelDir) { $mRelDir = '' }
                        $mHash = Get-FileHashHex $m.FullName
                        if ($srcHash -and $mHash -and $srcHash -eq $mHash){
                            if ($mRelDir -notin $matchingPaths){ $matchingPaths += $mRelDir }
                        }
                    }
                    if ($matchingPaths.Count -gt 0){ $targetPaths = $matchingPaths }
                }else{
                    $state = 'FILE DIFFERENT'
                }
            }
        }

        $result = [PSCustomObject]@{
            Category = $cat
            FileName = $fileName
            State = $state
            SourceRelativePath = $srcRelDir
            TargetRelativePath = if($targetPaths.Count -gt 0){ ($targetPaths -join ';') } else { '' }
            SourceHash = if($srcHash){ $srcHash } else { '' }
            TargetHashes = if($targetHashes.Count -gt 0){ ($targetHashes -join ';') } else { '' }
        }
        $results += $result
    }
}

# Output CSV
$results | Sort-Object Category,SourceRelativePath | Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8
Write-Host "Report written to $OutputCsv" -ForegroundColor Green

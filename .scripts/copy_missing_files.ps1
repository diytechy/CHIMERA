<#
.SYNOPSIS
Copy files marked FILE MISSING in a comparison CSV from a source project to a target project, preserving relative paths.

.DESCRIPTION
Reads a CSV report produced by .\compare_projects.ps1 (default: ../Review/hydraxia_vs_origen2.csv) and copies every file whose State is "FILE MISSING" from the SourceRoot to the TargetRoot, preserving the same relative (category + directory) path.

The script supports a DryRun mode that prints planned actions without copying, an optional -Overwrite switch to replace existing target files, and writes a log CSV to the Review folder (copied_missing_files.csv) recording results.

.PARAMETER SourceRoot
Source project root (default: C:\Projects\Hydraxia2)

.PARAMETER TargetRoot
Target project root (default: C:\Projects\ORIGEN2)

.PARAMETER InputCsv
Path to the comparison CSV (default: ../Review/hydraxia_vs_origen2.csv relative to this script)

.PARAMETER DryRun
If specified, do not actually copy files; only report what would be done.

.PARAMETER Overwrite
If specified, overwrite any existing target file (use cautiously).

.EXAMPLE
# Dry run:
cd .\scripts
.\copy_missing_files.ps1 -DryRun

# Real copy with overwrite:
.\copy_missing_files.ps1 -SourceRoot C:\Projects\Hydraxia2 -TargetRoot C:\Projects\ORIGEN2 -Overwrite
#>
[CmdletBinding()]
param(
    [Parameter()]
    [string]$SourceRoot = 'C:\Projects\Hydraxia2',

    [Parameter()]
    [string]$TargetRoot = 'C:\Projects\ORIGEN2',

    [Parameter()]
    [string]$InputCsv,

    [Parameter()]
    [switch]$DryRun,

    [Parameter()]
    [switch]$Overwrite,

    [Parameter()]
    [string[]]$Categories = @('biome-distribution','biomes','features','palettes','structures')
)

function Ensure-DirPathHasTrailingSlash([string]$p){
    if($p -and -not $p.EndsWith([System.IO.Path]::DirectorySeparatorChar)){
        return $p + [System.IO.Path]::DirectorySeparatorChar
    }
    return $p
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $PSBoundParameters.ContainsKey('InputCsv')){
    $defaultInput = Join-Path (Join-Path $ScriptDir '..\Review') 'hydraxia_vs_origen2.csv'
    $InputCsv = (Resolve-Path -Path $defaultInput -ErrorAction SilentlyContinue)?.Path ?? [System.IO.Path]::GetFullPath($defaultInput)
}

# Resolve roots (allow running script from ./scripts)
$SourceRoot = Ensure-DirPathHasTrailingSlash((Resolve-Path -Path $SourceRoot -ErrorAction SilentlyContinue)?.Path ?? (Resolve-Path -Path (Join-Path $ScriptDir $SourceRoot) -ErrorAction SilentlyContinue)?.Path ?? $SourceRoot)
$TargetRoot = Ensure-DirPathHasTrailingSlash((Resolve-Path -Path $TargetRoot -ErrorAction SilentlyContinue)?.Path ?? (Resolve-Path -Path (Join-Path $ScriptDir $TargetRoot) -ErrorAction SilentlyContinue)?.Path ?? $TargetRoot)

if (-not (Test-Path $SourceRoot)){
    Write-Error "Source root not found: $SourceRoot"
    return
}
if (-not (Test-Path $TargetRoot)){
    Write-Host "Target root not found: $TargetRoot - creating it." -ForegroundColor Yellow
    if (-not $DryRun){ New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null }
}

if (-not (Test-Path $InputCsv)){
    Write-Error "Input CSV not found: $InputCsv"
    return
}

# Prepare log file in Review folder
$ReviewDir = Join-Path (Join-Path $ScriptDir '..\Review') ''
$ReviewDir = (Resolve-Path -Path $ReviewDir -ErrorAction SilentlyContinue)?.Path ?? [System.IO.Path]::GetFullPath($ReviewDir)
if (-not (Test-Path $ReviewDir)){
    if (-not $DryRun){ New-Item -ItemType Directory -Path $ReviewDir -Force | Out-Null }
}
$LogCsv = Join-Path $ReviewDir 'copied_missing_files.csv'
$logResults = @()

# Read CSV
Write-Host "Reading CSV: $InputCsv" -ForegroundColor Cyan
$rows = Import-Csv -Path $InputCsv

# Filter missing entries and optional categories
$missingRows = $rows | Where-Object { $_.State -eq 'FILE MISSING' -and ($Categories -contains $_.Category) }
$total = $missingRows.Count
Write-Host "Found $total FILE MISSING entries to examine." -ForegroundColor Green

$copied = 0
$skipped = 0
$errors = 0

foreach($r in $missingRows){
    $category = $r.Category
    $fileName = $r.FileName
    $srcRelDir = $r.SourceRelativePath.Trim()
    if (-not $srcRelDir){ $srcRelDir = '' }

    $sourceFull = if ($srcRelDir -ne '') { Join-Path -Path (Join-Path $SourceRoot $category) -ChildPath (Join-Path $srcRelDir $fileName) } else { Join-Path -Path (Join-Path $SourceRoot $category) -ChildPath $fileName }
    $targetDir = if ($srcRelDir -ne '') { Join-Path -Path (Join-Path $TargetRoot $category) -ChildPath $srcRelDir } else { Join-Path -Path (Join-Path $TargetRoot $category) -ChildPath '' }
    $targetFull = Join-Path -Path $targetDir -ChildPath $fileName

    if (-not (Test-Path $sourceFull)){
        Write-Warning "Source missing: $sourceFull (skipping)"
        $logResults += [PSCustomObject]@{
            Category = $category
            FileName = $fileName
            SourcePath = $sourceFull
            TargetPath = $targetFull
            Result = 'SOURCE NOT FOUND'
            Message = 'Source file does not exist'
        }
        $skipped++
        continue
    }

    if ( (Test-Path $targetFull) -and (-not $Overwrite) ){
        Write-Host "Target already exists (skipping): $targetFull" -ForegroundColor Yellow
        $logResults += [PSCustomObject]@{
            Category = $category
            FileName = $fileName
            SourcePath = $sourceFull
            TargetPath = $targetFull
            Result = 'TARGET EXISTS'
            Message = 'Target already exists; use -Overwrite to replace'
        }
        $skipped++
        continue
    }

    Write-Host "Copying: $sourceFull -> $targetFull"
    if ($DryRun){
        $logResults += [PSCustomObject]@{
            Category = $category
            FileName = $fileName
            SourcePath = $sourceFull
            TargetPath = $targetFull
            Result = 'DRYRUN'
            Message = 'Would copy (dry run)'
        }
        $copied++
        continue
    }

    try{
        # Ensure target directory exists
        if (-not (Test-Path $targetDir)){
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
        if ($Overwrite){
            Copy-Item -Path $sourceFull -Destination $targetFull -Force -ErrorAction Stop
        } else {
            Copy-Item -Path $sourceFull -Destination $targetFull -ErrorAction Stop
        }
        $logResults += [PSCustomObject]@{
            Category = $category
            FileName = $fileName
            SourcePath = $sourceFull
            TargetPath = $targetFull
            Result = 'COPIED'
            Message = ''
        }
        $copied++
    } catch {
        Write-Error "Failed to copy $sourceFull -> $targetFull : $_"
        $logResults += [PSCustomObject]@{
            Category = $category
            FileName = $fileName
            SourcePath = $sourceFull
            TargetPath = $targetFull
            Result = 'ERROR'
            Message = $_.Exception.Message
        }
        $errors++
    }
}

# Write log
$logResults | Sort-Object Category,FileName | Export-Csv -Path $LogCsv -NoTypeInformation -Encoding UTF8

Write-Host "Done. Copied: $copied, Skipped: $skipped, Errors: $errors. Log: $LogCsv" -ForegroundColor Green

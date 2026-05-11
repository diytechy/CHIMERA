# revert_simplex_samplers.ps1
# Finds every place in git history where a sampler type was changed from
# OPEN_SIMPLEX_2S to OPEN_SIMPLEX_2, then reverts ONLY those specific lines
# in the working tree. Uses surrounding context to disambiguate lines that
# were always OPEN_SIMPLEX_2 from ones that were changed.
#
# Usage (run from repo root on the branch you want to fix, e.g. main):
#   .\.scripts\revert_simplex_samplers.ps1            # dry-run
#   .\.scripts\revert_simplex_samplers.ps1 -Apply     # write changes

param(
    [switch]$Apply
)

Set-Location $PSScriptRoot\..
$repoRoot = (Get-Location).Path

# ---------------------------------------------------------------------------
# PART 1 – Parse git history for OPEN_SIMPLEX_2S -> OPEN_SIMPLEX_2 changes
# ---------------------------------------------------------------------------
Write-Host "Scanning git history (this may take a moment)..."
$allLines = @(git log --all -p -- "*.yml" 2>&1)

$findings = [System.Collections.ArrayList]::new()
$currentFile = $null
$contextBuf  = [System.Collections.Generic.List[string]]::new()
$pendingRem  = [System.Collections.Generic.List[string]]::new()

for ($i = 0; $i -lt $allLines.Length; $i++) {
    $line = $allLines[$i]

    # New file section
    if ($line -match '^diff --git .+ b/(.+\.yml)$') {
        $currentFile = $matches[1] -replace '/', '\'
        $contextBuf.Clear(); $pendingRem.Clear()
        continue
    }

    # Hunk header – reset context
    if ($line -match '^@@') {
        $contextBuf.Clear(); $pendingRem.Clear()
        continue
    }

    # Context line (unchanged) – keep last 4 lines as context window
    if ($line -match '^ (.*)') {
        $contextBuf.Add($matches[1])
        if ($contextBuf.Count -gt 4) { $contextBuf.RemoveAt(0) }
        $pendingRem.Clear()   # gap between - and + blocks resets pairing
        continue
    }

    # Removed line: sampler was OPEN_SIMPLEX_2S
    if ($line -match '^\-(\s+(?:type|sampler):\s+OPEN_SIMPLEX_2S)\s*$') {
        $pendingRem.Add($matches[1]) | Out-Null
        continue
    }

    # Added line: sampler is now OPEN_SIMPLEX_2 (not S) – pair with pending removal
    if ($line -match '^\+(\s+(?:type|sampler):\s+OPEN_SIMPLEX_2)\s*$' -and $pendingRem.Count -gt 0) {
        $findings.Add([PSCustomObject]@{
            File        = $currentFile
            Context     = @($contextBuf)   # up to 4 preceding unchanged lines
            OrigLine    = $pendingRem[0].TrimEnd()
            ChangedLine = $matches[1].TrimEnd()
        }) | Out-Null
        $pendingRem.RemoveAt(0)
        continue
    }

    # Any other + line breaks the removal pairing
    if ($line.StartsWith('+')) { $pendingRem.Clear() }
}

# De-duplicate: same (file + changedLine + context[-1]) may appear in
# multiple commits if the file was touched again later. Keep unique pairs.
$seen     = [System.Collections.Generic.HashSet[string]]::new()
$deduped  = [System.Collections.ArrayList]::new()
foreach ($f in $findings) {
    $key = "$($f.File)|$($f.ChangedLine)|$($f.Context[-1])"
    if ($seen.Add($key)) { $deduped.Add($f) | Out-Null }
}
$findings = $deduped

# ---------------------------------------------------------------------------
# PART 2 – Report
# ---------------------------------------------------------------------------
Write-Host "`n=== OPEN_SIMPLEX_2S -> OPEN_SIMPLEX_2 changes found in history ===`n"
$byFile = $findings | Group-Object File | Sort-Object Name
foreach ($grp in $byFile) {
    Write-Host "[$($grp.Count) change(s)]  $($grp.Name)"
    foreach ($c in $grp.Group) {
        $ctx = if ($c.Context.Count -gt 0) { $c.Context[-1].Trim() } else { "(no context)" }
        Write-Host "    context before : $ctx"
        Write-Host "    revert         : '$($c.ChangedLine.Trim())' -> '$($c.OrigLine.Trim())'"
        Write-Host ""
    }
}
Write-Host "Total: $($findings.Count) change(s) across $($byFile.Count) file(s)"

if (-not $Apply) {
    Write-Host "`n[DRY RUN] No files written. Re-run with -Apply to make changes."
    exit
}

# ---------------------------------------------------------------------------
# PART 3 – Apply reversions (only runs with -Apply)
# ---------------------------------------------------------------------------
Write-Host "`nApplying reversions..."
$fixed = 0; $warnings = 0

foreach ($grp in $byFile) {
    $fullPath = Join-Path $repoRoot $grp.Name
    if (-not (Test-Path $fullPath)) {
        Write-Warning "File not found in working tree: $($grp.Name)"
        $warnings++
        continue
    }

    $fileLines = [System.IO.File]::ReadAllLines($fullPath)
    $fileChanged = $false

    foreach ($c in $grp.Group) {
        $target   = $c.ChangedLine   # what we're looking for in the file now
        $revert   = $c.OrigLine      # what we want to put back
        $ctx      = $c.Context       # preceding unchanged lines for disambiguation

        $matched = $false
        for ($li = 0; $li -lt $fileLines.Length; $li++) {
            if ($fileLines[$li].TrimEnd() -ne $target) { continue }

            # Verify preceding context lines
            $ok = $true
            for ($ci = 0; $ci -lt $ctx.Count; $ci++) {
                $checkIdx = $li - ($ctx.Count - $ci)
                if ($checkIdx -lt 0) { continue }
                if ($fileLines[$checkIdx].TrimEnd() -ne $ctx[$ci]) { $ok = $false; break }
            }
            if (-not $ok) { continue }

            $fileLines[$li] = $revert
            $fileChanged = $true
            $matched = $true
            break
        }

        if (-not $matched) {
            Write-Warning "Could not match line in: $($grp.Name)"
            Write-Warning "  Looking for : $target"
            Write-Warning "  Context     : $($ctx -join ' | ')"
            $warnings++
        }
    }

    if ($fileChanged) {
        [System.IO.File]::WriteAllLines($fullPath, $fileLines)
        Write-Host "  Fixed: $($grp.Name)"
        $fixed++
    }
}

Write-Host "`nDone. $fixed file(s) updated, $warnings warning(s)."

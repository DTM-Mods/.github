# Pushes this repository's commits to main the checked way: main only takes a commit that passed the
# Check workflow (ruleset "Checked before main"), because every DTM mod builds with the scripts here.
#
#     .\ci\push_checked.ps1
#
# It pushes HEAD to the branch "next", waits for Check to finish on that commit, and when it is green
# moves main up to the same commit. When it is red, main is left alone: fix, commit, run it again.
$ErrorActionPreference = 'Stop'
# work in this repository, and put the shell back where it was afterwards
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $sha = (git rev-parse HEAD).Trim()
    git fetch origin main --quiet
    git merge-base --is-ancestor origin/main HEAD
    if ($LASTEXITCODE -ne 0) { Write-Host "origin/main has commits you don't have: git pull --rebase first."; return }
    if ((git rev-parse origin/main).Trim() -eq $sha) { Write-Host "main is at $($sha.Substring(0,7)) already."; return }
    git push origin "HEAD:refs/heads/next" --force
    if ($LASTEXITCODE -ne 0) { return }
    Write-Host "Waiting for Check on $($sha.Substring(0,7))..."
    $run = $null
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 5
        $run = gh run list -R DTM-Mods/.github --workflow check.yml --commit $sha --limit 1 --json databaseId,status,conclusion | ConvertFrom-Json | Select-Object -First 1
        if ($run) { break }
    }
    if (-not $run) { Write-Host "Check didn't start within a few minutes: look at the Actions tab."; return }
    gh run watch $run.databaseId -R DTM-Mods/.github --exit-status --interval 10
    if ($LASTEXITCODE -ne 0) { Write-Host "Check failed: main is unchanged. See: gh run view $($run.databaseId) -R DTM-Mods/.github --log-failed"; return }
    git push origin "HEAD:main"
    if ($LASTEXITCODE -ne 0) { return }
    git push origin --delete next --quiet
    Write-Host "main is at $($sha.Substring(0,7)), checked."
} finally {
    Pop-Location
}

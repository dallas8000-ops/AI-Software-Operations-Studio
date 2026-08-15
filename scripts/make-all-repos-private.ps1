param(
    [string]$Organization = "dallas8000-ops",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-GitHubToken {
    if ($env:GH_TOKEN) { return $env:GH_TOKEN }
    if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
    throw "Set GH_TOKEN or GITHUB_TOKEN before running this script."
}

function Invoke-GitHubApi {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [object]$Body
    )

    $headers = @{
        Authorization = "Bearer $(Get-GitHubToken)"
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
    }

    $invokeParams = @{
        Method = $Method
        Uri = $Uri
        Headers = $headers
        ContentType = "application/json"
    }

    if ($null -ne $Body) {
        $invokeParams.Body = ($Body | ConvertTo-Json -Depth 10)
    }

    Invoke-RestMethod @invokeParams
}

Write-Host "Listing public repositories for $Organization..." -ForegroundColor Cyan
$repos = @()
$page = 1

while ($true) {
    $pageItems = Invoke-GitHubApi -Method "GET" -Uri "https://api.github.com/orgs/$Organization/repos?type=public&per_page=100&page=$page"
    if (-not $pageItems -or $pageItems.Count -eq 0) { break }
    $repos += $pageItems
    if ($pageItems.Count -lt 100) { break }
    $page++
}

if (-not $repos -or $repos.Count -eq 0) {
    Write-Host "No public repositories found." -ForegroundColor Green
    exit 0
}

foreach ($repo in $repos) {
    Write-Host "Making private: $($repo.full_name)" -ForegroundColor Yellow
    if (-not $DryRun) {
        Invoke-GitHubApi -Method "PATCH" -Uri "https://api.github.com/repos/$($repo.full_name)" -Body @{ private = $true } | Out-Null
    }
}

Write-Host "Verifying remaining public repositories..." -ForegroundColor Cyan
$remaining = @()
$page = 1

while ($true) {
    $pageItems = Invoke-GitHubApi -Method "GET" -Uri "https://api.github.com/orgs/$Organization/repos?type=public&per_page=100&page=$page"
    if (-not $pageItems -or $pageItems.Count -eq 0) { break }
    $remaining += $pageItems
    if ($pageItems.Count -lt 100) { break }
    $page++
}

if ($remaining.Count -eq 0) {
    Write-Host "All repositories are private." -ForegroundColor Green
} else {
    Write-Host "Public repositories remaining:" -ForegroundColor Red
    $remaining | Select-Object -ExpandProperty full_name
}
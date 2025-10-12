param (
    [string]$version
)
if (-not $version) {
    Write-Host "Usage: .\cleanup-dev-releases-for.ps1 -version <version>"
    exit 1
}
$releases = gh release list --limit 1000 --json tagName --jq ".[] | select(.tagName | startswith(""""${version}-dev""""""))"
foreach ($release in $releases) {
    Write-Host "Deleting release & tag: $($release)"
    gh release delete $release.tagName --cleanup-tag --yes
}
param(
    [string]$Credentials = "credentials.json"
)

$ErrorActionPreference = "Stop"
$SourceFolder = "https://drive.google.com/drive/folders/1d80JZ33vLArjdSsXpnu0Xi9KN1dzeCl6"
$OutputFolder = "https://drive.google.com/drive/folders/18Ibs2v-cH3W7hw95bZRlXsVuEsIa2-e5"

Write-Host "RooomPhotoSkills: インスタベース + スペースマーケット用の写真を選定・補正します。"
Write-Host "元写真は削除・移動・上書きしません。"

python -m pip install -e .
rooomphotos spaces `
    $SourceFolder `
    --output-folder $OutputFolder `
    --credentials $Credentials `
    --min-selected 15 `
    --max-selected 24

Write-Host "完了: $OutputFolder"

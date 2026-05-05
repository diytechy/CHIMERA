$data = Import-Csv -Path ".artifacts\BiomeTable.csv"

$filtered = $data | Where-Object {
    $_.Source -eq "surface" -and
    $_.Type -eq "Land" -and
    $_.BiomeID -notlike "*river*"
}

$biomeIds = $filtered | Select-Object -ExpandProperty BiomeID | Sort-Object

$biomeIds -join "`n"
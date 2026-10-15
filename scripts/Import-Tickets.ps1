<#
.SYNOPSIS
Converts exported ticket emails or a CSV export into a JSON Lines file for the triage agent.

.DESCRIPTION
With -FolderPath, reads every .eml and .txt file in the folder (and subfolders), pulls out
the Subject, From and Date header fields and the plain-text body, and writes one JSON object
per line. Multipart MIME emails are not decoded, so export tickets as plain text.

With -CsvPath, reads a CSV export that has Subject and Body columns, and an optional Id column.

.EXAMPLE
./scripts/Import-Tickets.ps1 -FolderPath ./export -OutputPath ./data/imported.jsonl

.EXAMPLE
./scripts/Import-Tickets.ps1 -CsvPath ./tickets.csv -OutputPath ./data/imported.jsonl
#>
[CmdletBinding(DefaultParameterSetName = 'Folder')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Folder')]
    [string]$FolderPath,

    [Parameter(Mandatory, ParameterSetName = 'Csv')]
    [string]$CsvPath,

    [Parameter(Mandatory)]
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-HeaderField {
    param([string[]]$Lines, [string]$Name)
    $line = $Lines | Where-Object { $_ -match "^$Name\s*:" } | Select-Object -First 1
    if ($line) { return ($line -replace "^$Name\s*:\s*", '').Trim() }
    return ''
}

$tickets = [System.Collections.Generic.List[object]]::new()

if ($PSCmdlet.ParameterSetName -eq 'Csv') {
    $index = 0
    foreach ($row in Import-Csv -Path $CsvPath) {
        $index++
        $id = if ($row.PSObject.Properties['Id'] -and $row.Id) { $row.Id } else { 'CSV-{0:D4}' -f $index }
        $tickets.Add([ordered]@{ id = $id; subject = $row.Subject; body = $row.Body })
    }
}
else {
    $files = Get-ChildItem -Path $FolderPath -File -Recurse -Include *.eml, *.txt
    foreach ($file in $files) {
        $raw = Get-Content -Path $file.FullName -Raw
        # Header fields end at the first blank line.
        $parts = $raw -split '\r?\n\r?\n', 2
        $headers = $parts[0] -split '\r?\n'
        $body = if ($parts.Count -gt 1) { $parts[1].Trim() } else { '' }
        $tickets.Add([ordered]@{
                id      = $file.BaseName
                subject = Get-HeaderField -Lines $headers -Name 'Subject'
                from    = Get-HeaderField -Lines $headers -Name 'From'
                date    = Get-HeaderField -Lines $headers -Name 'Date'
                body    = $body
            })
    }
}

$skipped = 0
$lines = @(foreach ($ticket in $tickets) {
        if (-not $ticket.subject -and -not $ticket.body) { $skipped++; continue }
        $ticket | ConvertTo-Json -Compress -Depth 3
    })

$lines | Set-Content -Path $OutputPath -Encoding utf8
Write-Host ('Wrote {0} tickets to {1} ({2} skipped because they were empty)' -f $lines.Count, $OutputPath, $skipped)

# Get-MyChartAppointments.ps1
# Fetches appointments from Benefis MyChart using Edge remote debugging
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -ErrorAction SilentlyContinue

$OutputPath = "$env:USERPROFILE\Desktop\MyChart_Appointments"
$BaseUrl    = "https://mychart.benefis.org/MyChart"
$DebugPort  = 9222
$EdgeExe    = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host "Becky's Care - MyChart Scraper" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

if (-not (Test-Path $OutputPath)) { New-Item -ItemType Directory -Path $OutputPath | Out-Null }

# ── FUNCTIONS ────────────────────────────────────────────────────────────────
function Get-PageHtml($WsUrl) {
    # Use CDP via .NET HttpClient + manual WebSocket
    $HttpClient = [System.Net.Http.HttpClient]::new()
    $Cts = [System.Threading.CancellationTokenSource]::new(15000)
    
    # Build WebSocket request manually using TCP
    $Uri = [Uri]$WsUrl
    $Host2 = $Uri.Host
    $Port = if ($Uri.Port -gt 0) { $Uri.Port } else { 80 }
    $Path = $Uri.PathAndQuery
    
    $Tcp = [System.Net.Sockets.TcpClient]::new($Host2, $Port)
    $Stream = $Tcp.GetStream()
    $Writer = [System.IO.StreamWriter]::new($Stream)
    $Reader = [System.IO.BinaryReader]::new($Stream)
    
    # WebSocket handshake
    $Key = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("BeckyCare12345678901234"))
    $Handshake = "GET $Path HTTP/1.1`r`nHost: ${Host2}:${Port}`r`nUpgrade: websocket`r`nConnection: Upgrade`r`nSec-WebSocket-Key: $Key`r`nSec-WebSocket-Version: 13`r`n`r`n"
    $Writer.Write($Handshake)
    $Writer.Flush()
    
    # Read handshake response
    Start-Sleep -Milliseconds 500
    $HeaderBuf = New-Object byte[] 4096
    $HeaderLen = $Stream.Read($HeaderBuf, 0, 4096)
    
    # Send CDP evaluate command as WebSocket frame
    $Cmd = '{"id":1,"method":"Runtime.evaluate","params":{"expression":"document.documentElement.outerHTML","returnByValue":true}}'
    $CmdBytes = [System.Text.Encoding]::UTF8.GetBytes($Cmd)
    $Len = $CmdBytes.Length
    
    # Build WebSocket frame (text, no mask for client... actually clients must mask)
    $MaskKey = [byte[]](1,2,3,4)
    $Frame = New-Object System.Collections.Generic.List[byte]
    $Frame.Add(0x81) # FIN + text opcode
    if ($Len -le 125) {
        $Frame.Add([byte]($Len -bor 0x80))
    } elseif ($Len -le 65535) {
        $Frame.Add(0xFE)
        $Frame.Add([byte](($Len -shr 8) -band 0xFF))
        $Frame.Add([byte]($Len -band 0xFF))
    }
    $Frame.AddRange($MaskKey)
    for ($i=0; $i -lt $CmdBytes.Length; $i++) {
        $Frame.Add($CmdBytes[$i] -bxor $MaskKey[$i % 4])
    }
    $Stream.Write($Frame.ToArray(), 0, $Frame.Count)
    $Stream.Flush()
    
    # Read response frames
    Start-Sleep -Milliseconds 2000
    $AllData = New-Object System.Collections.Generic.List[byte]
    $ReadBuf = New-Object byte[] 65536
    $Deadline = (Get-Date).AddSeconds(10)
    
    while ((Get-Date) -lt $Deadline) {
        if ($Stream.DataAvailable) {
            $N = $Stream.Read($ReadBuf, 0, $ReadBuf.Length)
            for ($i=0; $i -lt $N; $i++) { $AllData.Add($ReadBuf[$i]) }
            if ($AllData.Count -gt 100) { break }
        }
        Start-Sleep -Milliseconds 200
    }
    
    $Tcp.Close()
    
    if ($AllData.Count -lt 10) { return $null }
    
    # Parse WebSocket frame
    $Payload = New-Object System.Collections.Generic.List[byte]
    $Idx = 0
    $Fin = ($AllData[$Idx] -band 0x80) -ne 0
    $Opcode = $AllData[$Idx] -band 0x0F
    $Idx++
    $Masked = ($AllData[$Idx] -band 0x80) -ne 0
    $PayLen = $AllData[$Idx] -band 0x7F
    $Idx++
    if ($PayLen -eq 126) { $PayLen = ([int]$AllData[$Idx] -shl 8) -bor $AllData[$Idx+1]; $Idx += 2 }
    elseif ($PayLen -eq 127) { $Idx += 8; $PayLen = 0 }
    if ($Masked) { $Idx += 4 }
    
    $JsonBytes = $AllData.GetRange($Idx, [Math]::Min($PayLen, $AllData.Count - $Idx)).ToArray()
    $JsonStr = [System.Text.Encoding]::UTF8.GetString($JsonBytes)
    
    try {
        $Parsed = $JsonStr | ConvertFrom-Json
        return $Parsed.result.result.value
    } catch {
        return $JsonStr
    }
}

function Parse-Appointments($Html) {
    $Appts = @()
    
    # Epic MyChart appointment patterns
    $Patterns = @(
        '(?i)(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}[^\n]*\d{1,2}:\d{2}\s*(am|pm)',
        '(?i)\d{1,2}/\d{1,2}/\d{4}[^\n]*\d{1,2}:\d{2}\s*(am|pm)',
        '(?i)(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s+(january|february|march|april|may|june|july|august|september|october|november|december)[a-z]*\.?\s+\d{1,2}'
    )
    
    foreach ($Pat in $Patterns) {
        $Matches2 = [regex]::Matches($Html, $Pat)
        foreach ($M in $Matches2) {
            $Appts += $M.Value.Trim()
        }
    }
    
    return $Appts | Select-Object -Unique
}

function Parse-Providers($Html) {
    $Providers = @()
    # Look for provider names (Dr., MD, APRN, etc.)
    $Pat = '(?i)(Dr\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+|[A-Z][a-z]+\s+[A-Z][a-z]+,?\s+(MD|DO|APRN|NP|PA|RN|PT|OT|SLP))'
    $Matches2 = [regex]::Matches($Html, $Pat)
    foreach ($M in $Matches2) { $Providers += $M.Value.Trim() }
    return $Providers | Select-Object -Unique
}

# ── MAIN ─────────────────────────────────────────────────────────────────────

# Kill existing debug Edge
Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "Opening MyChart in Edge with debugging..." -ForegroundColor Yellow
$Args2 = "--remote-debugging-port=$DebugPort --user-data-dir=`"$env:TEMP\EdgeMC`" `"$BaseUrl/Visits`""
Start-Process $EdgeExe -ArgumentList $Args2
Write-Host "Please log in to MyChart if prompted, then press Enter..." -ForegroundColor Cyan
Read-Host

# Get tabs
Write-Host "Connecting..." -ForegroundColor Yellow
try {
    $Tabs = Invoke-RestMethod "http://localhost:$DebugPort/json" -ErrorAction Stop
    Write-Host "Found $($Tabs.Count) tab(s)" -ForegroundColor Green
    $Tabs | ForEach-Object { Write-Host "  - $($_.title): $($_.url)" }
} catch {
    Write-Warning "Could not connect to Edge DevTools. Trying manual approach."
    Write-Host ""
    Write-Host "MANUAL STEPS:" -ForegroundColor Yellow
    Write-Host "1. Go to $BaseUrl/Visits in Edge"
    Write-Host "2. Press Ctrl+S, save as 'Webpage, Single File (.mhtml)'"
    Write-Host "3. Save to: $OutputPath\visits.mhtml"
    Write-Host "4. Re-run this script"
    
    $ManualFile = "$OutputPath\visits.mhtml"
    if (Test-Path $ManualFile) {
        Write-Host "Found visits.mhtml - parsing..." -ForegroundColor Green
        $Html = Get-Content $ManualFile -Raw -Encoding UTF8
        $Appts = Parse-Appointments $Html
        $Provs = Parse-Providers $Html
        Write-Host "Appointments: $($Appts.Count)" -ForegroundColor Green
        $Appts | ForEach-Object { Write-Host "  $_" }
        $Provs | ForEach-Object { Write-Host "  Provider: $_" }
        @{ appointments=$Appts; providers=$Provs } | ConvertTo-Json | Out-File "$OutputPath\results.json" -Encoding UTF8
    }
    exit
}

# Try to get Visits page tab
$VisitsTab = $Tabs | Where-Object { $_.url -like "*Visits*" -or $_.url -like "*mychart*" } | Select-Object -First 1
if (-not $VisitsTab) { $VisitsTab = $Tabs[0] }
Write-Host "Using tab: $($VisitsTab.title)" -ForegroundColor Green

# Navigate to Visits if needed
if ($VisitsTab.url -notlike "*Visits*") {
    $NavCmd = @{id=2; method="Page.navigate"; params=@{url="$BaseUrl/Visits"}} | ConvertTo-Json
    # Will try via HTTP evaluate instead
}

Write-Host "Fetching page HTML..." -ForegroundColor Yellow

# Try simple HTTP approach via CDP /json/version then execute
$Html = $null
try {
    # Use Invoke-RestMethod to send CDP command via HTTP (newer Edge supports this)
    $EvalBody = @{expression="document.documentElement.outerHTML"; returnByValue=$true} | ConvertTo-Json
    $TabId = $VisitsTab.id
    
    # Try WebSocket via Get-PageHtml
    $Html = Get-PageHtml $VisitsTab.webSocketDebuggerUrl
} catch {
    Write-Warning "WebSocket failed: $_"
}

if (-not $Html -or $Html.Length -lt 100) {
    Write-Host ""
    Write-Host "Automatic extraction failed. Using manual approach:" -ForegroundColor Yellow
    Write-Host "1. In the Edge window that just opened, log in to MyChart"
    Write-Host "2. Go to Visits page"  
    Write-Host "3. Press Ctrl+A (select all), Ctrl+C (copy)"
    Write-Host "4. Press Enter here to paste and parse"
    Read-Host "Press Enter after copying page text"
    $Html = Get-Clipboard
}

if ($Html -and $Html.Length -gt 100) {
    $Html | Out-File "$OutputPath\visits_raw.html" -Encoding UTF8
    Write-Host "Saved raw content ($($Html.Length) chars)" -ForegroundColor Green
    
    $Appts = Parse-Appointments $Html
    $Provs = Parse-Providers $Html
    
    Write-Host ""
    Write-Host "=== APPOINTMENTS FOUND ===" -ForegroundColor Cyan
    if ($Appts.Count -eq 0) {
        Write-Host "None found automatically. Check visits_raw.html" -ForegroundColor Yellow
    } else {
        $Appts | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
    }
    
    Write-Host ""
    Write-Host "=== PROVIDERS FOUND ===" -ForegroundColor Cyan
    $Provs | Select-Object -Unique | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
    
    @{ appointments=$Appts; providers=($Provs | Select-Object -Unique) } | 
        ConvertTo-Json -Depth 3 | 
        Out-File "$OutputPath\results.json" -Encoding UTF8
    
    Write-Host ""
    Write-Host "Results saved to: $OutputPath\results.json" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: Share results.json with Claude to add to Becky's Care app" -ForegroundColor Cyan
} else {
    Write-Host "No content extracted." -ForegroundColor Red
}

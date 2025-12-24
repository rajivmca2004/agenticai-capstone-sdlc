# PowerShell script to start both A2A agent servers

Write-Host @"
╔═══════════════════════════════════════════════════════════════╗
║           Starting A2A Agent Servers                          ║
╚═══════════════════════════════════════════════════════════════╝
"@

# Start Agent 1 in a new PowerShell window
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$PSScriptRoot\src\agents'; python agent1_server.py"
)

# Wait a moment for Agent 1 to start
Start-Sleep -Seconds 2

# Start Agent 2 in a new PowerShell window
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$PSScriptRoot\src\agents'; python agent2_server.py"
)

Write-Host @"

✅ Agent servers starting in new windows:
   - Agent 1: http://localhost:5001
   - Agent 2: http://localhost:5002

📝 To run the A2A client demo, use:
   cd src
   python a2a_client.py

"@

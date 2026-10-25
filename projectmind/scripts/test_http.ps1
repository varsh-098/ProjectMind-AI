# =============================================================================
# scripts/test_http.ps1
# Phase 3 -- Test llama-server HTTP API directly (no Python)
#
# WHY THIS EXISTS:
#   Before connecting Python or FastAPI, we verify that llama-server itself
#   is working. If something fails here, we know the problem is in the server
#   or the model -- not in our Python code.
#
# USAGE:
#   1. Start llama-server in a separate PowerShell window first.
#   2. Then run: .\scripts\test_http.ps1
# =============================================================================

$SERVER = "http://127.0.0.1:8081"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  ProjectMind -- Phase 3: HTTP API Test" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# TEST 1: Health check
# ---------------------------------------------------------------------------
# /health is a lightweight endpoint built into llama-server.
# It confirms the process is running and ready to accept requests.
# If this fails, the server is not running -- check your llama-server window.
# ---------------------------------------------------------------------------

Write-Host "TEST 1: Health check -- is llama-server alive?" -ForegroundColor Yellow

try {
    $health = Invoke-RestMethod -Uri "$SERVER/health" -TimeoutSec 10
    Write-Host "  PASS: Server is healthy" -ForegroundColor Green
    Write-Host "  Response: $($health | ConvertTo-Json)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: Server is not reachable." -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Action: Make sure llama-server.exe is running in another terminal." -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# ---------------------------------------------------------------------------
# TEST 2: Chat completion
# ---------------------------------------------------------------------------
# This sends a real inference request to Nemotron using the OpenAI-compatible
# /v1/chat/completions endpoint that llama-server exposes.
#
# WHY OpenAI-compatible format?
#   llama-server deliberately mimics the OpenAI Chat API format.
#   This means any code written for OpenAI can work with llama-server
#   with minimal changes -- just change the URL and remove the API key.
#
# The request body has:
#   model      -- llama-server ignores this value (it only serves one model),
#                 but we send it to stay API-compatible.
#   messages   -- a list of conversation turns. "role" is "user", "assistant",
#                 or "system". "content" is the message text.
#   max_tokens -- limits how many tokens the model generates in its response.
# ---------------------------------------------------------------------------

Write-Host "TEST 2: Chat completion -- does Nemotron respond?" -ForegroundColor Yellow
Write-Host "  Sending request to Nemotron... (may take 10-30 seconds)" -ForegroundColor Gray

$body = @{
    model    = "nemotron"
    messages = @(
        @{ role = "user"; content = "What is an API? Answer in exactly two sentences." }
    )
    max_tokens = 120
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod `
        -Uri "$SERVER/v1/chat/completions" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 120

    $answer = $response.choices[0].message.content

    Write-Host "  PASS: Got a response from Nemotron" -ForegroundColor Green
    Write-Host ""
    Write-Host "  --- Nemotron says ---" -ForegroundColor Cyan
    Write-Host "  $answer" -ForegroundColor White
    Write-Host "  ---------------------" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Tokens used:" -ForegroundColor Gray
    Write-Host "    Prompt tokens:     $($response.usage.prompt_tokens)" -ForegroundColor Gray
    Write-Host "    Completion tokens: $($response.usage.completion_tokens)" -ForegroundColor Gray
    Write-Host "    Total tokens:      $($response.usage.total_tokens)" -ForegroundColor Gray

} catch {
    Write-Host "  FAIL: Inference request failed." -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Possible causes:" -ForegroundColor Yellow
    Write-Host "    - Server still loading the model (wait 30s and retry)" -ForegroundColor Yellow
    Write-Host "    - Timeout: increase -TimeoutSec" -ForegroundColor Yellow
    Write-Host "    - Model crashed: check llama-server terminal for FATAL errors" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Phase 3 COMPLETE -- HTTP API is working!" -ForegroundColor Green
Write-Host "  Next step: Phase 4 -- Python client" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# test-tnl-api.ps1

# Define the Fly.io API base URL
$baseUrl = "https://tnl-api-blue-snow-1079.fly.dev"

# Define the seed chunk payload
$body = @{
    chunk_order = 0
    seed_chunk = "Smoky intro"
} | ConvertTo-Json

# POST the seed chunk
$response = Invoke-RestMethod -Uri "$baseUrl/v1/save_seed_chunk" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

# Output response
Write-Host "Seed chunk saved. Campaign ID:"
Write-Host $response.campaign_id
Write-Host ""

# GET the seed chunk back
Write-Host "Retrieving campaign..."
$result = Invoke-RestMethod -Uri "$baseUrl/v1/load_campaign/$($response.campaign_id)"

# Output full response
Write-Host "Retrieved Campaign Data:"
$result | ConvertTo-Json -Depth 3

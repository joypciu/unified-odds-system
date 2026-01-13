# Manual Network Inspection Guide for OddPortal

Since automated network inspection is blocked, follow these steps manually:

## Step 1: Open Browser DevTools

1. Open Chrome/Edge browser
2. Press `F12` to open DevTools
3. Go to **Network** tab
4. Check "Preserve log" option
5. Clear existing requests (🚫 icon)

## Step 2: Load OddPortal Page

Navigate to: https://www.oddsportal.com/football/england/premier-league/

## Step 3: Analyze Network Traffic

Look for requests containing:

### A. GraphQL Endpoints

- URL contains: `/graphql`
- Request Type: `POST`
- Response Type: `application/json`

**What to check:**

- Click on the request
- Go to "Payload" tab
- Look for query/mutation operations
- Check "Response" tab for JSON structure

### B. REST API Calls

- URL patterns like:
  - `/api/matches`
  - `/api/odds`
  - `/api/events`
  - `/data/` endpoints
- Response Type: `application/json`

### C. XHR/Fetch Requests

- Filter by: `XHR` and `Fetch` in DevTools
- Look for JSON responses with match/odds data

## Step 4: Click on a Match

1. Click any match in the list
2. Watch Network tab for new requests
3. Look for requests that load:
   - Match details
   - Bookmaker odds
   - Historical data

## Step 5: Document Findings

For each interesting request, note:

1. **URL**: Full request URL
2. **Method**: GET/POST
3. **Headers**: Required headers (especially auth tokens)
4. **Payload**: Request body (for POST requests)
5. **Response**: JSON structure

## Common Patterns to Look For

### Example 1: GraphQL

```
POST https://www.oddsportal.com/graphql
Content-Type: application/json

{
  "query": "query GetMatches($league: String!) { matches(league: $league) { id homeTeam awayTeam odds { bookmaker home draw away } } }",
  "variables": { "league": "premier-league" }
}
```

### Example 2: REST API

```
GET https://www.oddsportal.com/api/v1/leagues/premier-league/matches
Accept: application/json
X-Api-Key: abc123...
```

### Example 3: Data Endpoint

```
GET https://www.oddsportal.com/data/matches.json?league=premier-league
```

## What We're Looking For

✅ **GOOD SIGNS** (we can use API):

- JSON responses with match/odds data
- Predictable URL patterns
- No complex authentication
- Public endpoints

❌ **BAD SIGNS** (must use HTML scraping):

- No JSON endpoints found
- All data rendered in HTML only
- Complex auth tokens that expire
- WebSocket-only data delivery
- Encrypted/obfuscated responses

## Next Steps

### If APIs Found:

1. Document all endpoints
2. Test with `curl` or Postman
3. Build Python API client
4. Replace HTML scraper

### If No APIs:

Current HTML scraping approach is correct - continue using it.

## Quick Test Commands

### Test with curl:

```powershell
# Example - adjust URL based on findings
curl "https://www.oddsportal.com/api/matches" `
  -H "Accept: application/json" `
  -H "User-Agent: Mozilla/5.0"
```

### Test with Python:

```python
import requests

url = "https://www.oddsportal.com/api/endpoint"  # Replace with found endpoint
headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
}

response = requests.get(url, headers=headers)
print(response.status_code)
print(response.json())
```

# Basketball API Timeout Fix - Summary

## Problem Identified

The `/oddsmagnet/api/basketball` endpoint was experiencing connection timeouts causing errors like:

```
GET http://142.44.160.36:8000/oddsmagnet/api/basketball net::ERR_CONNECTION_TIMED_OUT
```

## Root Causes

1. **Synchronous File I/O**: The endpoint was using blocking `open()` and `json.load()` calls
2. **No Timeout Protection**: If the file was being written by the collector, the read would hang indefinitely
3. **Poor Error Handling**: No graceful degradation for missing or corrupted files
4. **Missing HTTP Status Codes**: Browser couldn't distinguish between different failure modes

## Solution Implemented

### Changes to `core/live_odds_viewer_clean.py`

1. **Added Async File Reading**:

   - Imported `aiofiles` for non-blocking file operations
   - Converted synchronous file reads to async

2. **Added Timeout Protection**:

   - 5-second timeout for file read operations
   - Compatible with Python 3.11+ (`asyncio.timeout`) and older versions (`asyncio.wait_for`)

3. **Improved Error Responses**:

   - **503 Service Unavailable**: When file doesn't exist or is corrupted
   - **504 Gateway Timeout**: When file read times out
   - **200 OK**: When data is successfully retrieved
   - All errors include helpful messages explaining the situation

4. **Better File Existence Checks**:
   - Checks if `oddsmagnet_basketball.json` exists before attempting to read
   - Returns proper error message if basketball collector isn't running

### Code Changes

**Before:**

```python
# Blocking, no timeout
with open(basketball_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
```

**After:**

```python
# Async with timeout, proper error handling
try:
    # Python 3.11+ has asyncio.timeout, fallback for older versions
    try:
        async with asyncio.timeout(5.0):
            async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
    except AttributeError:
        async def read_file():
            async with aiofiles.open(basketball_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        data = await asyncio.wait_for(read_file(), timeout=5.0)
except asyncio.TimeoutError:
    return JSONResponse(
        content={'error': 'Request timeout', ...},
        status_code=504
    )
```

## Dependencies

- ✅ `aiofiles` - Already in `config/requirements.txt`

## Deployment

### Quick Deploy on VPS:

```bash
ssh ubuntu@142.44.160.36
cd /home/ubuntu/services/unified-odds
git pull origin main
chmod +x deployment/fix_basketball_timeout.sh
./deployment/fix_basketball_timeout.sh
```

### Manual Deploy:

```bash
# Pull changes
git pull origin main

# Restart web viewer
sudo systemctl restart live-odds-viewer.service

# Verify basketball collector is running
ps aux | grep basketball_realtime

# If not running, restart unified odds
sudo systemctl restart unified-odds.service

# Test endpoint
curl -v http://localhost:8000/oddsmagnet/api/basketball
```

## Expected Behavior After Fix

### Scenario 1: Normal Operation

- Basketball data file exists and is up-to-date
- **Response**: 200 OK with JSON data
- **Time**: < 1 second

### Scenario 2: Basketball Collector Not Running

- File doesn't exist
- **Response**: 503 Service Unavailable
- **Message**: "Basketball collector not running. Start with: python bookmakers/oddsmagnet/oddsmagnet_basketball_realtime.py"
- **Time**: Immediate

### Scenario 3: File Being Written

- File exists but is being updated by collector
- **Response**: 504 Gateway Timeout
- **Message**: "Basketball data file is being updated. Please try again in a moment."
- **Time**: ~5 seconds (timeout)

### Scenario 4: Corrupted Data

- File exists but contains invalid JSON
- **Response**: 503 Service Unavailable
- **Message**: "Basketball data is being updated. Please try again in a moment."
- **Time**: < 5 seconds

## Testing

### Test Commands:

```bash
# Test endpoint directly
curl http://142.44.160.36:8000/oddsmagnet/api/basketball

# Test with verbose output
curl -v http://142.44.160.36:8000/oddsmagnet/api/basketball

# Check response time
time curl http://142.44.160.36:8000/oddsmagnet/api/basketball > /dev/null

# Monitor logs
sudo journalctl -u live-odds-viewer.service -f
```

### Frontend Testing:

1. Open OddsMagnet viewer: http://142.44.160.36/oddsmagnet
2. Click "Basketball" sport button
3. Should see either:
   - Data loads successfully
   - Clear error message (not browser timeout)
   - Retry works after collector starts

## Benefits

✅ **No More Browser Timeouts**: All timeouts are handled server-side with proper HTTP codes
✅ **Faster Error Detection**: Users get immediate feedback instead of waiting 60+ seconds
✅ **Better User Experience**: Clear error messages explain what's happening
✅ **Graceful Degradation**: System handles missing/incomplete data elegantly
✅ **Production Ready**: Proper async handling prevents blocking other requests

## Files Modified

1. `core/live_odds_viewer_clean.py` - Added async timeout handling
2. `FIX_DEPLOYMENT.txt` - Updated with basketball fix instructions
3. `deployment/fix_basketball_timeout.sh` - New deployment script

## Related Issues

This fix also benefits other similar endpoints that may experience the same issue:

- `/oddsmagnet/api/basketball/nba`
- `/oddsmagnet/api/basketball/ncaa`

Consider applying similar async timeout handling to these endpoints as well.

## Monitoring

After deployment, monitor:

- Response times: Should be < 5 seconds
- Error rates: 503/504 errors should decrease as collector stabilizes
- Basketball collector uptime: `ps aux | grep basketball_realtime`
- File modification times: `stat bookmakers/oddsmagnet/oddsmagnet_basketball.json`

## Date: December 15, 2025

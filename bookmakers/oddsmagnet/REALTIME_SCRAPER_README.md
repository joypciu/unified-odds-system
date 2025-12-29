# OddsMagnet Real-Time Parallel Scraper

## Overview

Production-ready scraper that continuously updates odds data using browser automation. Works both locally (with remote debugging) and on VPS (headless Chrome).

## Features

✅ **Real-time continuous updates** - Runs in loop with configurable intervals
✅ **Parallel scraping** - Uses multiple browser tabs for maximum speed
✅ **Dual mode** - Works locally (remote debugging) and on VPS (headless)
✅ **Graceful shutdown** - Handles SIGINT/SIGTERM properly
✅ **Rate limiting** - Batched requests to prevent overload
✅ **Auto-recovery** - Retries on errors

## Installation

### Local (Windows)

1. Start Chrome with remote debugging:

   ```cmd
   START_CHROME_DEBUG.bat
   ```

2. Run the scraper:
   ```cmd
   python oddsmagnet_realtime_parallel.py --mode local --interval 30
   ```

### VPS (Ubuntu/Debian)

1. Run setup script:

   ```bash
   chmod +x setup_vps.sh
   ./setup_vps.sh
   ```

2. Run the scraper:
   ```bash
   python oddsmagnet_realtime_parallel.py --mode vps --interval 30
   ```

## Usage

### Command Line Options

```bash
python oddsmagnet_realtime_parallel.py [OPTIONS]

Options:
  --mode {local,vps}     local: remote debugging, vps: headless Chrome (default: local)
  --concurrent INT       Max concurrent browser tabs (default: 20)
  --interval INT         Minimum seconds between iterations (default: 30)
  --single              Run single iteration and exit
```

### Examples

**Local continuous mode (30s interval):**

```cmd
python oddsmagnet_realtime_parallel.py --mode local --interval 30
```

**VPS continuous mode (60s interval):**

```bash
python oddsmagnet_realtime_parallel.py --mode vps --interval 60
```

**Single run (testing):**

```cmd
python oddsmagnet_realtime_parallel.py --mode local --single
```

**High performance (50 concurrent tabs, 20s interval):**

```bash
python oddsmagnet_realtime_parallel.py --mode vps --concurrent 50 --interval 20
```

## VPS Deployment

### As Background Process

```bash
nohup python oddsmagnet_realtime_parallel.py --mode vps --interval 30 > scraper.log 2>&1 &
```

### As Systemd Service

Create `/etc/systemd/system/oddsmagnet-scraper.service`:

```ini
[Unit]
Description=OddsMagnet Real-Time Parallel Scraper
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/bookmakers/oddsmagnet
ExecStart=/usr/bin/python3 oddsmagnet_realtime_parallel.py --mode vps --interval 30
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable oddsmagnet-scraper
sudo systemctl start oddsmagnet-scraper
sudo systemctl status oddsmagnet-scraper
```

View logs:

```bash
sudo journalctl -u oddsmagnet-scraper -f
```

## Output Files

The scraper updates these JSON files:

- `oddsmagnet_top10.json` - Football (10 top leagues)
- `oddsmagnet_basketball.json` - Basketball
- `oddsmagnet_tennis.json` - Tennis
- `oddsmagnet_americanfootball.json` - American Football
- `oddsmagnet_tabletennis.json` - Table Tennis

## Configuration

Edit `SPORTS_CONFIG` in the script to customize:

```python
SPORTS_CONFIG = {
    'football': {
        'enabled': True,
        'top_leagues': 10,
        'output': 'oddsmagnet_top10.json',
        'markets': ['win market', 'over under betting', 'both teams to score'],
        'update_interval': 30  # seconds
    },
    # Add more sports...
}
```

## Performance

**Typical performance:**

- 600+ markets in ~5 minutes
- 2-3 markets/second
- 20 concurrent browser tabs

**Optimization tips:**

- Increase `--concurrent` for more speed (requires more RAM)
- Adjust `--interval` based on your needs
- On VPS: Consider adding swap space for memory

## Monitoring

Check iteration logs:

```bash
tail -f scraper.log
```

Monitor resource usage:

```bash
htop
```

## Troubleshooting

**Chrome won't start on VPS:**

```bash
# Install missing dependencies
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
```

**Out of memory:**

```bash
# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Scraper stops unexpectedly:**

- Check logs for errors
- Ensure Chrome/Chromium is properly installed
- Verify network connectivity
- Check disk space

## Comparison with Old Scrapers

| Feature         | Old (HTTP)       | New (Parallel)     |
| --------------- | ---------------- | ------------------ |
| Speed           | ~30s/100 markets | ~5min/600 markets  |
| CloudFront WAF  | ❌ Blocked       | ✅ Bypassed        |
| Bookmakers      | 0-1              | 2-10               |
| Real-time       | ✅ Yes           | ✅ Yes             |
| VPS Ready       | ✅ Yes           | ✅ Yes             |
| Parallelization | Thread-based     | Async browser tabs |

## License

Part of the VPS Deploy project.

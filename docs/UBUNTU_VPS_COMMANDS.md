# Essential Ubuntu VPS Commands - Quick Reference Guide

## 📋 Table of Contents

1. [System Monitoring](#system-monitoring)
2. [Process Management](#process-management)
3. [Service Management](#service-management)
4. [File Operations](#file-operations)
5. [Log Viewing](#log-viewing)
6. [Network Commands](#network-commands)
7. [User & Permissions](#user--permissions)
8. [Remote Access & File Transfer](#remote-access--file-transfer)
9. [Disk Management](#disk-management)
10. [Common Troubleshooting](#common-troubleshooting)

---

## System Monitoring

### Check Running Processes

**Understanding `ps aux`:**

- `ps` = Process Status (shows running processes)
- `a` = Show processes for all users
- `u` = Display user-oriented format (shows owner, CPU%, memory%, etc.)
- `x` = Include processes not attached to a terminal

```bash
# View all processes
ps aux
# Shows: USER, PID, %CPU, %MEM, VSZ, RSS, TTY, STAT, START, TIME, COMMAND

# View processes with memory usage sorted (highest first)
ps aux --sort=-%mem
# --sort=-%mem means sort by memory in descending order (- means reverse)

# View processes with CPU usage sorted (highest first)
ps aux --sort=-%cpu
# --sort=-%cpu means sort by CPU usage in descending order

# Find specific process using pipe (|) and grep
ps aux | grep python
# | (pipe) = Send output of first command to second command
# grep = Search for text pattern (finds lines containing "python")

ps aux | grep chrome
ps aux | grep unified-odds

# Example: Find all unified-odds related processes
ps aux | grep -E 'unified-odds|1xbet|fanduel|oddsmagnet' | grep -v grep
# -E = Extended regex (allows | for OR pattern)
# grep -v grep = Exclude lines containing "grep" (removes the grep command itself from results)
```

**Common `ps` Output Columns:**

- `USER` = Process owner
- `PID` = Process ID (unique number)
- `%CPU` = CPU usage percentage
- `%MEM` = Memory usage percentage
- `VSZ` = Virtual memory size (KB)
- `RSS` = Resident set size (actual physical memory in KB)
- `STAT` = Process state (R=running, S=sleeping, Z=zombie)
- `START` = When process started
- `TIME` = Total CPU time used
- `COMMAND` = Command that started the process

### Real-time Process Monitoring

**Understanding `top` and `htop`:**

- `top` = Table Of Processes (real-time process monitor)
- `htop` = Enhanced version of top with better UI

```bash
# Interactive process viewer (basic)
top
# Shows live updating list of processes with CPU, memory usage
# Updates every few seconds automatically

# Better interactive viewer (if installed)
htop
# Color-coded, more user-friendly interface
# Shows CPU bars, memory bars, process tree

# Press 'q' to quit both top and htop
# Press 'M' to sort by memory (in top)
# Press 'P' to sort by CPU (in top)
# Press 'k' to kill a process
# Press 'h' for help
```

### Memory Usage

**Understanding `free` command:**

- `free` = Display amount of free and used memory
- `-h` = Human-readable format (GB, MB instead of bytes)

```bash
# Check memory usage (human readable)
free -h
# Shows: total, used, free, shared, buff/cache, available

# Example output:
#               total        used        free      shared  buff/cache   available
# Mem:            47Gi       8.2Gi        38Gi       127Mi       1.4Gi        39Gi

# Check memory for specific service
systemctl status unified-odds.service | grep Memory
# systemctl = System control (manage services)
# status = Show service status
# grep Memory = Find lines containing "Memory"

# Continuous memory monitoring (updates every 2 seconds)
watch -n 2 free -h
# watch = Execute command periodically
# -n 2 = Update interval of 2 seconds
```

**Memory Terms Explained:**

- `total` = Total installed RAM
- `used` = Memory currently in use
- `free` = Completely unused memory
- `shared` = Memory used by tmpfs (temporary filesystem)
- `buff/cache` = Memory used for buffers and cache (can be freed if needed)
- `available` = Memory available for new applications (includes some buff/cache)

### CPU Usage

```bash
# Check CPU info
lscpu

# CPU usage per core
mpstat -P ALL

# CPU load average
uptime
```

### System Information

```bash
# OS version
cat /etc/os-release

# Kernel version
uname -r

# Full system info
uname -a

# System uptime
uptime

# Hostname
hostname
```

---

## Process Management

### Kill Processes

**Understanding Kill Commands:**

- `kill` = Send signal to process (default: terminate gracefully)
- `kill -9` = Force kill (SIGKILL - cannot be ignored)
- `pkill` = Kill by process name pattern
- `killall` = Kill all processes by exact name
- `PID` = Process ID (unique number for each process)

```bash
# Kill by process ID (graceful - allows cleanup)
kill <PID>
kill 12345
# Sends SIGTERM (signal 15) - process can catch and cleanup

# Force kill by PID (immediate - no cleanup)
kill -9 <PID>
sudo kill -9 12345
# Sends SIGKILL (signal 9) - process cannot ignore
# Use when process doesn't respond to regular kill

# Kill by process name (kills all matching)
pkill python
# pkill = Process kill (matches partial name)

pkill chrome
sudo pkill -9 -f chrome
# -f = Match against full command line (not just process name)
# -9 = Force kill signal

# Kill all processes matching pattern
killall python3
# killall = Kill ALL processes with exact name

killall -9 chrome
# Forces all chrome processes to stop

# Kill all Chrome processes (multiple variations)
sudo killall -9 chrome chrome-headless-shell chromium
# Kills chrome, chrome-headless-shell, and chromium processes

# Example: Kill all unified-odds related processes
sudo pkill -9 -f unified-odds
# Kills any process with "unified-odds" in command line

sudo pkill -9 -f fanduel
sudo pkill -9 -f 1xbet
```

**When to use each:**

- `kill <PID>` - When you know exact PID and want graceful shutdown
- `kill -9 <PID>` - When process is frozen/not responding
- `pkill <name>` - When you want to kill by name pattern
- `killall <name>` - When you want to kill all instances of exact name

### Process Information

**Understanding Process Commands:**

- `pgrep` = Process grep (find PID by name)
- `wc` = Word count (-l counts lines)
- `$?` = Exit status of last command (0=success, 1=failure)

```bash
# Get PID of running process
pgrep python
# Returns process ID(s) of processes named "python"

pgrep -f unified-odds
# -f = Match against full command line

# Count processes (useful for monitoring)
ps aux | grep chrome | grep -v grep | wc -l
# wc -l = Word count, lines (counts number of lines)
# Shows total number of chrome processes

# Check if process is running
ps aux | grep unified-odds | grep -v grep
echo $?  # 0 = running (found), 1 = not running (not found)
# $? = Special variable containing exit status of last command
# 0 = success (process found)
# 1 = failure (process not found)
```

**Practical Example:**

```bash
# Count how many Python processes are running
ps aux | grep python | grep -v grep | wc -l

# Check if unified-odds service is running
if ps aux | grep unified-odds | grep -v grep > /dev/null; then
    echo "Service is running"
else
    echo "Service is NOT running"
fi
```

---

## Service Management

**Understanding systemctl:**

- `systemctl` = System control command for managing systemd services
- `status` = Show current state and recent logs
- `start` = Begin running a service
- `stop` = Stop a running service
- `restart` = Stop then start (full restart)
- `reload` = Reload config without stopping
- `enable` = Auto-start on boot
- `disable` = Don't auto-start on boot
- `--no-pager` = Display all output at once (no scrolling)

### Systemctl Commands

```bash
# Start a service
sudo systemctl start unified-odds.service
# Begins running the service if not running

# Stop a service
sudo systemctl stop unified-odds.service
# Gracefully stops the service

# Restart a service (stop then start)
sudo systemctl restart unified-odds.service
# Full restart - useful after code changes or config updates

# Reload service configuration (without stopping)
sudo systemctl reload unified-odds.service
# Only reloads config, doesn't restart process
# Not all services support this

# Check service status
systemctl status unified-odds.service
# Shows: Active state, PID, memory, recent logs

systemctl status unified-odds.service --no-pager
# --no-pager = Show all output at once (don't paginate)

# Enable service (start on boot)
sudo systemctl enable unified-odds.service

# Disable service (don't start on boot)
sudo systemctl disable unified-odds.service

# Check if service is active
systemctl is-active unified-odds.service

# Check if service is enabled
systemctl is-enabled unified-odds.service

# List all services
systemctl list-units --type=service

# List running services
systemctl list-units --type=service --state=running

# View service file
systemctl cat unified-odds.service

# Reload systemd daemon (after editing service files)
sudo systemctl daemon-reload
```

---

## File Operations

**Understanding ls (list) command:**

- `ls` = List directory contents
- `-l` = Long format (detailed info: permissions, owner, size, date)
- `-h` = Human-readable sizes (KB, MB, GB instead of bytes)
- `-a` = All files (including hidden files starting with .)
- `-t` = Sort by modification time (newest first)
- `-S` = Sort by size (largest first)
- `-r` = Reverse order

### List Files

```bash
# List files
ls
# Shows file and directory names in current directory

# List with details
ls -l
# Long format shows: permissions, owner, group, size, date, name
# Example: -rw-r--r-- 1 ubuntu ubuntu 1024 Dec 29 10:00 file.txt

# List with human-readable sizes
ls -lh
# Shows sizes as 1K, 234M, 2.1G instead of bytes
# Example: -rw-r--r-- 1 ubuntu ubuntu 1.5M Dec 29 10:00 file.txt

# List all files including hidden
ls -la
# Shows files starting with . (like .bashrc, .git)

# List sorted by modification time
ls -lt
# Newest files first

# List sorted by size
ls -lhS
# Largest files first (-h for human-readable)

# Combine options
ls -lhtr
# -l = long format, -h = human sizes, -t = by time, -r = reverse (oldest first)

# Example: Check data files
ls -lh /home/ubuntu/services/unified-odds/bookmakers/1xbet/*.json
```

### View File Contents

**Understanding file viewing commands:**

- `cat` = Concatenate and print (shows entire file)
- `head` = Show first lines of file
- `tail` = Show last lines of file
- `-n` = Number of lines to show
- `-f` = Follow (tail only, for real-time updates)
- `less` = View file with navigation (recommended for large files)
- `more` = View file page by page

```bash
# View entire file
cat filename.txt
# Prints all content to screen

# View first 10 lines
head filename.txt
# Default is 10 lines

head -20 filename.txt  # first 20 lines
# -20 = Show first 20 lines

# View last 10 lines
tail filename.txt
# Default is 10 lines

tail -30 /var/log/syslog  # last 30 lines
# -30 = Show last 30 lines

# Follow file in real-time (useful for logs)
tail -f filename.log
# -f = Follow (continuously shows new lines as they're added)
# Press Ctrl+C to stop following

tail -f /var/log/syslog
# Perfect for monitoring log files

# View file with pagination
less filename.txt
# Interactive viewer:
# - Arrow keys = scroll up/down
# - Space = next page, 'b' = previous page
# - '/' = search forward, '?' = search backward
# - 'q' = quit

# View large file efficiently
more filename.txt
# Simple paginator (Space to continue, 'q' to quit)
```

### Search in Files

**Understanding grep (search) command:**

- `grep` = Global Regular Expression Print (search tool)
- `-r` = Recursive (search in all subdirectories)
- `-i` = Ignore case (case-insensitive search)
- `-n` = Show line numbers
- `-v` = Invert match (show lines that DON'T match)
- `-c` = Count matches
- `-C` = Context (show surrounding lines)

```bash
# Search for text in file
grep "error" filename.log
# Shows all lines containing "error"

# Search recursively in directory
grep -r "error" /var/log/
# -r = Searches in all files under /var/log/ and subdirectories

# Search case-insensitive
grep -i "error" filename.log
# -i = Matches "error", "Error", "ERROR", etc.

# Search with line numbers
grep -n "error" filename.log
# -n = Shows line number before each match
# Example output: 42:error occurred

# Search excluding pattern
grep -v "grep" output.txt
# -v = Shows lines that DON'T contain "grep"
# Commonly used: ps aux | grep chrome | grep -v grep

# Count matches
grep -c "error" filename.log
# -c = Just show count, not the lines themselves

# Search with context (3 lines before and after)
grep -C 3 "error" filename.log
# -C 3 = Shows 3 lines before and 3 after each match
# Useful for understanding error context

# Example: Search for 1xbet in logs
grep -i "1xbet" /var/log/syslog
```

### Find Files

**Understanding find command:**

- `find` = Search for files and directories
- `-name` = Match by filename pattern
- `-mtime` = Modified time in days (-1 = last 24 hours)
- `-mmin` = Modified time in minutes (-10 = last 10 minutes)
- `-size` = File size (+100M = larger than 100MB)
- `-delete` = Delete matching files (BE CAREFUL!)
- `*` = Wildcard (matches anything)

```bash
# Find files by name
find /path -name "filename.txt"
# Searches for exact filename

find /home/ubuntu -name "*.json"
# *.json = Wildcard: any file ending with .json

# Find files modified in last 24 hours
find /path -mtime -1
# -mtime -1 = Modified within last 1 day
# +1 = more than 1 day ago

# Find files larger than 100MB
find /path -size +100M
# +100M = Larger than 100 megabytes
# Use: +1G for gigabytes, -10M for smaller than 10MB

# Find and delete files
find /tmp -name "*.tmp" -delete
# Finds and deletes all .tmp files
# WARNING: BE CAREFUL with -delete!

# Example: Find all JSON files
find /home/ubuntu/services/unified-odds -name "*.json"

# Find files modified in last 10 minutes
find /home/ubuntu/services/unified-odds -name "*.json" -mmin -10
# -mmin -10 = Modified within last 10 minutes
# Useful for checking which data files are updating
```

### File Operations

```bash
# Copy file
cp source.txt destination.txt
cp -r /source/directory /destination/directory  # recursive

# Move/rename file
mv oldname.txt newname.txt
mv /path/file.txt /new/path/

# Remove file
rm filename.txt
rm -f filename.txt  # force without confirmation
rm -r directory/    # recursive (delete directory)
rm -rf directory/   # force recursive (dangerous!)

# Create directory
mkdir new_directory
mkdir -p /path/to/nested/directory  # create parent directories

# Remove empty directory
rmdir directory/

# Create empty file or update timestamp
touch filename.txt

# Check file timestamps
stat filename.txt
stat -c '%y %n' filename.json  # modification time
```

---

## Log Viewing

### System Logs

```bash
# View system log
sudo cat /var/log/syslog

# View last 50 lines
sudo tail -50 /var/log/syslog

# Follow system log in real-time
sudo tail -f /var/log/syslog

# View auth log (login attempts)
sudo tail -f /var/log/auth.log
```

### Journalctl (systemd logs)

```bash
# View all logs
journalctl

# View logs for specific service
journalctl -u unified-odds.service

# View last 50 lines
journalctl -u unified-odds.service -n 50

# Follow logs in real-time
journalctl -u unified-odds.service -f

# View logs since boot
journalctl -b

# View logs from last hour
journalctl --since "1 hour ago"

# View logs from specific time
journalctl --since "2025-12-29 23:00:00"

# View logs with no pager
journalctl -u unified-odds.service --no-pager

# Search in logs
journalctl -u unified-odds.service | grep "error"

# Example: Check unified-odds service logs
journalctl -u unified-odds.service --no-pager -n 100 | grep -i '1xbet'
```

---

## Network Commands

### Check Network Connections

```bash
# Show all listening ports
sudo netstat -tulpn
sudo ss -tulpn  # newer alternative

# Check specific port
sudo netstat -tulpn | grep :8000
sudo ss -tulpn | grep :8000

# Show all network connections
netstat -an

# Check internet connectivity
ping google.com
ping -c 4 google.com  # send 4 packets only
```

### HTTP Requests

```bash
# GET request
curl http://142.44.160.36:8000

# GET request with headers
curl -I http://142.44.160.36:8000

# POST request
curl -X POST http://142.44.160.36:8000/api/data

# Download file
curl -O http://example.com/file.zip

# Follow redirects
curl -L http://example.com

# Save output to file
curl http://example.com -o output.html

# Example: Test API endpoint
curl -I http://142.44.160.36/oddsmagnet/football/top10
```

### Check Services

```bash
# Check if port is open
nc -zv 142.44.160.36 8000

# Check HTTP service
curl -I http://localhost:8000

# DNS lookup
nslookup google.com
dig google.com
```

---

## User & Permissions

### User Management

```bash
# Current user
whoami

# Switch to root
sudo su

# Switch to another user
sudo su - ubuntu

# Add user
sudo adduser newuser

# Delete user
sudo deluser username

# List all users
cat /etc/passwd
```

### File Permissions

```bash
# View permissions
ls -l filename.txt

# Change permissions (numeric)
chmod 644 filename.txt   # rw-r--r--
chmod 755 script.sh      # rwxr-xr-x
chmod 600 private.key    # rw-------

# Change permissions (symbolic)
chmod +x script.sh       # add execute
chmod -w filename.txt    # remove write
chmod u+x,g+x script.sh  # add execute for user and group

# Change owner
sudo chown ubuntu:ubuntu filename.txt
sudo chown -R ubuntu:ubuntu /directory/

# Example: Make script executable
chmod +x /home/ubuntu/scripts/deploy.sh
```

### Sudo

```bash
# Run command as root
sudo command

# Edit file as root
sudo nano /etc/hosts

# Run previous command with sudo
sudo !!

# Run shell as root
sudo -i
```

---

## Remote Access & File Transfer

### SSH

```bash
# Connect to VPS
ssh ubuntu@142.44.160.36

# Connect with key file
ssh -i /path/to/key.pem ubuntu@142.44.160.36

# Connect with different port
ssh -p 2222 ubuntu@142.44.160.36

# Execute command remotely
ssh ubuntu@142.44.160.36 "ls -lh /home/ubuntu"

# SSH with no host key checking
ssh -o StrictHostKeyChecking=no ubuntu@142.44.160.36
```

### SCP (Secure Copy)

```bash
# Copy file TO server
scp local_file.txt ubuntu@142.44.160.36:/home/ubuntu/

# Copy file FROM server
scp ubuntu@142.44.160.36:/home/ubuntu/file.txt ./

# Copy directory recursively
scp -r local_directory/ ubuntu@142.44.160.36:/home/ubuntu/

# Copy with key file
scp -i key.pem file.txt ubuntu@142.44.160.36:/home/ubuntu/

# Example: Upload scraper to VPS
scp -i vps_ssh_key.txt parallel_sports_scraper.py ubuntu@142.44.160.36:/home/ubuntu/services/unified-odds/bookmakers/oddsmagnet/
```

---

## Disk Management

### Disk Space

```bash
# Check disk usage
df -h

# Check specific directory size
du -sh /home/ubuntu
du -h /home/ubuntu  # all subdirectories

# Find largest directories
du -h /home/ubuntu | sort -rh | head -10

# Check inode usage
df -i

# Example: Check unified-odds directory size
du -sh /home/ubuntu/services/unified-odds
```

### Cleanup

```bash
# Clean package cache
sudo apt clean
sudo apt autoclean

# Remove unused packages
sudo apt autoremove

# Clear temp files
sudo rm -rf /tmp/*

# Find and delete old log files
find /var/log -name "*.log" -mtime +30 -delete

# Example: Clean Chrome temp directories
sudo rm -rf /tmp/chrome_*
sudo rm -rf /tmp/playwright_*
```

---

## Common Troubleshooting

### Check What's Using Memory

```bash
# Top memory consumers
ps aux --sort=-%mem | head -10

# Memory by process
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20
```

### Check What's Using CPU

```bash
# Top CPU consumers
ps aux --sort=-%cpu | head -10
```

### Find Zombie Processes

```bash
# Find zombie processes
ps aux | grep defunct
ps aux | grep Z
```

### Check Port Usage

```bash
# What's using port 8000?
sudo lsof -i :8000
sudo netstat -tulpn | grep :8000
sudo ss -tulpn | grep :8000
```

### Service Won't Start

```bash
# Check service status with details
systemctl status unified-odds.service -l

# Check recent errors
journalctl -u unified-odds.service -n 50

# Check if port is already in use
sudo netstat -tulpn | grep :8000

# Check file permissions
ls -l /etc/systemd/system/unified-odds.service
```

### Out of Disk Space

```bash
# Find large files
find / -type f -size +100M 2>/dev/null

# Find largest directories
du -h / | sort -rh | head -20

# Clean logs
sudo journalctl --vacuum-time=7d  # keep last 7 days
sudo journalctl --vacuum-size=500M  # keep max 500MB
```

---

## Quick Unified-Odds System Commands

### Start/Stop System

```bash
# Start unified-odds service
sudo systemctl start unified-odds.service

# Stop unified-odds service
sudo systemctl stop unified-odds.service

# Restart unified-odds service
sudo systemctl restart unified-odds.service

# Check status
systemctl status unified-odds.service
```

### Monitor System

```bash
# Check all processes
ps aux | grep -E 'unified-odds|1xbet|oddsmagnet|fanduel' | grep python | grep -v grep

# Check Chrome processes
ps aux | grep chrome | grep -v grep | wc -l

# Check memory usage
free -h
systemctl status unified-odds.service | grep Memory
```

### View Logs

```bash
# Service logs (last 50 lines)
journalctl -u unified-odds.service -n 50

# Follow logs in real-time
journalctl -u unified-odds.service -f

# Check 1xBet activity
journalctl -u unified-odds.service --no-pager -n 100 | grep -i '1xbet'

# Check OddsMagnet logs
tail -50 /home/ubuntu/services/unified-odds/bookmakers/oddsmagnet/scraper.log
```

### Check Data Files

```bash
# List data files with timestamps
ls -lh /home/ubuntu/services/unified-odds/bookmakers/1xbet/*.json

# Check file modification time
stat -c '%y %n' /home/ubuntu/services/unified-odds/bookmakers/1xbet/1xbet_live.json

# View file content
tail -20 /home/ubuntu/services/unified-odds/bookmakers/1xbet/1xbet_live.json
```

### Emergency Cleanup

```bash
# Kill all Chrome processes
sudo killall -9 chrome chrome-headless-shell

# Kill all Python processes from unified-odds
sudo pkill -9 -f unified-odds

# Clean temp directories
sudo rm -rf /tmp/chrome_* /tmp/fd_master_* /tmp/playwright_*

# Restart service
sudo systemctl restart unified-odds.service
```

---

## Useful One-Liners

```bash
# Check system resources
echo "CPU: $(uptime | awk '{print $10}') | Memory: $(free -h | awk 'NR==2{print $3"/"$2}') | Disk: $(df -h / | awk 'NR==2{print $3"/"$2}')"

# Count total processes
ps aux | wc -l

# Find process by port
sudo lsof -i :8000 | grep LISTEN

# Find all Python processes with memory usage
ps aux | grep python | grep -v grep | awk '{print $2, $4, $11}' | sort -k2 -rn

# Check if unified-odds is running
systemctl is-active unified-odds.service && echo "Running" || echo "Not running"

# Monitor unified-odds memory every 2 seconds
watch -n 2 "systemctl status unified-odds.service | grep Memory"

# Tail multiple log files simultaneously
tail -f /var/log/syslog /home/ubuntu/services/unified-odds/bookmakers/oddsmagnet/scraper.log
```

---

## Keyboard Shortcuts in Terminal

- `Ctrl + C` - Kill current process
- `Ctrl + Z` - Suspend current process
- `Ctrl + D` - Exit terminal/logout
- `Ctrl + L` - Clear screen
- `Ctrl + A` - Move to beginning of line
- `Ctrl + E` - Move to end of line
- `Ctrl + U` - Delete from cursor to beginning of line
- `Ctrl + K` - Delete from cursor to end of line
- `Ctrl + R` - Search command history
- `Tab` - Auto-complete
- `↑` / `↓` - Navigate command history

---

## Important Safety Tips

⚠️ **Always be careful with these commands:**

```bash
rm -rf /              # NEVER DO THIS - Deletes everything!
sudo rm -rf /*        # NEVER DO THIS - Deletes everything!
chmod -R 777 /        # NEVER DO THIS - Makes everything writable!
```

✅ **Best Practices:**

- Always use `sudo` carefully
- Test commands on test files first
- Make backups before major changes
- Use `--help` or `man` to learn about commands
- Use Tab completion to avoid typos
- Double-check paths before using `rm -rf`

---

## Getting Help

```bash
# Manual for any command
man ls
man systemctl

# Quick help
ls --help
systemctl --help

# Search for command
apropos search_term
```

---

**Remember:** When in doubt, use `--help` or `man <command>` to learn more!

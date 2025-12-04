#!/usr/bin/env python3
"""
Pre-Deployment Checklist
Verifies that the project is ready for GitHub-based VPS deployment
"""

import sys
from pathlib import Path
import json

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_check(passed, message):
    if passed:
        print(f"{Colors.GREEN}✅{Colors.END} {message}")
    else:
        print(f"{Colors.RED}❌{Colors.END} {message}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠️{Colors.END}  {message}")

def print_info(message):
    print(f"{Colors.BLUE}ℹ️{Colors.END}  {message}")

def check_file_exists(filepath, description):
    """Check if a required file exists"""
    exists = filepath.exists()
    print_check(exists, f"{description}: {filepath.name}")
    return exists

def check_github_workflow():
    """Check GitHub Actions workflow file"""
    print_header("📋 Checking GitHub Actions Workflow")
    
    workflow_file = Path('.github/workflows/deploy.yml')
    exists = check_file_exists(workflow_file, "GitHub Actions workflow")
    
    if exists:
        content = workflow_file.read_text()
        has_secrets = all(x in content for x in ['VPS_HOST', 'VPS_USERNAME', 'VPS_SSH_KEY', 'VPS_PORT'])
        print_check(has_secrets, "Workflow uses GitHub secrets")
        
        has_deploy = 'git pull origin main' in content
        print_check(has_deploy, "Workflow includes deployment steps")
        
        has_restart = 'systemctl restart' in content
        print_check(has_restart, "Workflow restarts service")
        
        return exists and has_secrets and has_deploy and has_restart
    
    return False

def check_chrome_helper():
    """Check chrome_helper.py"""
    print_header("🔧 Checking Chrome Helper")
    
    chrome_helper = Path('chrome_helper.py')
    exists = check_file_exists(chrome_helper, "Chrome helper module")
    
    if exists:
        content = chrome_helper.read_text()
        has_windows = 'Windows' in content and 'Program Files' in content
        print_check(has_windows, "Supports Windows Chrome paths")
        
        has_linux = 'Linux' in content and '/usr/bin/google-chrome' in content
        print_check(has_linux, "Supports Ubuntu Chrome paths")
        
        has_xvfb = 'xvfb' in content.lower() or 'DISPLAY' in content
        print_check(has_xvfb, "Handles xvfb/virtual display")
        
        return exists and has_windows and has_linux
    
    return False

def check_service_file():
    """Check systemd service file"""
    print_header("⚙️ Checking Systemd Service File")
    
    service_file = Path('unified-odds.service')
    exists = check_file_exists(service_file, "Systemd service file")
    
    if exists:
        content = service_file.read_text()
        has_xvfb = 'xvfb-run' in content
        print_check(has_xvfb, "Uses xvfb-run for virtual display")
        
        has_workdir = 'WorkingDirectory' in content
        print_check(has_workdir, "Has working directory")
        
        has_restart = 'Restart=always' in content
        print_check(has_restart, "Auto-restart enabled")
        
        has_memory = 'MemoryMax' in content
        print_check(has_memory, "Memory limit configured")
        
        return exists and has_xvfb and has_workdir and has_restart
    
    return False

def check_deployment_script():
    """Check deployment script"""
    print_header("📦 Checking Deployment Script")
    
    deploy_script = Path('deploy_unified_odds.sh')
    exists = check_file_exists(deploy_script, "Deployment script")
    
    if exists:
        content = deploy_script.read_text()
        has_chrome = 'google-chrome-stable' in content
        print_check(has_chrome, "Installs Google Chrome")
        
        has_xvfb = 'xvfb' in content
        print_check(has_xvfb, "Installs xvfb")
        
        has_venv = 'venv' in content
        print_check(has_venv, "Creates Python virtual environment")
        
        has_git = 'git clone' in content or 'git pull' in content
        print_check(has_git, "Clones/updates from GitHub")
        
        return exists and has_chrome and has_xvfb and has_venv and has_git
    
    return False

def check_gitignore():
    """Check .gitignore file"""
    print_header("🚫 Checking .gitignore")
    
    gitignore = Path('.gitignore')
    exists = check_file_exists(gitignore, ".gitignore file")
    
    if exists:
        content = gitignore.read_text()
        ignores_data = 'unified_odds.json' in content
        print_check(ignores_data, "Ignores generated data files")
        
        ignores_cache = 'cache_data.json' in content or 'cache_backups' in content
        print_check(ignores_cache, "Ignores cache files")
        
        ignores_logs = '*.log' in content or 'logs/' in content
        print_check(ignores_logs, "Ignores log files")
        
        ignores_venv = 'venv/' in content
        print_check(ignores_venv, "Ignores virtual environment")
        
        # Check if config.json is handled properly
        if 'config.json' in content:
            print_warning("config.json is in .gitignore (credentials won't be pushed)")
        else:
            print_warning("config.json is NOT in .gitignore (credentials may be pushed!)")
        
        return exists and ignores_data and ignores_logs and ignores_venv
    
    return False

def check_requirements():
    """Check requirements.txt"""
    print_header("📚 Checking Python Dependencies")
    
    requirements = Path('requirements.txt')
    exists = check_file_exists(requirements, "requirements.txt file")
    
    if exists:
        content = requirements.read_text()
        deps = ['patchright', 'playwright', 'fastapi', 'uvicorn', 'psutil', 'aiofiles']
        
        for dep in deps:
            has_dep = dep in content.lower()
            print_check(has_dep, f"Includes {dep}")
        
        return exists
    
    return False

def check_config_file():
    """Check config.json or template"""
    print_header("⚙️ Checking Configuration")
    
    config = Path('config.json')
    template = Path('config.json.template')
    
    has_config = config.exists()
    has_template = template.exists()
    
    if has_config:
        print_check(True, "config.json exists")
        try:
            with open(config) as f:
                data = json.load(f)
            
            has_email = 'email' in data
            print_check(has_email, "Has email configuration")
            
            has_monitoring = 'monitoring' in data
            print_check(has_monitoring, "Has monitoring configuration")
            
            has_cache = 'cache' in data
            print_check(has_cache, "Has cache configuration")
            
            # Check if credentials are real or template
            if has_email:
                sender = data['email'].get('sender_email', '')
                if 'your-email' in sender or 'example' in sender:
                    print_warning("Email credentials look like template values")
                else:
                    print_info("Email credentials appear to be configured")
            
            return True
        except json.JSONDecodeError:
            print_check(False, "config.json has JSON syntax errors!")
            return False
    
    elif has_template:
        print_warning("config.json.template exists but config.json doesn't")
        print_info("You'll need to create config.json on VPS after deployment")
        return True
    else:
        print_check(False, "No config.json or config.json.template found")
        return False

def check_documentation():
    """Check documentation files"""
    print_header("📖 Checking Documentation")
    
    docs = {
        'GITHUB_DEPLOYMENT_GUIDE.md': 'Complete deployment guide',
        'QUICKSTART_GITHUB_DEPLOY.md': 'Quick start guide',
        'README.md': 'Project README',
    }
    
    all_exist = True
    for doc, description in docs.items():
        exists = Path(doc).exists()
        print_check(exists, description)
        all_exist = all_exist and exists
    
    return all_exist

def check_directory_structure():
    """Check required directories"""
    print_header("📁 Checking Directory Structure")
    
    dirs = {
        'bet365': 'Bet365 scrapers',
        'fanduel': 'FanDuel scrapers',
        '1xbet': '1xBet scrapers',
        '.github/workflows': 'GitHub Actions workflows',
    }
    
    all_exist = True
    for dir_name, description in dirs.items():
        exists = Path(dir_name).exists()
        print_check(exists, description)
        all_exist = all_exist and exists
    
    return all_exist

def check_git_status():
    """Check if git is initialized"""
    print_header("🔧 Checking Git Status")
    
    git_dir = Path('.git')
    is_git_repo = git_dir.exists()
    print_check(is_git_repo, "Git repository initialized")
    
    if is_git_repo:
        # Check if there's a remote
        git_config = Path('.git/config')
        if git_config.exists():
            content = git_config.read_text()
            has_remote = 'github.com' in content
            print_check(has_remote, "GitHub remote configured")
            return has_remote
    else:
        print_info("Run 'git init' to initialize git repository")
    
    return is_git_repo

def print_summary(results):
    """Print summary and next steps"""
    print_header("📊 Summary")
    
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    
    print(f"Total checks: {total}")
    print(f"{Colors.GREEN}✅ Passed: {passed}{Colors.END}")
    if failed > 0:
        print(f"{Colors.RED}❌ Failed: {failed}{Colors.END}")
    
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\nCompletion: {percentage:.1f}%")
    
    if percentage == 100:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All checks passed! Ready for deployment!{Colors.END}")
        print_next_steps_success()
    elif percentage >= 80:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️ Most checks passed. Review failed items above.{Colors.END}")
        print_next_steps_partial()
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Several checks failed. Please fix issues above.{Colors.END}")
        print_next_steps_failed()

def print_next_steps_success():
    """Print next steps when all checks pass"""
    print("\n" + "="*70)
    print("🚀 NEXT STEPS")
    print("="*70)
    print("\n1. Push to GitHub:")
    print("   git add .")
    print("   git commit -m 'Setup GitHub deployment'")
    print("   git push origin main")
    
    print("\n2. Deploy to VPS:")
    print("   - Upload deploy_unified_odds.sh to VPS")
    print("   - Run: ./deploy_unified_odds.sh")
    
    print("\n3. Configure GitHub Secrets:")
    print("   - Go to: Settings → Secrets → Actions")
    print("   - Add: VPS_HOST, VPS_USERNAME, VPS_SSH_KEY, VPS_PORT")
    
    print("\n4. Test automatic deployment:")
    print("   - Make a small change")
    print("   - Push to GitHub")
    print("   - Check Actions tab for deployment status")
    
    print("\n📚 See QUICKSTART_GITHUB_DEPLOY.md for detailed instructions")

def print_next_steps_partial():
    """Print next steps when most checks pass"""
    print("\n" + "="*70)
    print("⚠️ RECOMMENDED ACTIONS")
    print("="*70)
    print("\n1. Review failed checks above")
    print("2. Fix any missing or incorrect files")
    print("3. Run this script again: python check_deployment_ready.py")
    print("4. Once all checks pass, follow deployment steps")
    print("\n📚 See GITHUB_DEPLOYMENT_GUIDE.md for help")

def print_next_steps_failed():
    """Print next steps when many checks fail"""
    print("\n" + "="*70)
    print("❌ REQUIRED ACTIONS")
    print("="*70)
    print("\n1. Review all failed checks above")
    print("2. Missing files? Run the setup scripts")
    print("3. Check file contents for correctness")
    print("4. Ensure you're in the project root directory")
    print("5. Run this script again after fixes")
    print("\n📚 See GITHUB_DEPLOYMENT_GUIDE.md for complete setup")

def main():
    print(f"{Colors.BOLD}🔍 Pre-Deployment Checklist{Colors.END}")
    print("Checking if project is ready for GitHub-based VPS deployment...\n")
    
    # Run all checks
    results = {
        'GitHub Workflow': check_github_workflow(),
        'Chrome Helper': check_chrome_helper(),
        'Service File': check_service_file(),
        'Deployment Script': check_deployment_script(),
        'Gitignore': check_gitignore(),
        'Requirements': check_requirements(),
        'Configuration': check_config_file(),
        'Documentation': check_documentation(),
        'Directory Structure': check_directory_structure(),
        'Git Status': check_git_status(),
    }
    
    # Print summary
    print_summary(results)
    
    # Return exit code
    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(1)

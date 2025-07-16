#!/usr/bin/env python3
import os
import sys
import subprocess
import platform

def is_admin():
    """Check for admin/root privileges."""
    if os.name == "nt":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        return os.getuid() == 0

def update_repo():
    """
    If the current installation directory is a Git repo (editable install),
    perform a 'git pull origin main'. Otherwise, exit with a message.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    git_dir = os.path.join(current_dir, '.git')
    if os.path.exists(git_dir):
        print("Pulling latest changes from Git...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print("Git pull failed:", result.stderr)
            sys.exit(result.returncode)
    else:
        print("This installation does not appear to be a Git repository.")
        print("For non-editable installs, use 'pip install -U git+<repo-url>'")
        sys.exit(1)

def reinstall_package():
    """
    Reinstall/upgrade the package using pip.
    If not running as admin/root, use the --user flag.
    """
    print("Upgrading package via pip...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "."]
    if not is_admin():
        pip_cmd.append("--user")
    result = subprocess.run(pip_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("pip install failed:", result.stderr)
        sys.exit(result.returncode)

def main():
    update_repo()
    reinstall_package()

if __name__ == "__main__":
    main()

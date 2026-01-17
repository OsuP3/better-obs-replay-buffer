"""
Build script for Better OBS Replay Buffer
Creates a single standalone executable using PyInstaller

Usage:
    python build.py       - Build the executable
    python build.py clean - Remove build artifacts
"""

import subprocess
import sys
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")

def install_pyinstaller():
    """Install PyInstaller if not present"""
    try:
        import PyInstaller
        print("PyInstaller already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def clean():
    """Clean previous build artifacts"""
    for folder in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(folder):
            print(f"Removing {folder}")
            shutil.rmtree(folder)
    
    # Remove spec files
    for f in os.listdir(SCRIPT_DIR):
        if f.endswith(".spec"):
            os.remove(os.path.join(SCRIPT_DIR, f))

def build():
    """Build the single executable"""
    install_pyinstaller()
    clean()
    
    # Build single exe from app.py entry point
    # Includes service.py and settings_gui.py as hidden imports
    print("\n=== Building Better Replay Buffer ===")
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",  # No console window
        "--name", "BetterReplayBuffer",
        "--icon", "NONE",  # Add --icon path/to/icon.ico if you have one
        "--add-data", f"notification.wav;.",
        "--add-data", f"settings.example.txt;.",
        "--hidden-import", "service",
        "--hidden-import", "settings_gui",
        "app.py"
    ], cwd=SCRIPT_DIR)
    
    # Copy additional files to dist
    print("\n=== Copying additional files ===")
    shutil.copy(
        os.path.join(SCRIPT_DIR, "notification.wav"),
        os.path.join(DIST_DIR, "notification.wav")
    )
    shutil.copy(
        os.path.join(SCRIPT_DIR, "settings.example.txt"),
        os.path.join(DIST_DIR, "settings.example.txt")
    )
    shutil.copy(
        os.path.join(SCRIPT_DIR, "README.md"),
        os.path.join(DIST_DIR, "README.md")
    )
    
    print("\n" + "="*50)
    print("BUILD COMPLETE!")
    print("="*50)
    print(f"\nOutput files in: {DIST_DIR}")
    print("\nFiles created:")
    for f in os.listdir(DIST_DIR):
        fpath = os.path.join(DIST_DIR, f)
        size = os.path.getsize(fpath)
        if size > 1024*1024:
            print(f"  - {f} ({size / 1024 / 1024:.1f} MB)")
        else:
            print(f"  - {f} ({size / 1024:.1f} KB)")
    
    print("\n" + "-"*50)
    print("DISTRIBUTION INSTRUCTIONS:")
    print("-"*50)
    print("Zip the contents of the 'dist' folder.")
    print("\nUsers should:")
    print("  1. Extract to a folder")
    print("  2. Double-click BetterReplayBuffer.exe to configure")
    print("  3. Click 'Start' or enable 'Run on Startup'")
    print("\nThe same exe handles both settings and background service!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
        print("Cleaned build artifacts")
    else:
        build()

"""
Better Replay Buffer - Single Entry Point
==========================================
Run without arguments: Settings GUI
Run with --service:    Background replay buffer service
"""

import sys
import os

# -------------------------------
# PyInstaller support: determine base paths
# -------------------------------
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = EXE_DIR

def main():
    if "--service" in sys.argv:
        # Run the background service
        from service import run_service
        run_service()
    else:
        # Run the settings GUI
        from settings_gui import run_gui
        run_gui()

if __name__ == "__main__":
    main()

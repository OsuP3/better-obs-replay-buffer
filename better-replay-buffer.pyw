import os
import sys
import time
import threading
import subprocess

# -------------------------------
# Single instance check
# -------------------------------
import msvcrt

lock_file_path = os.path.join(os.getenv("TEMP"), "obs_toast.lock")
lock_file = open(lock_file_path, "w")
try:
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print("Another instance of the script is already running. Exiting...")
    sys.exit(0)

# -------------------------------
# Auto-install dependencies
# -------------------------------
try:
    import keyboard
except ImportError:
    print("Installing 'keyboard'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard"])
    import keyboard

try:
    import tkinter as tk
except ImportError:
    print("Tkinter not found. Make sure Python is installed with Tk support.")
    sys.exit(1)

try:
    import winsound
except ImportError:
    winsound = None  # optional if sound disabled

# -------------------------------
# Settings
# -------------------------------
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.txt")

def read_settings(path):
    settings = {}
    if not os.path.exists(path):
        print(f"{path} not found.")
        sys.exit(1)
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip().lower()] = value.strip().strip('"').lower()
    return settings

settings = read_settings(SETTINGS_FILE)

# -------------------------------
# Configurable settings with defaults
# -------------------------------
keybind = settings.get("savereplaykeybind", "ctrl+shift+s")
sound_file = settings.get("savereplaysound")
sound_enabled = settings.get("sound", "no") == "yes"
popup_enabled = settings.get("popup", "yes") == "yes"
WATCH_DIR = settings.get("savereplaysdirectory")
OBS_EXE = settings.get("obs_exe_path", r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
OBS_ARGS = settings.get("obs_args", "--disable-crash-handler --disable-shutdown-check --startreplaybuffer --minimize-to-tray")

# -------------------------------
# Validation
# -------------------------------
if not WATCH_DIR or not os.path.exists(WATCH_DIR):
    print(f"Directory '{WATCH_DIR}' not found.")
    sys.exit(1)

if sound_enabled and (not sound_file or not os.path.exists(sound_file)):
    print(f"Sound file '{sound_file}' not found. Disabling sound.")
    sound_enabled = False

if not os.path.exists(OBS_EXE):
    print(f"OBS executable not found at '{OBS_EXE}'. It will be skipped.")
    OBS_EXE = None
else:
    # Launch OBS immediately
    try:
        subprocess.Popen(f'"{OBS_EXE}" {OBS_ARGS}', shell=True, cwd=os.path.dirname(OBS_EXE))
        print("OBS started successfully.")
    except Exception as e:
        print(f"Failed to launch OBS at startup: {e}")

# -------------------------------
# Toast popup
# -------------------------------
def show_toast(file_path, duration=5):
    if not popup_enabled:
        return

    def open_file(event=None):
        os.startfile(file_path)
        toast.destroy()

    toast = tk.Tk()
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.attributes("-alpha", 0.9)

    width, height = 250, 60
    x = toast.winfo_screenwidth() - width - 10
    y = toast.winfo_screenheight() - height - 40
    toast.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(toast, bg="#333333")
    frame.pack(fill="both", expand=True)

    label = tk.Label(frame, text=os.path.basename(file_path), bg="#333333", fg="white", font=("Segoe UI", 10))
    label.pack(pady=10, padx=10)

    frame.bind("<Button-1>", open_file)
    label.bind("<Button-1>", open_file)

    toast.after(duration * 1000, toast.destroy)
    toast.mainloop()

# -------------------------------
# Monitor function
# -------------------------------
seen_files = set(os.listdir(WATCH_DIR))

def check_for_new_files():
    global seen_files
    start_time = time.time()
    while time.time() - start_time < 60:
        current_files = set(os.listdir(WATCH_DIR))
        new_files = current_files - seen_files
        for file in new_files:
            file_path = os.path.join(WATCH_DIR, file)
            # Show popup
            if popup_enabled:
                threading.Thread(target=show_toast, args=(file_path,), daemon=True).start()
            # Play sound
            if sound_enabled and winsound:
                threading.Thread(target=winsound.PlaySound, args=(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC), daemon=True).start()
        seen_files.update(new_files)
        time.sleep(0.5)

# -------------------------------
# Hotkey binding
# -------------------------------
keyboard.add_hotkey(keybind, check_for_new_files)

print(f"Press {keybind} to check for new files in '{WATCH_DIR}' for 60 seconds.")


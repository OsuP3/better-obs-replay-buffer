import os
import sys
import time
import threading
import subprocess
import msvcrt
import atexit
import queue
import logging
import ctypes
from logging.handlers import RotatingFileHandler

# -------------------------------
# Set process name for Task Manager
# -------------------------------
PROCESS_NAME = "BetterReplayBuffer"
try:
    # This sets the App User Model ID which helps identify the process
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(PROCESS_NAME)
except:
    pass

# Set console title
try:
    ctypes.windll.kernel32.SetConsoleTitleW(PROCESS_NAME)
except:
    pass

# -------------------------------
# Logging (runs in background -> log file)
# -------------------------------
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "better-replay-buffer.log")
logger = logging.getLogger("better-replay-buffer")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Starting better-replay-buffer")

TEMP = os.getenv("TEMP") or os.getenv("TMP") or "."
lock_file_path = os.path.join(TEMP, "obs_toast.lock")
pid_file_path = os.path.join(TEMP, "obs_toast.pid")
refresh_file_path = os.path.join(TEMP, "obs_toast.refresh")

def _atomic_write(path: str, data: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)

# Try to lock. if already locked, request refresh and exit
try:
    lock_file = open(lock_file_path, "w")
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    _atomic_write(pid_file_path, str(os.getpid()))
except OSError:
    try:
        _atomic_write(refresh_file_path, f"{time.time()}:{os.getpid()}")
        logger.info("Refresh requested; exiting launcher")
    except Exception:
        pass
    sys.exit(0)

def _cleanup():
    try:
        lock_file.close()
    except Exception:
        pass
    try:
        if os.path.exists(pid_file_path):
            os.remove(pid_file_path)
    except Exception:
        pass
    try:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
    except Exception:
        pass
    logger.info("Exiting and cleaned up")

atexit.register(_cleanup)

# -------------------------------
# Auto-install dependencies
# -------------------------------
try:
    import keyboard
except ImportError:
    logger.info("Installing 'keyboard'...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard"])
    import keyboard

try:
    import tkinter as tk
except ImportError:
    logger.error("Tkinter not found. Make sure Python is installed with Tk support.")
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
        logger.error(f"{path} not found.")
        sys.exit(1)
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip().lower()] = value.strip().strip('"')
    return settings

settings = read_settings(SETTINGS_FILE)

# -------------------------------
# Configurable settings with defaults
# -------------------------------
keybind = settings.get("savereplaykeybind", "ctrl+shift+s")
sound_file = settings.get("savereplaysound")
sound_enabled = settings.get("sound", "no").lower() == "yes"
popup_enabled = settings.get("popup", "yes").lower() == "yes"
WATCH_DIR = settings.get("savereplaysdirectory")
OBS_EXE = settings.get("obs_exe_path", r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
OBS_ARGS = settings.get("obs_args", "--disable-crash-handler --disable-shutdown-check --startreplaybuffer --minimize-to-tray")
CHECK_TIME = int(settings.get("check_time", "30"))

# -------------------------------
# Validation
# -------------------------------
if not WATCH_DIR or not os.path.exists(WATCH_DIR):
    logger.error(f"Directory '{WATCH_DIR}' not found.")
    sys.exit(1)

if sound_enabled and (not sound_file or not os.path.exists(sound_file)):
    logger.warning(f"Sound file '{sound_file}' not found. Disabling sound.")
    sound_enabled = False

# Only start OBS if it's not already running and executable exists
if not os.path.exists(OBS_EXE):
    logger.warning(f"OBS executable not found at '{OBS_EXE}'. It will be skipped.")
    OBS_EXE = None
else:
    try:
        obs_name = os.path.basename(OBS_EXE).lower()
        proc_list = subprocess.check_output(["tasklist"], text=True, stderr=subprocess.DEVNULL).lower()
        if obs_name in proc_list:
            logger.info("OBS is already running; skipping launch.")
        else:
            subprocess.Popen(f'"{OBS_EXE}" {OBS_ARGS}', shell=True, cwd=os.path.dirname(OBS_EXE))
            logger.info("OBS started successfully.")
    except Exception:
        logger.exception("Failed to check/start OBS at startup")

toast_queue = queue.Queue()

def _create_toast(file_path, duration=5):
    toast = tk.Toplevel(tk_root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    try:
        toast.attributes("-alpha", 0.9)
    except Exception:
        pass

    width, height = 250, 60
    x = toast.winfo_screenwidth() - width - 10
    y = toast.winfo_screenheight() - height - 40
    toast.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(toast, bg="#333333")
    frame.pack(fill="both", expand=True)

    def open_file(event=None):
        try:
            os.startfile(file_path)
        except Exception:
            logger.exception("Failed to open file from toast")
        toast.destroy()

    label = tk.Label(frame, text=os.path.basename(file_path), bg="#333333", fg="white", font=("Segoe UI", 10))
    label.pack(pady=10, padx=10)

    frame.bind("<Button-1>", open_file)
    label.bind("<Button-1>", open_file)

    toast.after(duration * 1000, toast.destroy)

def poll_toast_queue():
    try:
        while True:
            file_path = toast_queue.get_nowait()
            _create_toast(file_path)
    except queue.Empty:
        pass
    tk_root.after(200, poll_toast_queue)

tk_root = tk.Tk()
tk_root.withdraw()
tk_root.after(200, poll_toast_queue)

# Refresh / settings reload
hotkey_id = None

def reload_settings():
    global settings, keybind, sound_file, sound_enabled, popup_enabled, WATCH_DIR, OBS_EXE, OBS_ARGS, CHECK_TIME, seen_files
    logger.info("Reloading settings")
    try:
        new = read_settings(SETTINGS_FILE)
    except Exception:
        logger.exception("Failed to read settings on refresh")
        return
    settings = new
    old_keybind = keybind
    old_watch = WATCH_DIR
    old_obs = OBS_EXE

    keybind = settings.get("savereplaykeybind", keybind)
    sound_file = settings.get("savereplaysound", sound_file)
    sound_enabled = settings.get("sound", "no").lower() == "yes"
    popup_enabled = settings.get("popup", "yes").lower() == "yes"
    WATCH_DIR = settings.get("savereplaysdirectory", WATCH_DIR)
    OBS_EXE = settings.get("obs_exe_path", OBS_EXE)
    OBS_ARGS = settings.get("obs_args", OBS_ARGS)
    try:
        CHECK_TIME = int(settings.get("check_time", str(CHECK_TIME)))
    except Exception:
        logger.warning("Invalid check_time; keeping previous")

    if WATCH_DIR != old_watch:
        if WATCH_DIR and os.path.exists(WATCH_DIR):
            seen_files = set(os.listdir(WATCH_DIR))
            logger.info(f"Watch dir changed to {WATCH_DIR}")
        else:
            logger.error(f"New watch dir invalid: {WATCH_DIR}; keeping {old_watch}")
            WATCH_DIR = old_watch

    if sound_enabled and (not sound_file or not os.path.exists(sound_file)):
        logger.warning("Sound file missing; disabling sound")
        sound_enabled = False

    if keybind != old_keybind:
        apply_hotkey()

    try:
        if OBS_EXE and os.path.exists(OBS_EXE):
            obs_name = os.path.basename(OBS_EXE).lower()
            proc_list = subprocess.check_output(["tasklist"], text=True, stderr=subprocess.DEVNULL).lower()
            if obs_name not in proc_list:
                subprocess.Popen(f'"{OBS_EXE}" {OBS_ARGS}', shell=True, cwd=os.path.dirname(OBS_EXE))
                logger.info("OBS started after refresh")
        else:
            logger.info("OBS path not valid after refresh")
    except Exception:
        logger.exception("OBS refresh check failed")

def poll_refresh():
    try:
        if os.path.exists(refresh_file_path):
            reload_settings()
            try:
                os.remove(refresh_file_path)
            except Exception:
                logger.exception("Failed removing refresh file")
    except Exception:
        logger.exception("Refresh poll error")
    finally:
        tk_root.after(1000, poll_refresh)

def apply_hotkey():
    global hotkey_id
    if hotkey_id is not None:
        try:
            keyboard.remove_hotkey(hotkey_id)
        except Exception:
            pass
    try:
        hotkey_id = keyboard.add_hotkey(keybind, hotkey_handler)
        logger.info(f"Active hotkey: {keybind}")
    except Exception:
        logger.exception("Failed to register hotkey")

tk_root.after(1000, poll_refresh)

# -------------------------------
# Monitor function
# -------------------------------
seen_files = set(os.listdir(WATCH_DIR))

def check_for_new_files():
    global seen_files
    logger.info("Checking for new files")
    start_time = time.time()
    while time.time() - start_time < CHECK_TIME:
        try:
            current_files = set(os.listdir(WATCH_DIR))
        except Exception:
            logger.exception("Failed to list watch directory")
            return
        new_files = current_files - seen_files
        for file in new_files:
            file_path = os.path.join(WATCH_DIR, file)
            logger.info(f"New file detected: {file_path}")
            # enqueue popup for main thread to show
            if popup_enabled:
                toast_queue.put(file_path)
            # Play sound (can be run from worker thread)
            if sound_enabled and winsound:
                threading.Thread(target=winsound.PlaySound, args=(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC), daemon=True).start()
        seen_files.update(new_files)
        time.sleep(0.5)
    logger.info("Finished checking for new files")

def hotkey_handler():
    threading.Thread(target=check_for_new_files, daemon=True).start()

apply_hotkey()
logger.info(f"Ready: hotkey {keybind} checks new files for {CHECK_TIME}s in '{WATCH_DIR}'")

# ensure keyboard.wait runs in background so main thread can run Tk
def keyboard_waiter():
    try:
        keyboard.wait()  # waits until program exit or keyboard interrupt
    except Exception:
        logger.exception("keyboard.wait ended unexpectedly")
    finally:
        try:
            tk_root.quit()
        finally:
            _cleanup()
            sys.exit(0)

threading.Thread(target=keyboard_waiter, daemon=True).start()

# Keep process alive and run the Tk event loop in the main thread (shows toasts)
try:
    logger.info("Entering Tk mainloop")
    tk_root.mainloop()
except KeyboardInterrupt:
    logger.info("KeyboardInterrupt received, exiting")
finally:
    _cleanup()
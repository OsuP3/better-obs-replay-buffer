"""
Better Replay Buffer - Background Service Module
Monitors for new replay files and shows notifications
"""

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

def run_service():
    """Main entry point for the background service"""
    
    # -------------------------------
    # PyInstaller support: determine base paths
    # -------------------------------
    if getattr(sys, 'frozen', False):
        EXE_DIR = os.path.dirname(sys.executable)
        BUNDLE_DIR = sys._MEIPASS
    else:
        EXE_DIR = os.path.dirname(os.path.abspath(__file__))
        BUNDLE_DIR = EXE_DIR

    # -------------------------------
    # Set process name for Task Manager
    # -------------------------------
    PROCESS_NAME = "BetterReplayBuffer"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(PROCESS_NAME)
    except:
        pass

    try:
        ctypes.windll.kernel32.SetConsoleTitleW(PROCESS_NAME)
    except:
        pass

    # -------------------------------
    # Logging
    # -------------------------------
    LOG_FILE = os.path.join(EXE_DIR, "better-replay-buffer.log")
    logger = logging.getLogger("better-replay-buffer")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Starting better-replay-buffer service")
    logger.info(f"EXE_DIR: {EXE_DIR}, BUNDLE_DIR: {BUNDLE_DIR}")

    TEMP = os.getenv("TEMP") or os.getenv("TMP") or "."
    lock_file_path = os.path.join(TEMP, "obs_toast.lock")
    pid_file_path = os.path.join(TEMP, "obs_toast.pid")
    refresh_file_path = os.path.join(TEMP, "obs_toast.refresh")

    def _atomic_write(path: str, data: str):
        """Write file atomically, with fallback to direct write"""
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, path)
        except:
            # Fallback: direct write
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)

    # Try to lock. if already locked, request refresh and exit
    try:
        lock_file = open(lock_file_path, "w")
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        try:
            _atomic_write(refresh_file_path, f"{time.time()}:{os.getpid()}")
            logger.info("Refresh requested; exiting launcher")
        except Exception:
            pass
        sys.exit(0)
    
    # Write PID file (separate try so lock success doesn't get undone)
    try:
        _atomic_write(pid_file_path, str(os.getpid()))
    except Exception as e:
        logger.error(f"Failed to write PID file: {e}")

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
    # Dependencies
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
        logger.error("Tkinter not found.")
        sys.exit(1)

    try:
        import winsound
    except ImportError:
        winsound = None

    # -------------------------------
    # Settings
    # -------------------------------
    SETTINGS_FILE = os.path.join(EXE_DIR, "settings.txt")

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

    # Sound file resolution
    sound_file_setting = settings.get("savereplaysound", "")
    if sound_file_setting:
        if os.path.isabs(sound_file_setting) and os.path.exists(sound_file_setting):
            sound_file = sound_file_setting
        elif os.path.exists(os.path.join(EXE_DIR, sound_file_setting)):
            sound_file = os.path.join(EXE_DIR, sound_file_setting)
        elif os.path.exists(os.path.join(BUNDLE_DIR, sound_file_setting)):
            sound_file = os.path.join(BUNDLE_DIR, sound_file_setting)
        elif os.path.exists(os.path.join(EXE_DIR, os.path.basename(sound_file_setting))):
            sound_file = os.path.join(EXE_DIR, os.path.basename(sound_file_setting))
        elif os.path.exists(os.path.join(BUNDLE_DIR, os.path.basename(sound_file_setting))):
            sound_file = os.path.join(BUNDLE_DIR, os.path.basename(sound_file_setting))
        else:
            sound_file = sound_file_setting
    else:
        if os.path.exists(os.path.join(EXE_DIR, "notification.wav")):
            sound_file = os.path.join(EXE_DIR, "notification.wav")
        else:
            sound_file = os.path.join(BUNDLE_DIR, "notification.wav")

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

    # Start OBS if configured
    if not os.path.exists(OBS_EXE):
        logger.warning(f"OBS executable not found at '{OBS_EXE}'. It will be skipped.")
        OBS_EXE = None
    else:
        def is_obs_running():
            """Check if OBS is running"""
            try:
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], 
                                       capture_output=True, text=True, timeout=5)
                if "obs64.exe" in result.stdout.lower():
                    return True
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs32.exe"], 
                                       capture_output=True, text=True, timeout=5)
                return "obs32.exe" in result.stdout.lower()
            except:
                return False
        
        # Wait a moment in case OBS is still starting up
        time.sleep(1)
        
        if is_obs_running():
            logger.info("OBS is already running; skipping launch.")
        else:
            try:
                subprocess.Popen(f'"{OBS_EXE}" {OBS_ARGS}', shell=True, cwd=os.path.dirname(OBS_EXE))
                logger.info("OBS started successfully.")
            except Exception:
                logger.exception("Failed to start OBS")

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
        nonlocal settings, keybind, sound_file, sound_enabled, popup_enabled, WATCH_DIR, OBS_EXE, OBS_ARGS, CHECK_TIME, seen_files
        logger.info("Reloading settings")
        try:
            new = read_settings(SETTINGS_FILE)
        except Exception:
            logger.exception("Failed to read settings on refresh")
            return
        settings = new
        old_keybind = keybind
        old_watch = WATCH_DIR

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
        nonlocal hotkey_id
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
        nonlocal seen_files
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
                if popup_enabled:
                    toast_queue.put(file_path)
                if sound_enabled and winsound:
                    threading.Thread(target=winsound.PlaySound, args=(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC), daemon=True).start()
            seen_files.update(new_files)
            time.sleep(0.5)
        logger.info("Finished checking for new files")

    def hotkey_handler():
        threading.Thread(target=check_for_new_files, daemon=True).start()

    apply_hotkey()
    logger.info(f"Ready: hotkey {keybind} checks new files for {CHECK_TIME}s in '{WATCH_DIR}'")

    def keyboard_waiter():
        try:
            keyboard.wait()
        except Exception:
            logger.exception("keyboard.wait ended unexpectedly")
        finally:
            try:
                tk_root.quit()
            finally:
                _cleanup()
                sys.exit(0)

    threading.Thread(target=keyboard_waiter, daemon=True).start()

    try:
        logger.info("Entering Tk mainloop")
        tk_root.mainloop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, exiting")
    finally:
        _cleanup()

if __name__ == "__main__":
    run_service()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.txt")
REPLAY_SCRIPT = os.path.join(SCRIPT_DIR, "better-replay-buffer.pyw")
TEMP = os.getenv("TEMP") or os.getenv("TMP") or "."
REFRESH_FILE = os.path.join(TEMP, "obs_toast.refresh")
PID_FILE = os.path.join(TEMP, "obs_toast.pid")

# Startup shortcut path
STARTUP_FOLDER = os.path.join(os.getenv("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup")
STARTUP_SHORTCUT = os.path.join(STARTUP_FOLDER, "BetterReplayBuffer.lnk")

def is_startup_enabled():
    """Check if the startup shortcut exists"""
    return os.path.exists(STARTUP_SHORTCUT)

def enable_startup():
    """Create a startup shortcut"""
    try:
        # Use PowerShell to create the shortcut
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable  # Fallback to python.exe
        
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{STARTUP_SHORTCUT}")
$Shortcut.TargetPath = "{pythonw}"
$Shortcut.Arguments = '"{REPLAY_SCRIPT}"'
$Shortcut.WorkingDirectory = "{SCRIPT_DIR}"
$Shortcut.Description = "Better Replay Buffer"
$Shortcut.Save()
'''
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to enable startup: {e}")
        return False

def disable_startup():
    """Remove the startup shortcut"""
    try:
        if os.path.exists(STARTUP_SHORTCUT):
            os.remove(STARTUP_SHORTCUT)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disable startup: {e}")
        return False

def toggle_startup():
    """Toggle the startup setting based on checkbox"""
    if startup_var.get():
        enable_startup()
    else:
        disable_startup()

# -------------------------------
# Settings functions
# -------------------------------
def read_settings():
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    value = value.strip()
                    # Strip only the outer quotes (first and last char if both are quotes)
                    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    settings[key.strip().lower()] = value
    return settings

def save_settings(settings_dict):
    with open(SETTINGS_FILE, "w") as f:
        for key, value in settings_dict.items():
            # Always wrap in quotes, preserving any internal quotes
            f.write(f'{key}="{value}"\n')

PROCESS_NAME = "BetterReplayBuffer"

def is_script_running():
    """Check if the replay buffer script is running by checking PID file"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # Quick check using tasklist with specific PID filter
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            text=True, stderr=subprocess.DEVNULL
        )
        # If process exists, output will contain the PID
        return str(pid) in output and "INFO:" not in output
    except:
        return False
    return False

def refresh_script():
    """Signal the running script to reload settings"""
    try:
        with open(REFRESH_FILE, "w") as f:
            f.write(f"{time.time()}:{os.getpid()}")
        update_status()
        save_status_label.config(text="✓ Refreshed!", fg="green")
        root.after(2000, lambda: save_status_label.config(text=""))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh: {e}")

def is_obs_running():
    """Check if OBS is running"""
    try:
        output = subprocess.check_output(["tasklist"], text=True, stderr=subprocess.DEVNULL).lower()
        return "obs64.exe" in output or "obs32.exe" in output
    except:
        return False

def start_obs(force=False):
    """Start OBS with configured settings"""
    settings = read_settings()
    obs_exe = settings.get("obs_exe_path", r"C:\Program Files\obs-studio\bin\64bit\obs64.exe")
    obs_args = settings.get("obs_args", "--startreplaybuffer --minimize-to-tray")
    
    if not os.path.exists(obs_exe):
        messagebox.showerror("Error", f"OBS not found at: {obs_exe}")
        return False
    
    if not force and is_obs_running():
        return True  # Already running
    
    try:
        subprocess.Popen(f'"{obs_exe}" {obs_args}', shell=True, cwd=os.path.dirname(obs_exe))
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start OBS: {e}")
        return False

def stop_obs():
    """Stop OBS"""
    try:
        subprocess.run(["taskkill", "/IM", "obs64.exe", "/F"], capture_output=True, text=True)
        subprocess.run(["taskkill", "/IM", "obs32.exe", "/F"], capture_output=True, text=True)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to stop OBS: {e}")
        return False

def restart_script():
    """Restart the replay buffer script (and optionally OBS)"""
    # Stop everything first
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
        except:
            pass
    
    if include_obs_var.get():
        stop_obs()
        time.sleep(1)  # Give OBS time to fully close
        start_obs(force=True)
        time.sleep(2)  # Give OBS time to start
    
    # Start the script
    if os.path.exists(REPLAY_SCRIPT):
        subprocess.Popen([sys.executable, REPLAY_SCRIPT], 
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    
    root.after(1000, update_status)
    msg = "✓ Restarted!"
    if include_obs_var.get():
        msg = "✓ OBS and script restarted!"
    save_status_label.config(text=msg, fg="green")
    root.after(2000, lambda: save_status_label.config(text=""))

def start_script():
    """Start the replay buffer script"""
    if os.path.exists(REPLAY_SCRIPT):
        # Optionally start OBS first
        if include_obs_var.get():
            start_obs()
        
        subprocess.Popen([sys.executable, REPLAY_SCRIPT], 
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        root.after(1000, update_status)  # Update status after a delay
        msg = "✓ Started!"
        if include_obs_var.get():
            msg += " (OBS included)"
        save_status_label.config(text=msg, fg="green")
        root.after(2000, lambda: save_status_label.config(text=""))
    else:
        messagebox.showerror("Error", f"Script not found: {REPLAY_SCRIPT}")

def stop_script():
    """Stop the replay buffer script"""
    stopped_script = False
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], 
                          capture_output=True, text=True)
            stopped_script = True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop script: {e}")
    
    # Optionally stop OBS
    if include_obs_var.get():
        stop_obs()
    
    root.after(500, update_status)
    if stopped_script or include_obs_var.get():
        msg = "✓ Stopped!"
        save_status_label.config(text=msg, fg="green")
        root.after(2000, lambda: save_status_label.config(text=""))
    else:
        messagebox.showwarning("Warning", "Script is not running.")

def update_status():
    if is_script_running():
        status_label.config(text="● Running", fg="green")
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")
        refresh_btn.config(state="normal")
    else:
        status_label.config(text="● Stopped", fg="red")
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
        refresh_btn.config(state="disabled")

def save_and_refresh():
    """Save settings to file and refresh the script only if script-related settings changed"""
    # Settings that affect the running script
    script_settings_keys = ["savereplaysound", "savereplaykeybind", "sound", "popup", 
                            "check_time", "savereplaysdirectory", "obs_exe_path", "obs_args"]
    
    # Get current saved settings for comparison
    old_settings = read_settings()
    
    new_settings = {
        "savereplaysound": savereplaysound_entry.get(),
        "savereplaykeybind": savereplaykeybind_entry.get(),
        "sound": sound_combo.get(),
        "popup": popup_combo.get(),
        "check_time": check_time_entry.get(),
        "savereplaysdirectory": savereplaysdirectory_entry.get(),
        "obs_exe_path": obs_exe_path_entry.get(),
        "obs_args": obs_args_entry.get(),
        "include_obs": "yes" if include_obs_var.get() else "no",
    }
    
    # Check if any script-related settings changed
    script_settings_changed = any(
        old_settings.get(key) != new_settings.get(key) 
        for key in script_settings_keys
    )
    
    save_settings(new_settings)
    
    # Handle startup setting - only change if different from current state
    startup_enabled = is_startup_enabled()
    if startup_var.get() and not startup_enabled:
        enable_startup()
    elif not startup_var.get() and startup_enabled:
        disable_startup()
    
    if is_script_running() and script_settings_changed:
        refresh_script()
    
    # Show saved status
    save_status_label.config(text="✓ Saved!", fg="green")
    root.after(2000, lambda: save_status_label.config(text=""))

# Load existing settings
current_settings = read_settings()

root = tk.Tk()
root.title("Replay Buffer Settings")
root.geometry("800x380")
root.resizable(True, True)

# Configure grid weights for root
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

# Title and status frame
header_frame = tk.Frame(root)
header_frame.grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="ew")
header_frame.grid_columnconfigure(0, weight=1)

title_label = tk.Label(header_frame, text="Settings", font=("Arial", 14, "bold"))
title_label.grid(row=0, column=0, pady=(0, 5))

# Status and control buttons
control_frame = tk.Frame(header_frame)
control_frame.grid(row=1, column=0)

status_label = tk.Label(control_frame, text="● Checking...", fg="gray")
status_label.grid(row=0, column=0, padx=5)

start_btn = tk.Button(control_frame, text="Start", command=start_script, width=8)
start_btn.grid(row=0, column=1, padx=2)

stop_btn = tk.Button(control_frame, text="Stop", command=stop_script, width=8)
stop_btn.grid(row=0, column=2, padx=2)

restart_btn = tk.Button(control_frame, text="Restart", command=restart_script, width=8)
restart_btn.grid(row=0, column=3, padx=2)

refresh_btn = tk.Button(control_frame, text="Refresh", command=refresh_script, width=8)
refresh_btn.grid(row=0, column=4, padx=2)

include_obs_var = tk.BooleanVar(value=current_settings.get("include_obs", "no").lower() == "yes")
include_obs_check = tk.Checkbutton(control_frame, text="Include OBS", variable=include_obs_var)
include_obs_check.grid(row=0, column=5, padx=(10, 5))

startup_var = tk.BooleanVar(value=is_startup_enabled())
startup_check = tk.Checkbutton(control_frame, text="Run on Startup", variable=startup_var)
startup_check.grid(row=0, column=6, padx=(5, 5))

# Create a frame for settings
frame = tk.Frame(root)
frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10)

# Configure frame column weights for elastic entries
frame.grid_columnconfigure(1, weight=1)

# Helper functions
def browse_file(entry, filetypes):
    filename = filedialog.askopenfilename(filetypes=filetypes)
    if filename:
        entry.delete(0, tk.END)
        entry.insert(0, filename)

def browse_folder(entry):
    folder = filedialog.askdirectory()
    if folder:
        entry.delete(0, tk.END)
        entry.insert(0, folder)

def capture_keybind(event, entry):
    keys = []
    if event.state & 0x4:  # Control
        keys.append("ctrl")
    if event.state & 0x1:  # Shift
        keys.append("shift")
    if event.state & 0x20000:  # Alt on Windows
        keys.append("alt")
    
    key = event.keysym.lower()
    if key not in ('control_l', 'control_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r'):
        keys.append(key)
        entry.delete(0, tk.END)
        entry.insert(0, "+".join(keys))
    return "break"

# Settings labels and entries
row = 0

# Save Replay Sound (file browser)
tk.Label(frame, text="Save Replay Sound:").grid(row=row, column=0, sticky="w", pady=2)
sound_frame = tk.Frame(frame)
sound_frame.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
sound_frame.grid_columnconfigure(0, weight=1)
savereplaysound_entry = tk.Entry(sound_frame)
savereplaysound_entry.insert(0, current_settings.get("savereplaysound", "notification.wav"))
savereplaysound_entry.grid(row=0, column=0, sticky="ew")
tk.Button(sound_frame, text="Browse...", command=lambda: browse_file(savereplaysound_entry, [("Audio Files", "*.wav *.mp3 *.ogg"), ("All Files", "*.*")])).grid(row=0, column=1, padx=(5, 0))
row += 1

# Save Replay Keybind (capture input)
tk.Label(frame, text="Save Replay Keybind:").grid(row=row, column=0, sticky="w", pady=2)
keybind_frame = tk.Frame(frame)
keybind_frame.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
keybind_frame.grid_columnconfigure(0, weight=1)
savereplaykeybind_entry = tk.Entry(keybind_frame)
savereplaykeybind_entry.insert(0, current_settings.get("savereplaykeybind", "ctrl+shift+s"))
savereplaykeybind_entry.grid(row=0, column=0, sticky="ew")
savereplaykeybind_entry.bind("<Key>", lambda e: capture_keybind(e, savereplaykeybind_entry))
tk.Label(keybind_frame, text="(Press keys)", fg="gray").grid(row=0, column=1, padx=(5, 0))
row += 1

# Sound (yes/no)
tk.Label(frame, text="Sound:").grid(row=row, column=0, sticky="w", pady=2)
sound_combo = ttk.Combobox(frame, values=["yes", "no"], state='readonly')
sound_combo.set(current_settings.get("sound", "no"))
sound_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
row += 1

# Popup (yes/no)
tk.Label(frame, text="Popup:").grid(row=row, column=0, sticky="w", pady=2)
popup_combo = ttk.Combobox(frame, values=["yes", "no"], state='readonly')
popup_combo.set(current_settings.get("popup", "yes"))
popup_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
row += 1

# Check Time
tk.Label(frame, text="Check Time (seconds):").grid(row=row, column=0, sticky="w", pady=2)
check_time_entry = tk.Entry(frame)
check_time_entry.insert(0, current_settings.get("check_time", "30"))
check_time_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
row += 1

# Save Replays Directory (folder browser)
tk.Label(frame, text="Save Replays Directory:").grid(row=row, column=0, sticky="w", pady=2)
dir_frame = tk.Frame(frame)
dir_frame.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
dir_frame.grid_columnconfigure(0, weight=1)
savereplaysdirectory_entry = tk.Entry(dir_frame)
savereplaysdirectory_entry.insert(0, current_settings.get("savereplaysdirectory", r"D:\Users\<YOUR USERNAME>\Videos\OBS"))
savereplaysdirectory_entry.grid(row=0, column=0, sticky="ew")
tk.Button(dir_frame, text="Browse...", command=lambda: browse_folder(savereplaysdirectory_entry)).grid(row=0, column=1, padx=(5, 0))
row += 1

# OBS Exe Path (file browser)
tk.Label(frame, text="OBS Exe Path:").grid(row=row, column=0, sticky="w", pady=2)
obs_frame = tk.Frame(frame)
obs_frame.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
obs_frame.grid_columnconfigure(0, weight=1)
obs_exe_path_entry = tk.Entry(obs_frame)
obs_exe_path_entry.insert(0, current_settings.get("obs_exe_path", r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"))
obs_exe_path_entry.grid(row=0, column=0, sticky="ew")
tk.Button(obs_frame, text="Browse...", command=lambda: browse_file(obs_exe_path_entry, [("Executable", "*.exe"), ("All Files", "*.*")])).grid(row=0, column=1, padx=(5, 0))
row += 1

# OBS Args
tk.Label(frame, text="OBS Args:").grid(row=row, column=0, sticky="w", pady=2)
obs_args_entry = tk.Entry(frame)
obs_args_entry.insert(0, current_settings.get("obs_args", "--disable-crash-handler --disable-shutdown-check --startreplaybuffer --minimize-to-tray"))
obs_args_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
row += 1

# Save button at the bottom
button_frame = tk.Frame(root)
button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 10))

save_status_label = tk.Label(button_frame, text="", fg="green")
save_status_label.pack()

save_btn = tk.Button(button_frame, text="Save Settings", command=save_and_refresh, width=15)
save_btn.pack()

# Update status on startup
root.after(100, update_status)

root.mainloop()
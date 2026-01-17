import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import subprocess
import time
import re
import configparser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.txt")
REPLAY_SCRIPT = os.path.join(SCRIPT_DIR, "better-replay-buffer.pyw")
TEMP = os.getenv("TEMP") or os.getenv("TMP") or "."
REFRESH_FILE = os.path.join(TEMP, "obs_toast.refresh")
PID_FILE = os.path.join(TEMP, "obs_toast.pid")
FIRST_RUN_FILE = os.path.join(SCRIPT_DIR, ".setup_done")

# -------------------------------
# Auto-detection functions (from setup.bat logic)
# -------------------------------
def auto_detect_settings():
    """Auto-detect OBS settings like the setup.bat does"""
    detected = {}
    
    appdata = os.getenv("APPDATA")
    if not appdata:
        return detected
    
    obs_root = os.path.join(appdata, "obs-studio")
    if not os.path.exists(obs_root):
        return detected
    
    # Read global.ini to get active profile
    global_ini = os.path.join(obs_root, "global.ini")
    profile_name = None
    
    if os.path.exists(global_ini):
        try:
            with open(global_ini, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("Profile="):
                        profile_name = line.split("=", 1)[1].strip()
                        break
        except:
            pass
    
    # Fallback: pick first profile folder
    if not profile_name:
        profiles_dir = os.path.join(obs_root, "basic", "profiles")
        if os.path.exists(profiles_dir):
            for d in os.listdir(profiles_dir):
                if os.path.isdir(os.path.join(profiles_dir, d)):
                    profile_name = d
                    break
    
    if not profile_name:
        return detected
    
    profile_ini = os.path.join(obs_root, "basic", "profiles", profile_name, "basic.ini")
    
    if os.path.exists(profile_ini):
        try:
            # Read recording path
            with open(profile_ini, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Try RecFilePath first (Advanced Output)
            match = re.search(r'^RecFilePath=(.+)$', content, re.MULTILINE)
            if not match:
                # Try FilePath (Simple Output)
                match = re.search(r'^FilePath=(.+)$', content, re.MULTILINE)
            
            if match:
                rec_path = match.group(1).strip().strip('"').replace("\\\\", "\\")
                if rec_path.endswith("\\"):
                    rec_path = rec_path[:-1]
                detected["savereplaysdirectory"] = rec_path
            
            # Try to extract hotkey
            hotkey_match = re.search(r'^ReplayBuffer=(.+)$', content, re.MULTILINE)
            if hotkey_match:
                hotkey_data = hotkey_match.group(1)
                parsed = parse_obs_hotkey(hotkey_data)
                if parsed:
                    detected["savereplaykeybind"] = parsed
        except:
            pass
    
    # Detect OBS executable
    obs_paths = [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
    ]
    for path in obs_paths:
        if os.path.exists(path):
            detected["obs_exe_path"] = path
            break
    
    return detected

def parse_obs_hotkey(hotkey_data):
    """Parse OBS hotkey JSON-like format to simple format"""
    parts = []
    
    # Check modifiers
    if re.search(r'shift.*true', hotkey_data, re.IGNORECASE):
        parts.append("shift")
    if re.search(r'control.*true', hotkey_data, re.IGNORECASE):
        parts.append("ctrl")
    if re.search(r'alt.*true', hotkey_data, re.IGNORECASE):
        parts.append("alt")
    
    # Extract key from OBS_KEY_X format
    key_match = re.search(r'OBS_KEY_(\w+)', hotkey_data)
    if key_match:
        key = key_match.group(1).lower()
        parts.append(key)
        return "+".join(parts)
    
    return None

def get_obs_scenes():
    """Get list of scenes from OBS scene collection"""
    scenes = []
    
    appdata = os.getenv("APPDATA")
    if not appdata:
        return scenes
    
    obs_root = os.path.join(appdata, "obs-studio")
    scenes_dir = os.path.join(obs_root, "basic", "scenes")
    
    if not os.path.exists(scenes_dir):
        return scenes
    
    # Find the active scene collection from global.ini
    global_ini = os.path.join(obs_root, "global.ini")
    scene_collection = None
    
    if os.path.exists(global_ini):
        try:
            with open(global_ini, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("SceneCollection="):
                        scene_collection = line.split("=", 1)[1].strip()
                        break
        except:
            pass
    
    # Find the scene collection JSON file
    scene_file = None
    if scene_collection:
        scene_file = os.path.join(scenes_dir, f"{scene_collection}.json")
    
    if not scene_file or not os.path.exists(scene_file):
        # Fallback: use first .json file
        for f in os.listdir(scenes_dir):
            if f.endswith(".json"):
                scene_file = os.path.join(scenes_dir, f)
                break
    
    if scene_file and os.path.exists(scene_file):
        try:
            import json
            with open(scene_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Extract scene names
            if "sources" in data:
                for source in data["sources"]:
                    if source.get("id") == "scene" or source.get("versioned_id", "").startswith("scene"):
                        name = source.get("name")
                        if name:
                            scenes.append(name)
        except:
            pass
    
    return scenes

def get_scene_from_args(args):
    """Extract --scene value from obs args"""
    match = re.search(r'--scene\s+"([^"]+)"', args)
    if match:
        return match.group(1)
    match = re.search(r'--scene\s+(\S+)', args)
    if match:
        return match.group(1)
    return None

def set_scene_in_args(args, scene):
    """Set or remove --scene in obs args"""
    # Remove existing --scene argument
    args = re.sub(r'\s*--scene\s+"[^"]+"', '', args)
    args = re.sub(r'\s*--scene\s+\S+', '', args)
    args = args.strip()
    
    if scene and scene != "(None)":
        args = f'{args} --scene "{scene}"'
    
    return args

def run_auto_setup():
    """Run auto-detection and update settings"""
    detected = auto_detect_settings()
    
    if not detected:
        messagebox.showwarning("Auto-Setup", "Could not auto-detect OBS settings.\nPlease configure manually.")
        return False
    
    # Update the entry fields with detected values
    changes = []
    
    if "savereplaysdirectory" in detected:
        savereplaysdirectory_entry.delete(0, tk.END)
        savereplaysdirectory_entry.insert(0, detected["savereplaysdirectory"])
        changes.append(f"Replay Directory: {detected['savereplaysdirectory']}")
    
    if "savereplaykeybind" in detected:
        savereplaykeybind_entry.delete(0, tk.END)
        savereplaykeybind_entry.insert(0, detected["savereplaykeybind"])
        changes.append(f"Hotkey: {detected['savereplaykeybind']}")
    
    if "obs_exe_path" in detected:
        obs_exe_path_entry.delete(0, tk.END)
        obs_exe_path_entry.insert(0, detected["obs_exe_path"])
        changes.append(f"OBS Path: {detected['obs_exe_path']}")
    
    if changes:
        save_status_label.config(text="✓ Auto-detected: " + ", ".join(changes[:2]), fg="green")
        root.after(4000, lambda: save_status_label.config(text=""))
        return True
    else:
        messagebox.showwarning("Auto-Setup", "No settings could be auto-detected.")
        return False

def check_first_run():
    """Check if this is the first run and offer auto-setup"""
    if not os.path.exists(SETTINGS_FILE) or not os.path.exists(FIRST_RUN_FILE):
        result = messagebox.askyesno(
            "First Time Setup",
            "Would you like to auto-detect settings from OBS?\n\n"
            "This will try to find:\n"
            "• Your replay buffer save directory\n"
            "• Your replay buffer hotkey\n"
            "• OBS installation path\n\n"
            "You can also run this later from the 'Auto-Setup' button."
        )
        
        # Mark setup as done
        try:
            with open(FIRST_RUN_FILE, "w") as f:
                f.write("1")
        except:
            pass
        
        if result:
            # Delay to let the main window render first
            root.after(100, run_auto_setup)

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
    
    # Handle scene selection - update obs_args with scene
    obs_args = obs_args_entry.get()
    selected_scene = scene_combo.get()
    obs_args = set_scene_in_args(obs_args, selected_scene)
    
    new_settings = {
        "savereplaysound": savereplaysound_entry.get(),
        "savereplaykeybind": savereplaykeybind_entry.get(),
        "sound": sound_combo.get(),
        "popup": popup_combo.get(),
        "check_time": check_time_entry.get(),
        "savereplaysdirectory": savereplaysdirectory_entry.get(),
        "obs_exe_path": obs_exe_path_entry.get(),
        "obs_args": obs_args,
        "include_obs": "yes" if include_obs_var.get() else "no",
    }
    
    # Also update the entry field to show the scene argument
    obs_args_entry.delete(0, tk.END)
    obs_args_entry.insert(0, obs_args)
    
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

# OBS Scene selector
tk.Label(frame, text="Start Scene:").grid(row=row, column=0, sticky="w", pady=2)
scene_frame = tk.Frame(frame)
scene_frame.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
scene_frame.grid_columnconfigure(0, weight=1)

obs_scenes = get_obs_scenes()
current_scene = get_scene_from_args(current_settings.get("obs_args", ""))
scene_choices = ["(None)"] + obs_scenes

scene_combo = ttk.Combobox(scene_frame, values=scene_choices, state='readonly')
if current_scene and current_scene in obs_scenes:
    scene_combo.set(current_scene)
else:
    scene_combo.set("(None)")
scene_combo.grid(row=0, column=0, sticky="ew")

def refresh_scenes():
    """Refresh the scene list from OBS"""
    scenes = get_obs_scenes()
    scene_choices = ["(None)"] + scenes
    scene_combo['values'] = scene_choices
    save_status_label.config(text=f"✓ Found {len(scenes)} scenes", fg="green")
    root.after(2000, lambda: save_status_label.config(text=""))

tk.Button(scene_frame, text="Refresh", command=refresh_scenes, width=8).grid(row=0, column=1, padx=(5, 0))
row += 1

# Save button at the bottom
button_frame = tk.Frame(root)
button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 10))

save_status_label = tk.Label(button_frame, text="", fg="green")
save_status_label.pack()

buttons_row = tk.Frame(button_frame)
buttons_row.pack()

auto_setup_btn = tk.Button(buttons_row, text="Auto-Setup", command=run_auto_setup, width=12)
auto_setup_btn.pack(side=tk.LEFT, padx=5)

save_btn = tk.Button(buttons_row, text="Save Settings", command=save_and_refresh, width=15)
save_btn.pack(side=tk.LEFT, padx=5)

# Check for first run after window is ready
root.after(200, check_first_run)

# Update status on startup
root.after(100, update_status)

root.mainloop()
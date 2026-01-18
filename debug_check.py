import ctypes
import os

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', ctypes.c_ulong),
        ('cntUsage', ctypes.c_ulong),
        ('th32ProcessID', ctypes.c_ulong),
        ('th32DefaultHeapID', ctypes.c_void_p),
        ('th32ModuleID', ctypes.c_ulong),
        ('cntThreads', ctypes.c_ulong),
        ('th32ParentProcessID', ctypes.c_ulong),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', ctypes.c_ulong),
        ('szExeFile', ctypes.c_char * 260),
    ]

def get_running_processes():
    processes = {}
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return processes
    
    pe32 = PROCESSENTRY32()
    pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
    
    if kernel32.Process32First(snapshot, ctypes.byref(pe32)):
        while True:
            try:
                name = pe32.szExeFile.decode('utf-8', errors='ignore').lower()
                pid = pe32.th32ProcessID
                if name not in processes:
                    processes[name] = []
                processes[name].append(pid)
            except:
                pass
            if not kernel32.Process32Next(snapshot, ctypes.byref(pe32)):
                break
    
    kernel32.CloseHandle(snapshot)
    return processes

procs = get_running_processes()
print("=== All processes with 'better' in name ===")
for name, pids in procs.items():
    if 'better' in name.lower():
        print(f"  {repr(name)}: {pids}")

print("\n=== PID file check ===")
pid_file = os.path.join(os.getenv('TEMP'), 'obs_toast.pid')
print(f"PID file path: {pid_file}")
print(f"PID file exists: {os.path.exists(pid_file)}")

if os.path.exists(pid_file):
    with open(pid_file) as f:
        content = f.read()
        print(f"PID file raw content: {repr(content)}")
        pid = int(content.strip())
    print(f"PID from file: {pid}")
    
    exe_name = "betterreplaybuffer.exe"
    our_pids = procs.get(exe_name, [])
    print(f"PIDs for '{exe_name}': {our_pids}")
    print(f"PID {pid} in list: {pid in our_pids}")

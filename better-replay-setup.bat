@echo off
setlocal EnableDelayedExpansion

echo ==============================================
echo  Better OBS Replay Buffer - Setup Generator
echo ==============================================
echo.

REM Check Python installation and version
:check_python
echo Checking Python installation...
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    echo Press any key after installing Python to continue...
    pause >NUL
    goto check_python
)

REM Get Python version
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo Found Python version: %PYTHON_VERSION%

REM Get Python executable location
for /f "tokens=*" %%p in ('where python 2^>NUL') do set PYTHON_EXE=%%p
if defined PYTHON_EXE (
    echo Python executable: %PYTHON_EXE%
) else (
    echo Python executable location: Not found in PATH
)

REM Check if it's 3.11 (recommended)
echo %PYTHON_VERSION% | findstr /r "^3\.11\." >NUL
if %ERRORLEVEL% EQU 0 (
    echo Python 3.11 detected - excellent!
) else (
    echo %PYTHON_VERSION% | findstr /r "^3\." >NUL
    if %ERRORLEVEL% EQU 0 (
        echo WARNING: Python 3.11 is recommended, but %PYTHON_VERSION% should work.
        echo If you encounter issues, consider upgrading to Python 3.11.
        echo Download from: https://www.python.org/downloads/release/python-3119/
        echo.
    ) else (
        echo ERROR: Python 2.x detected. Python 3.x is required.
        echo Please install Python 3.11 from: https://www.python.org/downloads/
        echo.
        echo Press any key after installing Python 3.x to continue...
        pause >NUL
        goto check_python
    )
)
echo.

REM Determine script directory (repository root)
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%" >NUL 2>&1

REM Target settings file
set SETTINGS_FILE=settings.txt

REM OBS config root
if not defined APPDATA (
	echo ERROR: APPDATA environment variable not found.
	goto :write_settings
)
set OBS_ROOT=%APPDATA%\obs-studio
if not exist "%OBS_ROOT%" (
	echo WARN: OBS configuration directory not found at "%OBS_ROOT%".
	echo      Will fall back to defaults.
	goto :write_settings
)

set GLOBAL_INI=%OBS_ROOT%\global.ini
if not exist "%GLOBAL_INI%" (
	echo WARN: global.ini not found; using defaults.
	goto :write_settings
)

echo Reading OBS global.ini for active Profile ...
set LAST_PROFILE=
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^Profile=" "%GLOBAL_INI%"`) do (
	set LAST_PROFILE=%%B
)

if "!LAST_PROFILE!"=="" (
	echo WARN: Profile not found; picking first profile folder.
	for /d %%D in ("%OBS_ROOT%\basic\profiles\*") do (
		if "!LAST_PROFILE!"=="" set LAST_PROFILE=%%~nxD
	)
)

if "!LAST_PROFILE!"=="" (
	echo WARN: No profiles detected; using defaults.
	goto :extract_hotkey
)

echo Detected profile: !LAST_PROFILE!
set PROFILE_INI=%OBS_ROOT%\basic\profiles\!LAST_PROFILE!\basic.ini
if not exist "!PROFILE_INI!" (
	echo WARN: Profile INI not found at !PROFILE_INI!; using defaults for directory.
	goto :extract_hotkey
)

REM Attempt to read recording path (AdvOut takes priority over SimpleOutput)
set REC_PATH=
REM Try AdvOut RecFilePath first (more commonly used)
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^RecFilePath=" "!PROFILE_INI!"`) do (
	set REC_PATH=%%B
)
REM If not found, try SimpleOutput FilePath
if not defined REC_PATH (
	for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^FilePath=" "!PROFILE_INI!"`) do (
		set REC_PATH=%%B
	)
)

REM Use recording path for replay buffer saves
if defined REC_PATH (
	REM Strip surrounding quotes if any
	set REC_PATH=!REC_PATH:"=!
	REM Convert double backslashes to single
	set REC_PATH=!REC_PATH:\\=\!
	REM Remove trailing backslash if present
	if "!REC_PATH:~-1!"=="\" set REC_PATH=!REC_PATH:~0,-1!
	REM Trim whitespace
	for /f "tokens=* delims= " %%P in ("!REC_PATH!") do set REC_PATH=%%P
	
	set REPLAY_PATH=!REC_PATH!
	echo Found recording path from profile: !REC_PATH!
	echo Using recording path for replay buffer: !REPLAY_PATH!
) else (
	echo WARN: No recording path found; will use fallback.
)

echo.

:extract_hotkey
echo Extracting ReplayBuffer hotkey ...
set SAVE_HOTKEY=
REM Look for hotkey in profile config, not global.ini
if exist "!PROFILE_INI!" (
	for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /r "^ReplayBuffer=" "!PROFILE_INI!"`) do (
		set SAVE_HOTKEY=%%B
	)
) else (
	echo WARN: Profile INI not found for hotkey extraction.
)

if defined SAVE_HOTKEY (
	echo Raw hotkey data: !SAVE_HOTKEY!
	REM Parse JSON-like hotkey format to simple format
	set PARSED_HOTKEY=
	
	REM Check for shift modifier
	echo !SAVE_HOTKEY! | findstr /i "shift.*true" >NUL && set PARSED_HOTKEY=shift+
	
	REM Check for control modifier  
	echo !SAVE_HOTKEY! | findstr /i "control.*true" >NUL && set PARSED_HOTKEY=!PARSED_HOTKEY!ctrl+
	
	REM Check for alt modifier
	echo !SAVE_HOTKEY! | findstr /i "alt.*true" >NUL && set PARSED_HOTKEY=!PARSED_HOTKEY!alt+
	
	REM Extract key from OBS_KEY_X format - simpler approach
	echo !SAVE_HOTKEY! | findstr /r "OBS_KEY_" >NUL
	if !ERRORLEVEL! EQU 0 (
		REM Extract just the letter after OBS_KEY_
		set TEMP_KEY=!SAVE_HOTKEY:*OBS_KEY_=!
		for /f "tokens=1 delims=}" %%K in ("!TEMP_KEY!") do (
			set KEY_PART=%%K
			set KEY_PART=!KEY_PART:"=!
			REM Convert to lowercase
			if /i "!KEY_PART!"=="S" set KEY_PART=s
			if /i "!KEY_PART!"=="A" set KEY_PART=a
			if /i "!KEY_PART!"=="B" set KEY_PART=b
			if /i "!KEY_PART!"=="C" set KEY_PART=c
			if /i "!KEY_PART!"=="D" set KEY_PART=d
			if /i "!KEY_PART!"=="E" set KEY_PART=e
			if /i "!KEY_PART!"=="F" set KEY_PART=f
			if /i "!KEY_PART!"=="G" set KEY_PART=g
			if /i "!KEY_PART!"=="H" set KEY_PART=h
			if /i "!KEY_PART!"=="I" set KEY_PART=i
			if /i "!KEY_PART!"=="J" set KEY_PART=j
			if /i "!KEY_PART!"=="K" set KEY_PART=k
			if /i "!KEY_PART!"=="L" set KEY_PART=l
			if /i "!KEY_PART!"=="M" set KEY_PART=m
			if /i "!KEY_PART!"=="N" set KEY_PART=n
			if /i "!KEY_PART!"=="O" set KEY_PART=o
			if /i "!KEY_PART!"=="P" set KEY_PART=p
			if /i "!KEY_PART!"=="Q" set KEY_PART=q
			if /i "!KEY_PART!"=="R" set KEY_PART=r
			if /i "!KEY_PART!"=="T" set KEY_PART=t
			if /i "!KEY_PART!"=="U" set KEY_PART=u
			if /i "!KEY_PART!"=="V" set KEY_PART=v
			if /i "!KEY_PART!"=="W" set KEY_PART=w
			if /i "!KEY_PART!"=="X" set KEY_PART=x
			if /i "!KEY_PART!"=="Y" set KEY_PART=y
			if /i "!KEY_PART!"=="Z" set KEY_PART=z
			set PARSED_HOTKEY=!PARSED_HOTKEY!!KEY_PART!
		)
	)
	
	if defined PARSED_HOTKEY (
		set SAVE_HOTKEY=!PARSED_HOTKEY!
		echo Parsed hotkey: !SAVE_HOTKEY!
	) else (
		echo WARN: Could not parse hotkey format; using default.
		set SAVE_HOTKEY=
	)
) else (
	echo WARN: ReplayBuffer hotkey not found; default will be used.
)

echo.

REM Detect OBS executable path and check version
set OBS_EXE_PATH=
if exist "C:\Program Files\obs-studio\bin\64bit\obs64.exe" set OBS_EXE_PATH=C:\Program Files\obs-studio\bin\64bit\obs64.exe
if exist "C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe" set OBS_EXE_PATH=C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe
if defined OBS_EXE_PATH (
	echo Detected OBS executable: !OBS_EXE_PATH!
	
	REM Check OBS version from file properties
	echo Checking OBS version...
	set OBS_MAJOR=
	
	REM Try to get version from file properties using PowerShell
	for /f "tokens=*" %%v in ('powershell -Command "(Get-ItemProperty \"!OBS_EXE_PATH!\").VersionInfo.ProductVersion" 2^>NUL') do (
		set OBS_VERSION=%%v
	)
	
	if defined OBS_VERSION (
		REM Extract major version number
		for /f "tokens=1 delims=." %%m in ("!OBS_VERSION!") do set OBS_MAJOR=%%m
		echo Found OBS version: !OBS_VERSION!
	) else (
		REM Fallback: try to extract from executable metadata
		for /f "tokens=*" %%v in ('powershell -Command "$file = Get-Item \"!OBS_EXE_PATH!\"; $file.VersionInfo.FileVersion" 2^>NUL') do (
			set OBS_VERSION=%%v
			for /f "tokens=1 delims=." %%m in ("%%v") do set OBS_MAJOR=%%m
		)
		if defined OBS_VERSION (
			echo Found OBS version: !OBS_VERSION!
		)
	)
	
	if defined OBS_MAJOR (
		echo Found OBS version: !OBS_MAJOR!.x
		if !OBS_MAJOR! LSS 31 (
			echo.
			echo $$$$$$ WARNING: OBS Studio !OBS_MAJOR!.x detected.
			echo   For best compatibility, consider upgrading to OBS Studio 31.x
			echo   Download: https://github.com/obsproject/obs-studio/releases/tag/31.0.0
			echo.
		) else if !OBS_MAJOR! GEQ 32 (
			echo.
			echo $$$$$ CRITICAL WARNING $$$$$
			echo   OBS Studio !OBS_MAJOR!.x may have compatibility issues!
			echo   This tool was designed for OBS Studio 31 and earlier.
			echo   
			echo   RECOMMENDED: Downgrade to OBS Studio 31.x for guaranteed compatibility
			echo   Download OBS 31: https://github.com/obsproject/obs-studio/releases/tag/31.0.0
			echo.
			echo   Press any key to continue at your own risk...
			pause >NUL
		) else (
			echo OBS Studio !OBS_MAJOR!.x - Perfect compatibility!
		)
	) else (
		echo WARN: Could not determine OBS version.
	)
) else (
	echo INFO: OBS executable not auto-detected; using script default.
)

REM Fallbacks
if not defined REC_PATH set REC_PATH=%USERPROFILE%\Videos
if not exist "!REC_PATH!" (
	echo INFO: Creating recording directory: !REC_PATH!
	mkdir "!REC_PATH!" >NUL 2>&1
)
if not defined SAVE_HOTKEY set SAVE_HOTKEY=ctrl+shift+s
if not defined REPLAY_PATH set REPLAY_PATH=!REC_PATH!
if not exist "!REPLAY_PATH!" (
    echo INFO: Creating replay buffer directory: !REPLAY_PATH!
    mkdir "!REPLAY_PATH!" >NUL 2>&1
)


:write_settings
ECHO.
echo Writing settings to %SETTINGS_FILE% ...
(
    echo savereplaysound="notification.wav"
	echo savereplaykeybind="!SAVE_HOTKEY!"
    echo.
	echo sound=no
	echo popup=yes
	echo check_time=30
    echo.
    echo savereplaysdirectory="!REPLAY_PATH!"
	echo.
    if defined OBS_EXE_PATH echo obs_exe_path="!OBS_EXE_PATH!"
	echo obs_args=--disable-crash-handler --disable-shutdown-check --startreplaybuffer --minimize-to-tray
) > "%SETTINGS_FILE%"

if exist "%SETTINGS_FILE%" (
	echo SUCCESS: settings.txt generated.
) else (
	echo ERROR: Failed to create settings.txt
	exit /b 1
)


REM Check for existing startup shortcut that points to our script
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SCRIPT_TARGET=!SCRIPT_DIR!better-replay-buffer.pyw
set SHORTCUT_EXISTS=false

echo.
echo Checking for existing startup shortcuts...

REM Check all .lnk files in startup folder for our script
for %%f in ("!STARTUP_FOLDER!\*.lnk") do (
	REM Create temp PowerShell script to check shortcut target
	set PS_CHECK=!TEMP!\check_shortcut.ps1
	(
		echo $WshShell = New-Object -comObject WScript.Shell
		echo $Shortcut = $WshShell.CreateShortcut^("%%f"^)
		echo $TargetPath = $Shortcut.TargetPath
		echo $Arguments = $Shortcut.Arguments
		echo $FullCommand = "$TargetPath $Arguments"
		echo if ^($FullCommand -like "*better-replay-buffer.pyw*"^) { 
		echo     Write-Host "FOUND"
		echo } elseif ^($TargetPath -like "*better-replay-buffer.pyw*"^) {
		echo     Write-Host "FOUND" 
		echo }
	) > "!PS_CHECK!"
	
	REM Run check and capture output
	for /f "tokens=*" %%r in ('powershell -ExecutionPolicy Bypass -File "!PS_CHECK!" 2^>NUL') do (
		if "%%r"=="FOUND" (
			set SHORTCUT_EXISTS=true
			echo Found existing shortcut: %%~nxf
		)
	)
	del "!PS_CHECK!" >NUL 2>&1
)

if "!SHORTCUT_EXISTS!"=="true" (
	echo Startup shortcut for replay buffer already exists - skipping creation.
	goto script_end
)

echo Would you like to create a startup shortcut so the replay buffer
echo automatically starts when Windows boots? (y/n)
set /p CREATE_STARTUP="Enter choice: "
if /i "!CREATE_STARTUP!"=="y" (
	echo Creating startup shortcut...
	goto create_shortcut
) else (
	echo Skipped startup shortcut creation.
	echo You can run 'better-replay-buffer.pyw' manually when needed.
	if defined PYTHON_EXE (
		echo Alternative: If .pyw files don't open correctly, use:
		echo   "%PYTHON_EXE%" "!SCRIPT_DIR!better-replay-buffer.pyw"
	)
	goto script_end
)

:create_shortcut
	set SHORTCUT_PATH=!STARTUP_FOLDER!\Better OBS Replay Buffer.lnk
	REM Create PowerShell script to make a proper Windows shortcut
	set PS_SCRIPT=!TEMP!\create_shortcut.ps1
	(
		echo $WshShell = New-Object -comObject WScript.Shell
		echo $Shortcut = $WshShell.CreateShortcut^("!SHORTCUT_PATH!"^)
		echo $Shortcut.TargetPath = "pythonw.exe"
		echo $Shortcut.Arguments = """!SCRIPT_DIR!better-replay-buffer.pyw"""
		echo $Shortcut.WorkingDirectory = "!SCRIPT_DIR!"
		echo $Shortcut.WindowStyle = 7
		echo $Shortcut.Description = "Better OBS Replay Buffer - Auto notification for saved replays"
		echo $Shortcut.Save^(^)
	) > "!PS_SCRIPT!"
	
	REM Execute PowerShell script
	powershell -ExecutionPolicy Bypass -File "!PS_SCRIPT!" >NUL 2>&1
	
	REM Clean up temp script
	del "!PS_SCRIPT!" >NUL 2>&1
	
	if exist "!SHORTCUT_PATH!" (
		echo Startup shortcut created successfully!
		echo The replay buffer will now start automatically on boot.
	) else (
		echo Failed to create startup shortcut.
	)

:script_end
popd >NUL 2>&1
echo.
echo Setup complete! 
echo Start better-replay-buffer.pyw and you should be set! 
echo Make sure you're executing with pythonw.exe (make sure theres the w after python)
exit /b 0

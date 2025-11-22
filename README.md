I was tired of some issues with other instant replay software so I added a script to add some features to OBS replay buffer.
This includes: Notification noise and/or Notification popup on replay save. You can also click the popup to instantly play the clip. I also wanted this to open automatically on login so the script also opens OBS with replay buffer and ignore shutdown warning. To automatically run the script on startup, create a shortcut of the pyw file and place it in the "shell:startup" directory. The pyw file should execute with pythonw.exe so it can run in the background.

Only works with OBS Version <32.0.0 as a necessary tag was removed. please use OBS 31.1.2.
Works with Python 3.11, there are two automatic package downloads.

There is a setup script to automatically fetch your settings, but you can use the settings.example.txt to create them manually, you just need to remove the .example after you're done.

You can set your preferences in the settings.txt file.


# Utility functions

## Build USB Stick

**Recommendations**:

- Try using USB 3.0 usb stick, the process will take about 30 minutes per stick compared to 1.5hrs with USB 2.0 ones.

**Requirements**:

- The custom AWS DeepRacer Ubuntu ISO image `ubuntu-20.04.1-20.11.13_V1-desktop-amd64.iso` in the same directory (will be downloaded if missing)
- The latest AWS DeepRacer software update package `factory_reset.zip` **unzipped** in the same directory (will be downloaded and unzipped if missing)

Both files can be downloaded from here https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-ubuntu-update.html (under the "Prerequisites" heading).

### OSX version

**Requirements**:

- https://unetbootin.github.io/ installed

**Command**:

```
./usb-build.sh -d disk2 -s <WIFI_SSID> -w <WIFI_PASSWORD>
```

**Note:**

- The wifi credentials are used to create `wifi-creds.txt` on the `DEEPRACER` partition, upon rebooting after flashing the car will use this file to connect to wifi
- Tested and working on Intel and Apple based Macs
- Unetbootin currently doesn't work on OSX Ventura [#Issue 337](https://github.com/unetbootin/unetbootin/issues/337)

### Ubuntu version

**Requirements**:

- Requires sudo privileges
- Will add current user to sudoer automatically (with the "no password" option enabled)

**Command**:

```
./usb-build.ubuntu.sh -d sdX -s <WIFI_SSID> -W <WIFI_PASSWORD>
```

**Note:**

- The wifi credentials are used to create `wifi-creds.txt` on the `DEEPRACER` partition, upon rebooting after flashing the car will use this file to connect to wifi
- Tested and working on Ubuntu 20.0.4 (like a DeepRacer car)

### Windows PowerShell version

**Requirements**:

- Run in PowerShell command window (**NOT** run as Administrator, but you will be prompted to elevate with Administrator at some point in the script=

**Command**:

```
start powershell {.\usb-build.ps1 -DiskId <disk number>}
```

Additional switches:

Description                                                    | Switch
---------------------------------------------------------------|---------------------------------------------------
Provide Wifi Credentials                                       | `-SSID <WIFI_SSID> -SSIDPassword <WIFI_PASSWORD>`
Create partitions (default value is True)                      | `-CreatePartition <True/False>`
Ignore lock files (default value is False)                     | `-IgnoreLock <True/False>`
Ignore Factory Reset content creation (default value is False) | `-IgnoreFactoryReset <True/False>`
Ignore Boot Drive creation (default value is False)            | `-IgnoreBootDrive <True/False>`

**Note:**

- The wifi credentials are used to create `wifi-creds.txt` on the `DEEPRACER` partition, upon rebooting after flashing the car will use this file to connect to wifi
- Tested and working on Windows 11 Pro

## reset-usb.sh

Needs to be run on the car to reset USB in the event of a failure of the front USB hub, faster than a full reboot of the car - works ~70% of the time YMMV
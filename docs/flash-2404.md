# Flashing a DeepRacer from Ubuntu 20.04 to 24.04

This guide explains how to upgrade an original AWS DeepRacer from its stock
Ubuntu 20.04 / ROS 2 Foxy installation to Ubuntu 24.04 (Noble) / ROS 2 Jazzy
using a community-built custom flash image.

## Overview

The original AWS process flashes the car's internal eMMC using a bootable USB
drive containing:

- The AWS-supplied Ubuntu 20.04 live ISO (used to boot the car into the
  installer environment)
- A `factory_reset.zip` archive with the disk image and flash scripts

This guide follows the same mechanical procedure but substitutes the
`factory_reset.zip` with a community-built Ubuntu 24.04 image archive. The
`-r` flag on all `usb-build*` scripts accepts a custom archive URL, so no
manual USB preparation steps are required.

## Developer Mode

AWS DeepRacer devices ship with secure firmware that only allows AWS-signed
operating systems. The custom Ubuntu 24.04 image boots using a modified UEFI
bootloader — a **developer shim** (based on the open-source shim project from
Red Hat) — that enables self-service developer access. Without this shim, the
car would refuse to boot any non-AWS-signed OS.

### What to expect at every boot

Whenever the developer shim is active, the car provides clear visual
indication:

- **On-screen warning** displayed over HDMI informing you that developer mode
  is active
- **Morse code LED sequence** — the car's lights blink "DEVELOPER" in Morse
  code (approximately 21 seconds)
- **Boot delay** to ensure the warning cannot be missed

This is by design: the system maintains transparency so that users always
understand their device's security posture.

### Reversibility

Developer mode is fully reversible. To return the car to the original
AWS-signed configuration, follow the standard
[DeepRacer device reinstallation](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-ubuntu-update.html)
procedure — no hardware modifications are required.

## What the custom image includes

The community image (`custom_factory_reset.zip`) differs from the standard AWS
factory-reset archive in the following ways:

- **Ubuntu 24.04 LTS (Noble Numbat)** instead of 20.04
- **ROS 2 Jazzy** (`ros-jazzy-ros-core`) and all DeepRacer dependencies
- **OpenVINO 2024.6** and **TensorFlow 2.17** pre-installed
- Full DeepRacer software stack:
  - `aws-deepracer-core`
  - `aws-deepracer-community-device-console`
  - `aws-deepracer-util`
  - `aws-deepracer-sample-models`
- System hardening:
  - WiFi power-save disabled
  - Audio drivers blacklisted
  - Firewall enabled (SSH allowed)
  - Hostname set to `deepracer`

The image is self-contained — no additional software installation is required
after flashing.

## Prerequisites

| Requirement | Detail |
|---|---|
| USB drive | ≥ 32 GB |
| Host PC | Ubuntu/Linux, macOS, or Windows with PowerShell |
| Network | Required to download the ISO and custom image (~2–3 GB total) |
| DeepRacer | Running stock Ubuntu 20.04 (any software version) |
| `sudo` / admin rights | Required on the host PC |

## Step 1 — Prepare the USB drive

Change into the `utils/` directory first:

```bash
cd utils/
```

The custom image URL is:

```
https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip
```

### Linux (Ubuntu / Debian) — recommended

```bash
sudo ./usb-build.ubuntu.sh -d <drive> \
  -r https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip
```

Replace `<drive>` with the device name of the USB stick (e.g. `sdb`, `sdc`).
Run `lsblk` first to identify the correct device and avoid overwriting the wrong disk.

Optional flags:

| Flag | Description |
|---|---|
| `-s <SSID>` | Pre-configure WiFi SSID (written to `wifi-creds.txt` on the DEEPRACER partition so the car connects automatically after flashing) |
| `-w <PASSWORD>` | WiFi password (requires `-s`) |
| `-l` | Ignore lock file — useful when re-running after a partial failure |
| `-a` | Process all attached USB drives in parallel |

The script will:
1. Install any missing host packages (`parted`, `mtools`, `pv`, `dosfstools`, `syslinux`, `exfatprogs`)
2. Create three partitions on the USB drive: `BOOT` (4 GiB FAT32), `DEEPRACER` (1 GiB FAT32), `FLASH` (20 GiB exFAT)
3. Download the Ubuntu 20.04 DeepRacer live ISO (required for the BIOS bootloader)
4. Download and unpack `custom_factory_reset.zip` into `factory_reset/`
5. Write the ISO bootloader to the `BOOT` partition
6. Copy the image files to the `FLASH` partition

### macOS

> **Note:** unetbootin (required for the macOS script) does not work on macOS
> Ventura and later ([upstream issue #337](https://github.com/unetbootin/unetbootin/issues/337)).
> Use a Linux host if possible.

```bash
sudo ./usb-build.sh -d disk2 \
  -r https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip
```

Replace `disk2` with the disk identifier shown in Disk Utility or `diskutil list`.

### Windows (PowerShell)

Run from an elevated PowerShell prompt (**not** "Run as Administrator" — the
script will prompt for elevation at the appropriate point):

```powershell
start powershell {
    .\usb-build.ps1 -DiskId <disk number> -CreatePartition `
        -CustomResetUrl https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip
}
```

Use `Get-Disk | Where-Object BusType -eq 'usb'` to find the correct disk number.

## Step 2 — Flash the car

You will need a monitor (HDMI), USB keyboard, and USB mouse connected to the
car's compute module for this step.

1. Connect a monitor to the compute module's HDMI port, and plug in a USB
   keyboard and mouse.
2. Insert the USB drive into any available USB port on the compute module.
3. Power on (or reset) the car and **repeatedly press `ESC`** to enter the BIOS.
4. In the BIOS, choose **Boot From File**, then navigate:
   `BOOT` → `<EFI>` → `<BOOT>` → `BOOTx64.EFI`
5. The car boots from the USB into the Ubuntu live environment. A terminal window
   appears on the desktop showing progress. The flash process starts
   **automatically after 10 seconds** — no input is needed.
6. Wait for the update to complete. The terminal window closes automatically when
   done. This typically takes **20–30 minutes**.
7. Remove the USB drive, then reboot or power off the car.

> **Warning:** Do not remove the USB drive or cut power while the terminal
> window is open and the flash is in progress.

## Step 3 — First boot

After the car reboots into Ubuntu 24.04 the DeepRacer service starts
automatically. No additional software installation is required.

The image does not include the X Window System, so you will interact with a
classic text-based terminal (no graphical desktop).

Default credentials:

| | Value |
|---|---|
| Hostname | Printed on the sticker on the bottom of the car (e.g. `amss-abcd`) |
| SSH user | `deepracer` |
| SSH password | `deepracer` |
| Web console | `https://<hostname>` — password printed on the bottom sticker |

On first boot the SSH host keys are regenerated automatically.

### Configuring WiFi

There are three ways to connect the car to your WiFi network.

**Option 1: USB cable**

Connect the car directly to your PC with a USB cable. The car will be
reachable at `https://deepracer.aws` while connected this way. Follow the
[network setup instructions](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-set-up-vehicle.html)
in the AWS developer guide to complete WiFi configuration.

**Option 2: WiFi credentials file on a USB drive**

Create a file called `wifi-creds.txt` on the root of a FAT32-formatted USB
drive with the following content:

```
ssid: '<YourSSID>'
password: '<YourPassword>'
```

Insert the USB drive into one of the car's USB ports (front, near the camera,
or at the back) after boot. The car will read the file and connect
automatically. See the
[developer guide](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-troubleshooting-wifi-connection-first-time.html)
for details.

**Option 3: Linux console**

With a keyboard and monitor connected, log in at the console and run:

```bash
nmcli device wifi list
sudo nmcli device wifi connect "YourSSID" password "YourPassword"
```

## Verification

After rebooting, the DeepRacer web console should be reachable at
`https://<hostname>` (hostname printed on the bottom sticker). Log in with
the vehicle password also printed on the sticker.

Once logged in, navigate to **Settings** to confirm the software version
displayed in the **About** section.

To confirm the OS and ROS versions from the car over SSH:

```bash
lsb_release -a
# Distributor ID: Ubuntu  Release: 24.04  Codename: noble

ros2 --version
# ros2 cli information ... jazzy

apt-cache policy aws-deepracer-core aws-deepracer-community-device-console aws-deepracer-util aws-deepracer-sample-models
```

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Car does not boot from USB | USB preparation incomplete | Re-run the USB-build script; confirm all three partitions were created and the `FLASH` partition contains `usb_flash.sh` and the image file |
| LED stays red / flashing fails | Image write error or corrupted download | Delete the local `factory_reset/` directory and `factory_reset.zip`, then re-run the USB-build script to re-download |
| Cannot reach `deepracer.local` after reboot | WiFi not configured | Connect via Ethernet, or re-flash the USB with `-s`/`-w` WiFi credentials and reflash the car |
| `install-deepracer.sh` fails with package errors | Stale apt cache or partial earlier run | Run `sudo apt update && sudo apt upgrade -y`, then re-run the script |
| Web console shows old version after reboot | Service not started | Check `systemctl status deepracer-core` and review logs with `journalctl -u deepracer-core` |

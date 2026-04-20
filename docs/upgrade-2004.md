# Installing the Community Stack on Ubuntu 20.04

This guide is for original DeepRacer cars already running Ubuntu 20.04 (stock
or previously updated via the AWS procedure) that you want to upgrade to the
community software stack — without re-flashing the car.

If you want to move to Ubuntu 24.04 instead, see
[Flashing to Ubuntu 24.04](flash-2404.md).

## What the scripts do

`install-prerequisites.sh` hardens the OS and refreshes package sources:

- Stops the DeepRacer service
- Disables IPv6, system suspend, and WiFi power-save
- Enables SSH and opens the firewall
- Removes the desktop environment, snap, and other unused packages
- Refreshes the OpenVINO and ROS 2 apt repository keys
- Upgrades all remaining packages

`install-deepracer.sh` installs the community packages:

- Adds the community apt repository and GPG key
- Installs `aws-deepracer-core` and `aws-deepracer-community-device-console`
- Restarts the DeepRacer service

## Prerequisites

- Original DeepRacer running Ubuntu 20.04 (not 16.04 — if on 16.04 follow
  the [AWS update guide](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-ubuntu-update.html)
  first)
- Network connectivity on the car
- SSH access or keyboard/monitor

## Steps

Clone this repository onto the car (or copy the `install_scripts/` directory):

```bash
git clone https://github.com/aws-deepracer-community/deepracer-custom-car.git
cd deepracer-custom-car
```

Run the scripts in order:

```bash
sudo install_scripts/aws-20.04/install-prerequisites.sh
```

> **Note:** This script removes the GNOME desktop and a number of unused
> packages. The car will be console-only after this point (no graphical login).
> Your SSH session will remain active throughout.

```bash
sudo install_scripts/aws-20.04/install-deepracer.sh
```

Reboot to complete the setup:

```bash
sudo reboot
```

## Verification

After rebooting, the DeepRacer web console should be reachable at
`https://<hostname>` (hostname from the bottom sticker). Log in with the
vehicle password from the sticker.

Navigate to **Settings → About** to confirm the software version, or check
from SSH:

```bash
apt-cache policy aws-deepracer-core aws-deepracer-community-device-console
```


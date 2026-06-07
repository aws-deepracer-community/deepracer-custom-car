# Building a DeepRacer for Raspberry Pi

## Features

- Previously trained models work without modification
- Inference via TensorFlow Lite or OpenVINO; supports the Intel Neural Compute Stick 2 (NCS2/MYRIAD)
- Integrates with DREM
- Single power source¹ — reduces weight and lowers centre of gravity
- Over-the-Air Software Updates

## Supported Boards

| Board | Notes |
| ----- | ----- |
| Raspberry Pi 4 | |
| Raspberry Pi 5 | |
| Raspberry Pi CM4 Lite | With [Waveshare CM4-IOBASE-A/B](https://www.waveshare.com/product/raspberry-pi/boards-kits/cm4-series.htm) |
| Raspberry Pi CM5 Lite | With [Waveshare CM5-IOBASE-A/B](https://www.waveshare.com/product/raspberry-pi/boards-kits/cm5-series.htm) or [Waveshare CM4-IOBASE-A/B](https://www.waveshare.com/product/raspberry-pi/boards-kits/cm4-series.htm) |

It is recommended to have a minimum of 2 GB of RAM.

The above combinations have been tested, other combinations may also work. Pi Zero W / Pi Zero 2W is not supported due to only having 512 MB of RAM.

## Parts

* WLToys A959, A969, A979, compatible car built from parts, or an original DeepRacer
* ESC for brushed motor, e.g. WP-1060-RTR — original DeepRacer already includes this
* 4-pin servo, e.g. Surpass Hobby S0017M — original DeepRacer already includes this
* 3D-printed mount parts from `/drawings`
* WLToys Body Posts (part# A969-05)
* Raspberry Pi 4 or 5 (or CM4/CM5 Lite on a Waveshare IO Base)
    * Stand-off set (2.5 mm)
* [Waveshare Servo Driver Hat](https://www.waveshare.com/product/raspberry-pi/hats/motors-relays/servo-driver-hat.htm) or compatible PCA9685 board
    * 40-pin stackable header (raises the servo hat above the cooling fan)
* Raspberry Pi Camera Module 2, 3, or 5
    * Longer ribbon cable (20–25 cm)
    * M2×15 mm screws + nuts
* Recommended cooling fan: [GeeekPi Raspberry Pi 4 Armor Lite](https://www.amazon.de/gp/product/B091L1XKL6/) (Pi 4) or equivalent active cooler (Pi 5)
* RGB LED:
    * [AZDelivery 5 × KY-016 FZ0455](https://www.amazon.co.uk/AZDelivery-KY-016-3-Colour-Arduino-including/dp/B07V6YSGC9/)
    * 4 female-to-female jumper cables
    * [LED holder](https://www.amazon.co.uk/Chanzon-Holder-Headfor-Emitting-Diodes/dp/B083Q9Q1ZR/)
* Servo extension cable (red power wire removed)
* 3-pin female JST connector
* 2.5 mm plastic screws (good quality) or M2 screws with nuts for front/rear body mounts

¹ The Waveshare hat includes a step-down converter (7.4 V → 5 V) that powers the Pi via the GPIO header. Other PCA9685 boards may require a separate 5 V supply.

## Software Install

Pre-built packages are provided, making installation straightforward.

1. Flash an SD card with **Ubuntu 24.04 Server for ARM64** using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). The recommended username is `deepracer`.
2. Boot and wait for the first-run upgrade to complete (this can take several minutes).
3. Clone the repository:
   ```bash
   git clone https://github.com/aws-deepracer-community/deepracer-custom-car
   ```
4. Run the prerequisites script and reboot:
   ```bash
   sudo ./install_scripts/rpi-24.04/install-prerequisites.sh
   sudo reboot
   ```
5. Run the main install script:
   ```bash
   sudo ./install_scripts/rpi-24.04/install-deepracer.sh
   ```

### Firmware configuration (`/boot/firmware/config.txt`)

The prerequisites script automatically adds the I²C/PWM overlay. The following additional changes must be made **manually** before rebooting:

#### Camera

Unlike Raspberry Pi OS, Ubuntu 24.04 does **not** reliably auto-detect camera modules. Disable auto-detection and add the overlay for your specific camera manually in `/boot/firmware/config.txt`:

| Camera | Overlay line |
| ------ | ------------ |
| Raspberry Pi Camera Module 2 (IMX219) | `dtoverlay=imx219` |
| Raspberry Pi Camera Module 3 (IMX708) | `dtoverlay=imx708` |

For example, for a Camera Module 2:

```ini
camera_auto_detect=0
dtoverlay=imx219
```

If you have two cameras connected (e.g. on a Compute Module), repeat the overlay once per camera with the port specified:

```ini
dtoverlay=imx219,cam0
dtoverlay=imx219,cam1
```

#### GPU Memory

Allocate sufficient GPU memory for the camera pipeline:

```ini
gpu_mem=256
```

Add this line to `/boot/firmware/config.txt`.

#### USB OTG / Ethernet Gadget

To expose a USB Ethernet gadget on the USB-C port, make two changes:

**`/boot/firmware/config.txt`** — add:
```ini
dtoverlay=dwc2,dr_mode=peripheral
```

**`/boot/firmware/cmdline.txt`** — append (on the same single line, after `rootwait`):
```
modules-load=dwc2,g_ether
```

After booting, a new network interface appears on the host computer. The Raspberry Pi is reachable at `10.0.0.1`; the DeepRacer console is available at `https://deepracer.aws`. Note that your computer must not be connected to other networks due to DNS priority; SSH directly to `10.0.0.1` always works.

### Starting the stack

The install script enables `deepracer-core` at boot, so the stack starts automatically. To run it manually instead, stop the service and launch directly:

```bash
sudo systemctl stop deepracer-core
sudo /opt/aws/deepracer/start_ros.sh
```

A camera must be connected before starting. The ROS launch log is shown in the console.

To follow the service logs:
```bash
journalctl -u deepracer-core
```

## Hardware Details

### PWM Outputs (Waveshare Servo Driver Hat)

| Channel | Purpose          | Notes |
| ------- | ---------------- | ----- |
| 0       | Speed controller | <span style="color:red">Remove the red wire for a stock DeepRacer ESC — 6 V will damage the hat</span> |
| 1       | Steering servo   | |
| 2       | RGB LED          | Tail light — Red |
| 3       | RGB LED          | Tail light — Green |
| 4       | RGB LED          | Tail light — Blue |
| 5       | *(unused)*       | |
| 6–15    | *(unused)*       | Side LEDs are driven directly from Pi GPIO — see below |

<span style="color:red">**NOTE:** Always remove the red wire from the stock DeepRacer speed controller before connecting to PWM channel 0.</span>

LiPo battery wiring: connect the 3-pin balance lead (black and red wires only) to VIN on the hat to power the hat and Raspberry Pi. The 2-pin main power lead goes to the car's ESC as normal.

### GPIO

The software uses the `libgpiod` interface. The GPIO chip differs by board:

| Board | GPIO chip |
| ----- | --------- |
| Raspberry Pi 4 / CM4 | `/dev/gpiochip0` |
| Raspberry Pi 5 / CM5 | `/dev/gpiochip4` |

The three side RGB LEDs are **not** driven through the PCA9685. Instead they are wired directly to the Pi's GPIO header and controlled via `libgpiod`:

| GPIO (BCM) | LED | Channel |
| ---------- | --- | ------- |
| 9  | Side LED 1 | Red   |
| 10 | Side LED 1 | Green |
| 11 | Side LED 1 | Blue  |
| 12 | Side LED 2 | Red   |
| 13 | Side LED 2 | Green |
| 14 | Side LED 2 | Blue  |
| 15 | Side LED 3 | Red   |
| 16 | Side LED 3 | Green |
| 17 | Side LED 3 | Blue  |

This is confirmed in [`status_led_pkg/constants.py`](../src/aws-deepracer-status-led-pkg/status_led_pkg/status_led_pkg/constants.py): the RPi code path uses `/dev/gpiochip0` (Pi 4) or `/dev/gpiochip4` (Pi 5) with lines 9–17, which are the Pi's own BCM GPIO pins, not PCA9685 outputs.

## What does not (yet) work

- Battery gauge is not connected — red warning message persists
- Device Info Node looks in non-existent locations — no functional impact

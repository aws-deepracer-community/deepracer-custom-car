# Building a DeepRacer for Raspberry Pi 4

## Features

Main features of the port:

- Previously trained models will work
- Uses Tensorflow Lite or OpenVINO for inference. Supports the Intel Neural Compute Stick 2 (NCS2/MYRIAD)
- Can integrate with DREM
- Single power source¹ - reduces weight and lowers center of gravity
- Over-the-Air Software Updates

## Parts

The following parts are needed:

* WLToys A979 (or compatible) or original DeepRacer
* 3D-print of the parts in `/drawing`.
* Chassis holder **TODO**
* Raspberry Pi 4, recommended 2GB or more of RAM
    * Stand-off set (2.5mm)
* [Waveshare Servo Driver Hat](https://www.waveshare.com/product/raspberry-pi/hats/motors-relays/servo-driver-hat.htm) or compatible PCA9865 servo boards. 
    * Stackable header 40pin (to get higher servo driver hat higher than the fan)
* Raspberry Pi Camera 2
    * Longer cable (20-25cm)
    * Screws M2x15mm + nuts
* Recommended cooling fan: [GeeekPi Raspberry Pi 4 Armor Lite](https://www.amazon.de/gp/product/B091L1XKL6/ref=ppx_yo_dt_b_search_asin_title?ie=UTF8&psc=1)
* RGB Led: 
    * [AZDelivery 5 x KY-016 FZ0455](https://www.amazon.co.uk/AZDelivery-KY-016-3-Colour-Arduino-including/dp/B07V6YSGC9/ref=sr_1_1)
    * 4 female-female jumper cables
    * [Led Holder](https://www.amazon.co.uk/Chanzon-Holder-Headfor-Emitting-Diodes/dp/B083Q9Q1ZR/ref=sr_1_4_sspa)
* Servo extension cable (with red cable cut)
* 3-pin female JST
* 2.5mm plastic screws (preferrably of good quality) to mount back and front; or use M2 screws with nuts

¹ The Waveshare hat comes with a step-down converter from 7.4V to 5V, and will power the Pi via the GPIO header. Other similar cards will require separate power.

## Software Install

Installation of software is reasonably straight forward, as pre-built packages are provided:

- Flash an SD card with Ubuntu 22.04 Server for ARM64 using the Raspberry Pi Imager.
- Boot the SD card, and let it upgrade (this takes some time...)
- Run `git clone https://github.com/aws-deepracer-community/deepracer-custom`
- Run `sudo ./install_scripts/pi/install-prerequisites.sh`
- Reboot
- Run `sudo ./install_scripts/pi/install-deepracer.sh`

Once installed you can start the stack with `sudo /opt/aws/deepracer/start_ros.sh`. To ensure a smooth start a camera needs to be plugged in.
The launch log will now display in the console.

To automatically start at boot do `sudo systemctl enable deepracer-core` and to start the service in the background `sudo systemctl start deepracer-core`.

### Changes

Some changes have been made to the code to enable access to GPIO as sysfs layout is different on the Raspberry Pi than on the custom Intel board.

### Improvements

- Stripped down OS
- Runs the custom deepracer stack also seen in [deepracer-scripts](https://github.com/davidfsmith/deepracer-scripts).

### Details

**PWM Outputs**

| Channel | Purpose          | Notes                                                                   |
| ------- | ---------------- | ----------------------------------------------------------------------- |
| 0       | Speed controller | <span style="color:red">Remove red cable for stock DeepRacer ESC</span> |
| 1       | Steering servo   |                                                                         |
| 2       | RGB LED          | Tail light - Red                                                        |
| 3       | RGB LED          | Tail light - Green                                                      |
| 4       | RGB LED          | Tail light - Blue                                                       |
| 5       |
| 6       |
| 7       | RGB LED          |
| 8       | RGB LED          |
| 9       | RGB LED          |
| 10      | RGB LED          |
| 11      | RGB LED          |
| 12      | RGB LED          |
| 13      | RGB LED          |
| 14      | RGB LED          |
| 15      | RGB LED          |

<span style="color:red">**NOTE:** Remove the red cable on the stock DeepRacer from the speed controller into PWM channel 0, otherwise you are putting 6V into the servo hat.</span>

LiPo can power both the board and car, 3 pin (balance lead) gets wired to VIN (black and red cables only) to power the board and RPi. The 2 pin power cable goes to the car as normal.


**GPIO layout:**

- `gpio1` - enables PWM (does not do anything, PWM is always on for the Waveshare board)
- `gpio495`-`gpio504` - maps to PWM7 to PWM15 on the Hat, to control three RGB leds (those originally on the side of the board)

**USB host mode:**
To connect the USB-C port on the Raspberry Pi 4 to a USB on your computer, then you need to perform two changes:
* Add `dtoverlay=dwc2,dr_mode=host` to your `/boot/firmware/config.txt`
* Add `modules-load=dwc2,g_ether` to your `/boot/firmware/cmdline.txt`

With this you will see a new network connect appear in Windows (and Mac?). The Raspberry Pi will have IP 10.0.0.1; you can connect to the console via `https://deepracer.aws`. This will require your computer to be disconnected from all other networks (given a DNS priority issue). SSH directly to the IP will work.

## What does not (yet) work

- Battery gauge is not connected - red warning message persists
- Device Info Node is looking in non-existent places - no real impact

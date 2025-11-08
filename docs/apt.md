# APT Repository

The APT repository is hosted at `https://aws-deepracer-community-sw.s3.eu-west-1.amazonaws.com/deepracer-custom-car` and is signed by a key with ID `CFB167A8F18DE6A634A6A2E4A63BC335D48DF8C6`.

There are two codenames `stable` and `experimental`, the former having more stable packages, and experimental hosting any new features in development, which may or may not work at all times.

The component matrix / architecture support is as follows:

| Hardware               | Ubuntu 20.04 (Focal) + ROS2 Foxy  | Ubuntu 22.04 (Jammy) + ROS2 Humble | Ubuntu 24.04 (Noble) + ROS2 Jazzy  |
|------------------------|-----------------------------------|------------------------------------|------------------------------------|
| Original (`amd64`)     | `dr-focal`                        | No                                 | `dr-noble`                         |
| Raspberry Pi (`arm64`) | No                                | `rpi4-jammy`                       | `rpi-noble`                        |
| Other x86 (`amd64`)    | No                                | Source only                        | Source only                        |                          

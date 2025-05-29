# Custom Image USB Flash Drive Creation

## Create a USB flash drive automatically with the custom image

* Enter the utils directory
* Run `./usb-build.ubuntu.sh -d [drive] -r https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip`
* Drive is `sdb`, `sdc` or similar. Use `lsblk` to look for the available drives.


## Create a USB flash drive manually with the custom image

* Create the USB drive as normal with one of the usb-build scripts in `utils/`.
* Insert it into a PC - identify the "FLASH" partition (3rd partition on the drive)
* Check that it contains files (amongst others):
    * `dlrc_image_21WW09.5_tpm.img`
    * `dlrc_image_21WW09.5_tpm.md5`
    * `usb_flash.sh`
    * `usb_flash_dlrc.sh`
* Delete the `dlrc_image_21WW09.5_tpm.img` and `dlrc_image_21WW09.5_tpm.md5` files.
* Download `https://larsll-build-artifact-share.s3.eu-north-1.amazonaws.com/car-image/custom_factory_reset.zip` and unzip it.
* Copy the 4 files onto the FLASH partition from the unzip location:
    * `dlrc_image_20250409.1_tpm.img`
    * `dlrc_image_20250409.1_tpm.md5`
    * `usb_flash.sh`
    * `usb_flash_dlrc.sh`
* Unmount the drive.
* Insert into DR and flash as normal.
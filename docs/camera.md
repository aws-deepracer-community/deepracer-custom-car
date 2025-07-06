# Cameras

## Field of View

Modern cameras typically support multiple sensor modes with different resolutions. Some of these modes use the full sensor area, while others are cropped to achieve different aspect ratios or to reduce data processing requirements. The choice of sensor mode affects both the field of view and the processing latency.

For DeepRacer purposes we need the full FoV, but with a low output resolution as inference happens at 160 x 120. For the Raspberry Pi Camera Modules we use the lowest resolution sensor mode with a 100% FoV:

Camera                              | Sensor Mode | Output Res 
------------------------------------|-------------|-------------
Rasperry Pi Camera 2 (imx219)       | 1640x1232   | 160x120     
Rasperry Pi Camera 3 (imx708)       | 2304x1296   | 160x120     

The original DeepRacer/DeepLens camera, combines a GeoSemiconductor GC6500 processor with an OmniVision OV4689, and standard configuration uses a 1920x1080, resized to the requested resolution in the GC6500. The original camera package used 640x480 as input, and scaled down to 160x120 in software.

## Camera Performance

We define the camera latency as the time it takes to read in a full frame from first to last pixel. For Raspberry Pi we use libcamera, latency can be measured comparing the `libcamera::controls::SensorTimestamp` value with the time when the frame arrives in `camera_ros`.

Tested on a Raspberry Pi 5 on Ubuntu 24.04 we got the following results:

Camera                              | Sensor Mode | Output Res | Pixel Format | Latency
------------------------------------|-------------|------------|--------------|---------
Rasperry Pi Camera 2 (imx219)       | 640x480     | 160x120    | BGR888       | 10.7 ms 
Rasperry Pi Camera 2 (imx219)       | 640x480     | 640x480    | BGR888       | 10.6 ms 
**Rasperry Pi Camera 2 (imx219)**       | **1640x1232**   | **160x120**    | **BGR888**       | **27.1 ms** 
Rasperry Pi Camera 2 (imx219)       | 1640x1232   | 1640x1232  | BGR888       | 26.9 ms 
Rasperry Pi Camera 2 (imx219)       | 3280x2464   | 160x120    | BGR888       | 58.9 ms 
Rasperry Pi Camera 2 (imx219)       | 3280x2464   | 3280x2464  | BGR888       | 57.6 ms 
Rasperry Pi Camera 3 (imx708)       | 1536x864    | 160x120    | BGR888       | 10.5 ms 
Rasperry Pi Camera 3 (imx708)       | 1536x864    | 1536x864   | BGR888       | 10.4 ms 
**Rasperry Pi Camera 3 (imx708)**       | **2304x1296**   | **160x120**    | **BGR888**       | **21.6 ms** 
Rasperry Pi Camera 3 (imx708)       | 2304x1296   | 2304x1296  | BGR888       | 21.6 ms 
Rasperry Pi Camera 3 (imx708)       | 4608x2592   | 160x120    | BGR888       | 81.3 ms 
Rasperry Pi Camera 3 (imx708)       | 4608x2592   | 4608x2592  | BGR888       | 80.8 ms 
DeepLens (GC6500 + OV4689) via USB3 | 1920x1080   | 320x240    | MJPEG        | 0.3 ms* (~10 ms)

The OV4689 is a higher speed camera, which can do 120 fps @ 1920x1080; giving a latency of approximately 10 ms, assuming no negative impact of the GC6500.
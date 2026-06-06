#!/usr/bin/env python3
from enum import IntEnum
import datetime
import traceback
import glob
import json
import logging
import time
import sys
import os

import cv2
from cv_bridge import CvBridge

import numpy as np

import rclpy
from rclpy.time import Time, Duration
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from rcl_interfaces.msg import ParameterDescriptor, ParameterType

from sensor_msgs.msg import Image as ROSImg
from sensor_msgs.msg import CompressedImage as ROSCImg

from deepracer_interfaces_pkg.msg import CameraMsg, InferResultsArray
from deepracer_interfaces_pkg.srv import VideoStateSrv, LoadModelSrv, InferenceStateSrv

CAMERA_MSG_TOPIC = "video_mjpeg"
DISPLAY_MSG_TOPIC = "display_mjpeg"
ACTIVATE_CAMERA_SERVICE_NAME = "media_state"
TFLITE_INFERENCE_TOPIC = "/inference_pkg_tflite/rl_results"
TFLITE_LOAD_SRV = "/inference_pkg_tflite/load_model"
TFLITE_START_SRV = "/inference_pkg_tflite/inference_state"
OV_INFERENCE_TOPIC = "/inference_pkg_ov/rl_results"
OV_LOAD_SRV = "/inference_pkg_ov/load_model"
OV_START_SRV = "/inference_pkg_ov/inference_state"
DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480

class PlaybackState(IntEnum):
    """ Status of Playback
    Extends:
        Enum
    """
    Stopped = 0
    Running = 1

class InferenceComparisonNode(Node):
    """ This node is used to compare the inference of TFLite with OpenVINO.
    """

    _play_state = PlaybackState.Stopped
    _play_messages_generator = None
    _playback_frames = 0
    _prev_img = None

    def __init__(self):
        super().__init__('inference_comparison_node')

        self.declare_parameter('resize_images', False, ParameterDescriptor(
            type=ParameterType.PARAMETER_BOOL))
        self.declare_parameter('resize_images_factor', 4, ParameterDescriptor(
            type=ParameterType.PARAMETER_INTEGER))
        self.declare_parameter('fps', 15, ParameterDescriptor(
            type=ParameterType.PARAMETER_INTEGER))
        self.declare_parameter('display_topic_enable', True, ParameterDescriptor(
            type=ParameterType.PARAMETER_BOOL))
        self.declare_parameter('blur_image', False, ParameterDescriptor(
            type=ParameterType.PARAMETER_BOOL))
        self.declare_parameter('image_dir', "", ParameterDescriptor(
            type=ParameterType.PARAMETER_STRING))
        self.declare_parameter('model_dir', "", ParameterDescriptor(
            type=ParameterType.PARAMETER_STRING))
        self.declare_parameter('output_dir', "", ParameterDescriptor(
            type=ParameterType.PARAMETER_STRING))
        self.declare_parameter('autostart', True, ParameterDescriptor(
            type=ParameterType.PARAMETER_BOOL))

        self._resize_images = self.get_parameter('resize_images').value
        self._resize_images_factor = self.get_parameter('resize_images_factor').value
        self._display_topic_enable = self.get_parameter('display_topic_enable').value
        self._blur_image = self.get_parameter('blur_image').value
        self._fps = self.get_parameter('fps').value
        self._image_dir = self.get_parameter('image_dir').value
        self._model_dir = self.get_parameter('model_dir').value
        self._output_dir = self.get_parameter('output_dir').value
        self._autostart = self.get_parameter('autostart').value

        # Init cv bridge
        self._bridge = CvBridge()

    def __enter__(self):

        self._main_cbg = ReentrantCallbackGroup()
        self._svc_cbg = ReentrantCallbackGroup()

        # Call ROS service to enable the Video Stream
        self._camera_state_srv = self.create_service(VideoStateSrv, ACTIVATE_CAMERA_SERVICE_NAME,
                                                     callback=self._state_service_callback,
                                                     callback_group=self._main_cbg)

        # Publisher to broadcast the video stream.
        self._camera_pub = self.create_publisher(CameraMsg, CAMERA_MSG_TOPIC, 1,
                                                 callback_group=self._main_cbg)
        self._display_pub = self.create_publisher(ROSImg, DISPLAY_MSG_TOPIC, 250,
                                                  callback_group=self._main_cbg)
        self._display_cpub = self.create_publisher(ROSCImg, DISPLAY_MSG_TOPIC + "/compressed", 250,
                                                   callback_group=self._main_cbg)

        # Subscriber to the inference
        self._infer_tflite_sub = self.create_subscription(
            InferResultsArray, TFLITE_INFERENCE_TOPIC, lambda msg: self._inference_cb(msg, "tflite"),
            5, callback_group=self._main_cbg)
        self._infer_ov_sub = self.create_subscription(
            InferResultsArray, OV_INFERENCE_TOPIC, lambda msg: self._inference_cb(msg, "ov"),
            5, callback_group=self._main_cbg)

        # Service clients to load model and start inference
        self._infer_tflite_load = self.create_client(
            LoadModelSrv, TFLITE_LOAD_SRV, callback_group=self._svc_cbg)
        self._infer_tflite_state = self.create_client(
            InferenceStateSrv, TFLITE_START_SRV, callback_group=self._svc_cbg)
        self._infer_ov_load = self.create_client(
            LoadModelSrv, OV_LOAD_SRV, callback_group=self._svc_cbg)
        self._infer_ov_state = self.create_client(
            InferenceStateSrv, OV_START_SRV, callback_group=self._svc_cbg)

        with open(os.path.join(self._model_dir,'model_metadata.json')) as model_metadata:
            file_contents = model_metadata.read()
            self._model_metadata = json.loads(file_contents)

        self._playback_timer = None

        self.get_logger().info('Node started. Ready to start playback.')

        if self._autostart:
            self._infer_ov_load.wait_for_service()
            self._infer_tflite_load.wait_for_service()
            self.get_logger().info('Starting playback automatically.')
            self_start = self.create_client(VideoStateSrv, ACTIVATE_CAMERA_SERVICE_NAME)
            req = VideoStateSrv.Request()
            req.activate_video = 1
            _ = self_start.call_async(req)

        return self

    def __exit__(self, ExcType, ExcValue, Traceback):
        """Called when the object is destroyed.
        """
        if ExcType is not None:
            self.get_logger().info('Stopping the node due to {}.'
                                .format(ExcType.__name__))
        if self._play_state != PlaybackState.Stopped:
            self._play_state = PlaybackState.Stopped
            self._stop_playback()
            self.destroy_timer(self._playback_timer)

        self.get_logger().info('Node cleanup done. Exiting.')

    def _start_playback(self):
        """ Method that is used to start the playback.
        """
        try:
            self.get_logger().info("Reading {}.".format(self._image_dir))

            self._picture_files = sorted(glob.glob(f"{self._image_dir}/*.jpg"))
            self._results = {}
            self._frame_count = {}
            self._frame_count['tflite'] = 0
            self._frame_count['ov'] = 0
            self._frame_count['match'] = 0
            self._frame_count['mismatch'] = 0

            self.get_logger().info("Found {} files.".format(len(self._picture_files)))

            # Load the model
            tflite_model_call = LoadModelSrv.Request()
            tflite_model_call.artifact_path = os.path.join(self._model_dir, "model.tflite")
            tflite_model_call.action_space_type = 1
            tflite_model_call.task_type = 0
            tflite_model_call.pre_process_type = 1

            _ = self._infer_tflite_load.call(tflite_model_call)

            ov_model_call = LoadModelSrv.Request()
            ov_model_call.artifact_path = os.path.join(self._model_dir, "model.xml")
            ov_model_call.action_space_type = 1
            ov_model_call.task_type = 0
            ov_model_call.pre_process_type = 1

            _ = self._infer_ov_load.call(ov_model_call)

            # Start inference
            start_infer_call = InferenceStateSrv.Request()
            start_infer_call.start = 1
            start_infer_call.task_type = 0

            _ = self._infer_tflite_state.call(start_infer_call)
            _ = self._infer_ov_state.call(start_infer_call)

            # Prepare timer
            self._playback_timer = self.create_timer(1.0/(self._fps), self._playback_timer_cb,
                                                     callback_group=self._main_cbg)

            self._play_state = PlaybackState.Running

        except Exception as e:  # noqa E722
            self.get_logger().error("{} occurred.".format(traceback.format_exc()))

    def _stop_playback(self):

        try:
            """ Method that is used to stop the playback.
            """
            self.get_logger().info('Stopping the playback after {} frames.'.format(self._playback_frames))
            self._play_state = PlaybackState.Stopped
            self.get_logger().debug(json.dumps(self._results))

            # Stop timer
            self._playback_timer.destroy()

            # Wait for messages to come through
            time.sleep(1)

            # Create summary
            self._create_summary()

            # Stop ROS if autostart
            if self._autostart:
                self.context.try_shutdown()

        except Exception as e:  # noqa E722
            self.get_logger().error("{} occurred.".format(traceback.format_exc()))

    def _playback_timer_cb(self):

        # Play next message

        try:

            filename = self._picture_files.pop(0)

            img_in = cv2.imread(filename)
            img_in = cv2.cvtColor(img_in, cv2.COLOR_RGB2BGR)

            if self._blur_image and self._prev_img is not None:
                alpha = 0.6
                beta = (1.0 - alpha)
                img_out = cv2.addWeighted(img_in, alpha, self._prev_img, beta, 0.0)
                img_out = cv2.blur(img_out, (15, 15))
            else:
                img_out = img_in

            if (self._resize_images):
                img_out = cv2.resize(img_out, dsize=(int(DEFAULT_IMAGE_WIDTH / self._resize_images_factor),
                                     int(DEFAULT_IMAGE_HEIGHT / self._resize_images_factor)))

            c_msg = self._bridge.cv2_to_compressed_imgmsg(img_out)
            c_msg.format = "bgr8; jpeg compressed bgr8"

            timestamp = self.get_clock().now()
            c_msg.header.stamp = timestamp.to_msg()

            camera_msg: CameraMsg = CameraMsg()
            camera_msg.images.append(c_msg)

            self._results[str(timestamp.nanoseconds)] = {}
            self._results[str(timestamp.nanoseconds)]['filename'] = filename

            self._camera_pub.publish(camera_msg)
            if self._display_topic_enable:
                self._display_pub.publish(self._bridge.cv2_to_imgmsg(img_out, "bgr8"))
                self._display_cpub.publish(c_msg)

            self._playback_frames += 1
            self._prev_img = img_in

        except IndexError:
            self.get_logger().info("End of stream after {} messages.".format(self._playback_frames))
            self._playback_timer.cancel()
            self._stop_playback()
        except:  # noqa E722
            self.get_logger().error("{} occurred.".format(str(traceback.print_exc())))
            self._stop_playback()

    def _state_service_callback(self, req, res):
        """Callback for the playback state service.
        Args:
            req (VideoStateSrv.Request): Request change to the playback state
            res (VideoStateSrv.Response): Response object with error(int) flag
                                           to indicate if the service call was
                                           successful.

        Returns:
            VideoStateSrv.Response: Response object with error(int) flag to
                                     indicate if the call was successful.
        """
        if self._play_state == PlaybackState.Running and req.activate_video == 0:
            self._stop_playback()
            res.error = 0

        elif (self._play_state == PlaybackState.Running) and (req.activate_video == 1):
            res.error = 1

        elif self._play_state == PlaybackState.Stopped and req.activate_video == 0:
            res.error = 0

        elif self._play_state == PlaybackState.Stopped and req.activate_video == 1:
            self._start_playback()
            res.error = 0

        return res

    def _inference_cb(self, msg: InferResultsArray, node: str):
        timestamp = Time.from_msg(msg.images[0].header.stamp)
        timestamp_str = str(timestamp.nanoseconds)
        time_diff: Duration = self.get_clock().now() - timestamp
        self._frame_count[node] += 1
        self.get_logger().info(
            f"Received message {self._frame_count[node]} from {node} after {(time_diff.nanoseconds/1.0e6):.1f} ms")

        self._results[timestamp_str][node] = {}
        self._results[timestamp_str][node]['time'] = {}
        self._results[timestamp_str][node]['time']['stamp'] = timestamp.nanoseconds
        self._results[timestamp_str][node]['time']['diff'] = time_diff.nanoseconds
        self._results[timestamp_str][node]['results'] = {}
        for res in msg.results:
            self._results[timestamp_str][node]['results'][res.class_label] = res.class_prob

    def _create_summary(self):

        output = {}
        output['model'] = self._model_dir
        output['model_metadata'] = self._model_metadata

        # Check results
        for key, value in self._results.items():
            self._results[key]['summary'] = {}
            self._results[key]['summary']['action_diff'] = {}
            self._results[key]['summary']['best'] = {}

            tflite = value['tflite']['results']
            ov = value['ov']['results']

            tf_best = {'action': -1, 'value': 0}
            ov_best = {'action': -1, 'value': 0}

            for k in tflite:
                self._results[key]['summary']['action_diff'][k] = tflite[k] - ov[k]

                if tflite[k] > tf_best['value']:
                    tf_best['action'] = k
                    tf_best['value'] = tflite[k]

                if ov[k] > ov_best['value']:
                    ov_best['action'] = k
                    ov_best['value'] = ov[k]

            self._results[key]['summary']['best']['tflite'] = tf_best
            self._results[key]['summary']['best']['ov'] = ov_best

            if self._results[key]['summary']['best']['tflite']['action'] == self._results[key]['summary']['best'][
                    'ov']['action']:
                self.get_logger().info(
                    f"Picture {key} in agreement for action {self._results[key]['summary']['best']['tflite']['action']} at ({self._results[key]['summary']['best']['tflite']['value']:.5f}, {self._results[key]['summary']['best']['ov']['value']:.5f}).")
                self._frame_count['match'] += 1
            else:
                self.get_logger().info(
                    f"Picture {key} not in agreement with actions ({self._results[key]['summary']['best']['tflite']['action']}, {self._results[key]['summary']['best']['ov']['action']}) at ({self._results[key]['summary']['best']['tflite']['value']:.5f}, {self._results[key]['summary']['best']['ov']['value']:.5f}).")
                self._frame_count['mismatch'] += 1

        output['summary'] = self._frame_count
        output['frames'] = self._results

        # Writing to disk
        filename = f"results-{int(datetime.datetime.utcnow().timestamp() * 1000)}.json"
        if self._output_dir:
            filename = os.path.join(self._output_dir, filename)
        with open(filename, "w", encoding="utf-8") as f:
            self.get_logger().info(f"Writing {filename} to disk.")
            json.dump(output, f, ensure_ascii=False, indent=4)

def main(args=None):

    try:
        rclpy.init(args=args)
        with InferenceComparisonNode() as inference_comparison_node:
            executor = MultiThreadedExecutor()
            rclpy.spin(inference_comparison_node, executor)
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        inference_comparison_node.destroy_node()
    except KeyboardInterrupt:
        pass
    except:  # noqa: E722
        logging.exception("Error in Node")

    rclpy.try_shutdown()


if __name__ == "__main__":
    main()

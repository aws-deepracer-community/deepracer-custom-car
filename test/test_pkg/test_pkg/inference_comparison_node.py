#!/usr/bin/env python3
from enum import IntEnum
import datetime
import traceback
import glob
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
MODEL_INPUT_WIDTH = 160
MODEL_INPUT_HEIGHT = 120

# Metadata mappings used for internal TF frozen-graph inference
_TF_ALGORITHM_HEAD = {
    'clipped_ppo': 'main',
    'sac': 'policy',
}
_TF_CAMERA_SENSORS = {'observation', 'FRONT_FACING_CAMERA', 'LEFT_CAMERA', 'STEREO_CAMERAS'}
_TF_SENSOR_INPUT_NAME_FMT = {
    'observation':           'main_level/agent/{}/online/network_0/observation/observation:0',
    'FRONT_FACING_CAMERA':   'main_level/agent/{}/online/network_0/FRONT_FACING_CAMERA/FRONT_FACING_CAMERA:0',
    'LEFT_CAMERA':           'main_level/agent/{}/online/network_0/LEFT_CAMERA/LEFT_CAMERA:0',
    'STEREO_CAMERAS':        'main_level/agent/{}/online/network_0/STEREO_CAMERAS/STEREO_CAMERAS:0',
}
_TF_SENSOR_CHANNELS = {
    'observation': 1,
    'FRONT_FACING_CAMERA': 1,
    'LEFT_CAMERA': 1,
    'STEREO_CAMERAS': 2,
}

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

        # Internal TF inference state (populated by _load_tf_model)
        self._tf_graph = None
        self._tf_session = None
        self._tf_inputs = {}
        self._tf_output = None
        # Tracks concurrent in-flight TF session.run() calls so we can wait
        # for all of them to finish before closing the session or summarising.
        self._tf_inflight_lock = threading.Lock()
        self._tf_inflight_count = 0
        self._tf_idle = threading.Event()
        self._tf_idle.set()
        # Single-worker executor: TF v1 sessions serialize concurrent runs, so
        # submitting to one thread avoids blocking the ROS timer callback and
        # prevents wall-clock times from compounding across frames.
        self._tf_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tf_infer')

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

        if self._tf_session is not None:
            self._tf_idle.wait(timeout=10.0)
            self._tf_session.close()
            self._tf_session = None
        self._tf_executor.shutdown(wait=False)

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
            self._frame_count['tf'] = 0
            self._load_tf_model()

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

            # Wait for external inference messages and any in-flight TF calls
            self.get_logger().info('Waiting for pending inference results...')
            self._tf_idle.wait(timeout=10.0)
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

            # Run internal TF inference synchronously for 3-way comparison
            if self._tf_session is not None:
                with self._tf_inflight_lock:
                    self._tf_inflight_count += 1
                    self._tf_idle.clear()

                def _tf_task(img=img_in, ts=timestamp):
                    try:
                        tf_t0 = time.monotonic()
                        tf_results = self._run_tf_inference(img)
                        tf_elapsed_ms = (time.monotonic() - tf_t0) * 1000.0
                        timestamp_ns = str(ts.nanoseconds)
                        self._results[timestamp_ns]['tf'] = {
                            'time': {'stamp': ts.nanoseconds, 'diff': int(tf_elapsed_ms * 1e6)},
                            'results': tf_results,
                        }
                        self._frame_count['tf'] += 1
                        self.get_logger().info(
                            f"TF internal inference {self._frame_count['tf']} complete in {tf_elapsed_ms:.1f} ms")
                    except Exception:
                        self.get_logger().warning(
                            f"TF internal inference failed: {traceback.format_exc()}")
                    finally:
                        with self._tf_inflight_lock:
                            self._tf_inflight_count -= 1
                            if self._tf_inflight_count == 0:
                                self._tf_idle.set()

                self._tf_executor.submit(_tf_task)
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

    def _load_tf_model(self):
        """Load the TF frozen graph (model.pb) for internal inference comparison."""
        model_pb = os.path.join(self._model_dir, 'model.pb')
        if not os.path.isfile(model_pb):
            self.get_logger().warning(
                f"model.pb not found at {model_pb}; native TF inference disabled.")
            return

        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        import tensorflow.compat.v1 as tf  # type: ignore
        tf.disable_eager_execution()

        with tf.gfile.GFile(model_pb, 'rb') as f:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(f.read())

        self._tf_graph = tf.Graph()
        with self._tf_graph.as_default():
            tf.import_graph_def(graph_def, name='')

        config = tf.ConfigProto(allow_soft_placement=True)
        self._tf_session = tf.Session(graph=self._tf_graph, config=config)

        sensors = self._model_metadata.get('sensor', ['observation'])
        training_algo = self._model_metadata.get('training_algorithm', 'clipped_ppo')
        head = _TF_ALGORITHM_HEAD.get(training_algo, 'main')

        self._tf_inputs = {}
        for sensor in sensors:
            if sensor in _TF_CAMERA_SENSORS:
                tensor_name = _TF_SENSOR_INPUT_NAME_FMT[sensor].format(head)
                try:
                    self._tf_inputs[sensor] = {
                        'tensor': self._tf_graph.get_tensor_by_name(tensor_name),
                        'channels': _TF_SENSOR_CHANNELS[sensor],
                    }
                except KeyError:
                    self.get_logger().warning(f"Tensor {tensor_name} not found in graph.")

        output_name = (
            f'main_level/agent/{head}/online/network_1/ppo_head_0/policy:0'
        )
        self._tf_output = self._tf_graph.get_tensor_by_name(output_name)
        self.get_logger().info(
            f"TF model loaded from {model_pb}. Inputs: {list(self._tf_inputs.keys())}")

        # Warmup: run one dummy inference to trigger JIT compilation and
        # GPU→CPU device-placement resolution so the first real frame is not
        # burdened with startup overhead.
        try:
            warmup_feed = {
                info['tensor']: np.zeros(
                    (1, MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH, info['channels']),
                    dtype=np.float32)
                for info in self._tf_inputs.values()
            }
            self._tf_session.run(self._tf_output, feed_dict=warmup_feed)
            self.get_logger().info("TF warmup inference complete.")
        except Exception:
            self.get_logger().warning(f"TF warmup failed: {traceback.format_exc()}")

    def _preprocess_for_tf(self, img_bgr, channels):
        """Resize and normalise a BGR image for frozen-graph inference.

        Returns:
            numpy.ndarray: float32 array of shape
                [1, MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH, channels].
        """
        resized = cv2.resize(img_bgr, (MODEL_INPUT_WIDTH, MODEL_INPUT_HEIGHT))
        if channels == 1:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            return gray.astype(np.float32).reshape(
                1, MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH, 1)
        elif channels == 2:
            half_w = MODEL_INPUT_WIDTH // 2
            left = cv2.cvtColor(resized[:, :half_w], cv2.COLOR_BGR2GRAY)
            right = cv2.cvtColor(resized[:, half_w:], cv2.COLOR_BGR2GRAY)
            stacked = np.stack([left, right], axis=-1).astype(np.float32)
            return stacked.reshape(1, MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH, 2)
        else:
            return resized.astype(np.float32).reshape(
                1, MODEL_INPUT_HEIGHT, MODEL_INPUT_WIDTH, channels)

    def _run_tf_inference(self, img_bgr):
        """Run the frozen TF graph on a single BGR image.

        Returns:
            dict: str(class_index) -> probability, matching the format from
                  the external inference nodes.
        """
        feed_dict = {
            info['tensor']: self._preprocess_for_tf(img_bgr, info['channels'])
            for info in self._tf_inputs.values()
        }
        output = self._tf_session.run(self._tf_output, feed_dict=feed_dict)
        probs = output[0]
        return {i: float(p) for i, p in enumerate(probs)}

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

            if not all(k in value for k in ('tflite', 'ov', 'tf')):
                self.get_logger().warning(f"Frame {key} missing inference results, skipping.")
                continue

            tflite = value['tflite']['results']
            ov = value['ov']['results']
            tf_native = value['tf']['results']

            tflite_best = {'action': -1, 'value': 0}
            ov_best = {'action': -1, 'value': 0}
            tf_best = {'action': -1, 'value': 0}

            for k in tflite:
                self._results[key]['summary']['action_diff'][k] = tflite[k] - ov[k]

                if tflite[k] > tflite_best['value']:
                    tflite_best['action'] = k
                    tflite_best['value'] = tflite[k]

                if ov[k] > ov_best['value']:
                    ov_best['action'] = k
                    ov_best['value'] = ov[k]

                if k in tf_native and tf_native[k] > tf_best['value']:
                    tf_best['action'] = k
                    tf_best['value'] = tf_native[k]

            self._results[key]['summary']['best']['tflite'] = tflite_best
            self._results[key]['summary']['best']['ov'] = ov_best
            self._results[key]['summary']['best']['tf'] = tf_best

            all_agree = (
                tflite_best['action'] == ov_best['action'] == tf_best['action']
            )
            if all_agree:
                self.get_logger().info(
                    f"Picture {key} in agreement for action {tflite_best['action']} "
                    f"at tflite={tflite_best['value']:.5f}, "
                    f"ov={ov_best['value']:.5f}, tf={tf_best['value']:.5f}.")
                self._frame_count['match'] += 1
            else:
                self.get_logger().info(
                    f"Picture {key} not in agreement: "
                    f"tflite={tflite_best['action']} ({tflite_best['value']:.5f}), "
                    f"ov={ov_best['action']} ({ov_best['value']:.5f}), "
                    f"tf={tf_best['action']} ({tf_best['value']:.5f}).")
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

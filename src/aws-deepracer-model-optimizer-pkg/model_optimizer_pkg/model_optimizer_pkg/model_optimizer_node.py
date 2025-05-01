#!/usr/bin/env python3

#################################################################################
#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.          #
#                                                                               #
#   Licensed under the Apache License, Version 2.0 (the "License").             #
#   You may not use this file except in compliance with the License.            #
#   You may obtain a copy of the License at                                     #
#                                                                               #
#       http://www.apache.org/licenses/LICENSE-2.0                              #
#                                                                               #
#   Unless required by applicable law or agreed to in writing, software         #
#   distributed under the License is distributed on an "AS IS" BASIS,           #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.    #
#   See the License for the specific language governing permissions and         #
#   limitations under the License.                                              #
#################################################################################

"""
model_optimizer_node.py

This module creates the model_optimizer_node which is responsible for running the 
model converter script for the DeepRacer reinforcement learning models to obtain
the Intel OpenVINO or Tensorflow TFlite files required to run the inference with 
the model.

    "The optimizer performs static model analysis, and adjusts deep
    learning models for optimal execution on end-point target devices."

The node defines:
    model_optimizer_service: A service to call the model converter API
                             for the specific model with appropriate model and platform
                             specific parameters set.
"""

import os
import subprocess
import shlex
import re
import rclpy
from rclpy.parameter import ParameterType
from rclpy.node import Node, ParameterDescriptor
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from deepracer_interfaces_pkg.srv import (ModelOptimizeSrv)
from model_optimizer_pkg import constants


class ModelOptimizerNode(Node):
    """Node responsible for running the Model Converter for the DeepRacer models.
    """

    def __init__(self):
        """Create a ModelOptimizerNode.
        """
        super().__init__("model_optimizer_node")
        self.get_logger().info("model_optimizer_node started")

        self.declare_parameter('inference_engine', "TFLITE", ParameterDescriptor(
            type=ParameterType.PARAMETER_STRING))
        self._inference_engine = self.get_parameter('inference_engine').value

        if self._inference_engine in ['TFLITE', 'OV']:
            self.get_logger().info(f"Optimizing for {self._inference_engine}")
        else:
            self.get_logger().error(
                f"Inference Engine {self._inference_engine} unknown.")

        self.model_optimizer_service_cb_group = ReentrantCallbackGroup()
        self.model_optimizer_service = \
            self.create_service(ModelOptimizeSrv,
                                constants.MODEL_OPTIMIZER_SERVER_SERVICE_NAME,
                                self.model_optimizer,
                                callback_group=self.model_optimizer_service_cb_group)

        # Heartbeat timer.
        self.timer_count = 0
        self.timer = self.create_timer(5.0, self.timer_callback)

    def timer_callback(self):
        """Heartbeat function to keep the node alive.
        """
        self.get_logger().debug(f"Timer heartbeat {self.timer_count}")
        self.timer_count += 1

    def model_optimizer(self, req, res):
        """Callback for the model_optimizer_server service. Handles calling the model conversion
           API with appropriate parameters set for the specific model details passed in
           the request data.

        Args:
            req (ModelOptimizeSrv.Request): Request object with the model details required to
                                            run the optimizer set.
            res (ModelOptimizeSrv.Response): Response object with error(int) flag to indicate
                                             successful execution of the optimizer script and
                                             artifact_path(str) with the path where the
                                             intermediate representaiton xml files are created
                                             for the model.

        Returns:
            ModelOptimizeSrv.Response: Response object with error(int) flag to indicate
                                       successful execution of the optimizer script and
                                       artifact_path(str) with the path where the intermediate
                                       representaiton xml files are created for the model.
        """
        self.get_logger().info(
            f"Received optimization request for {req.model_name}")
        try:
            aux_param = {"--fuse": "OFF", "--img-format": req.img_format}
            error_code, artifact_path = self.optimize_tf_model(req.model_name,
                                                               req.model_metadata_sensors,
                                                               req.training_algorithm,
                                                               req.width,
                                                               req.height,
                                                               req.lidar_channels,
                                                               aux_param)
            res.error = error_code
            res.artifact_path = artifact_path
        except Exception as ex:
            res.error = 1
            self.get_logger().error(f"Error while optimizing model: {ex}")
        return res

    def prepare_parameters(self,
                           model_name,
                           model_metadata_sensors,
                           training_algorithm,
                           input_width,
                           input_height,
                           lidar_channels,
                           aux_inputs):
        """Helper method that converts the information in model optimizer API into
           the appropriate information through parsing the input.

        Args:
            model_name (str): Model prefix, should be the same in the weight and symbol file.
            model_metadata_sensors (list): List of sensor input types(int) for all the sensors
                                           with which the model was trained.
            training_algorithm (int): Training algorithm key(int) for the algorithm with which
                                      the model was trained.
            input_width (int): Width of the input image to the inference engine.
            input_height (int): Height of the input image to the inference engine.
            lidar_channels (int): Number of LiDAR values that with which the LiDAR head of
                                  the model was trained.
            aux_inputs (dict): Dictionary of auxiliary options for the model optimizer.

        Raises:
            Exception: Custom exception if the API flags and default values are not
                       aligned.
            Exception: Custom exception if the lidar_channel value is less than 1.

        Returns:
            dict: Map of parameters to be passed to model optimizer command based on the model.
        """
        if len(constants.APIFlags.get_list()) != len(constants.APIDefaults.get_list()):
            raise Exception("Inconsistent API flags")
        # Set the flags tot he default values.
        default_param = {}
        for flag, value in zip(constants.APIFlags.get_list(), constants.APIDefaults.get_list()):
            default_param[flag] = value
        # Set param values to the values to the user entered values in aux_inputs.
        for flag, value in aux_inputs.items():
            if flag in default_param:
                default_param[flag] = value

        # Dictionary that will house the cli commands.
        common_params = {}
        # Convert API information into appropriate cli commands.
        for flag, value in default_param.items():
            if flag is constants.APIFlags.MODELS_DIR:
                common_params[constants.ParamKeys.MODEL_PATH] = os.path.join(
                    value, model_name)
            # Input shape is in the for [n,h,w,c] to support tensorflow models only
            elif flag is constants.APIFlags.IMG_CHANNEL:
                common_params[constants.ParamKeys.INPUT_SHAPE] = (constants.ParamKeys.INPUT_SHAPE_FMT
                                                                  .format(1,
                                                                          input_height,
                                                                          input_width,
                                                                          value))
            elif flag is constants.APIFlags.PRECISION:
                if constants.MODEL_OPTIMIZER_VERSION == 2021:
                    common_params[constants.ParamKeys.DATA_TYPE] = value
                else:
                    if value is constants.APIDefaults.PRECISION:
                        common_params["--compress_to_fp16"] = ""
            elif flag is constants.APIFlags.FUSE:
                if value is not constants.APIDefaults.FUSE:
                    if constants.MODEL_OPTIMIZER_VERSION == 2021:
                        common_params[constants.ParamKeys.DISABLE_FUSE] = ""
                        common_params[constants.ParamKeys.DISABLE_GFUSE] = ""
            elif flag is constants.APIFlags.IMG_FORMAT:
                if value is constants.APIDefaults.IMG_FORMAT:
                    common_params[constants.ParamKeys.REV_CHANNELS] = ""
            elif flag is constants.APIFlags.OUT_DIR:
                common_params[constants.ParamKeys.OUT_DIR] = value
            # Only keep entries with non-empty string values.
            elif value:
                common_params[flag] = value

        # Override the input shape and the input flags to handle multi head inputs in tensorflow
        input_shapes = []
        input_names = []
        training_algorithm_key = constants.TrainingAlgorithms(
            training_algorithm)

        for input_type in model_metadata_sensors:
            input_key = constants.SensorInputTypes(input_type)
            if input_key == constants.SensorInputTypes.LIDAR \
               or input_key == constants.SensorInputTypes.SECTOR_LIDAR:
                if lidar_channels < 1:
                    raise Exception("Lidar channels less than 1")
                input_shapes.append(constants.INPUT_SHAPE_FORMAT_MAPPING[input_key]
                                             .format(1, lidar_channels))
            else:
                # Input shape is in the for [n,h,w,c] to support tensorflow models only
                input_shapes.append(
                    constants.INPUT_SHAPE_FORMAT_MAPPING[input_key]
                             .format(1,
                                     input_height,
                                     input_width,
                                     constants.INPUT_CHANNEL_SIZE_MAPPING[input_key]))
            input_name_format = constants.NETWORK_INPUT_FORMAT_MAPPING[input_key]
            input_names.append(
                input_name_format.format(
                    constants.INPUT_HEAD_NAME_MAPPING[training_algorithm_key]))

        if len(input_names) > 0 and len(input_shapes) == len(input_names):
            common_params[constants.ParamKeys.INPUT_SHAPE] = \
                constants.ParamKeys.INPUT_SHAPE_DELIM.join(input_shapes)
            common_params[constants.APIFlags.INPUT] = \
                constants.ParamKeys.INPUT_SHAPE_DELIM.join(input_names)

        common_params[constants.ParamKeys.MODEL_NAME] = model_name
        return common_params

    def run_optimizer_mo(self, mo_path, common_params, platform_parms):
        """Helper method that combines the common commands with the platform specific
           commands.
        Args:
            mo_path (str): Path to intel"s model optimizer for a given platform
                           (mxnet, caffe, or tensor flow).
            common_params (dict): Dictionary containing the cli flags common to all
                                  model optimizer.
            platform_parms (dict): Dictionary containing the cli flags for the specific
                                   platform.

        Raises:
            Exception: Custom exception if the model file is not present.

        Returns:
            tuple: Tuple whose first value is the error code and second value
                   is a string to the location of the converted model if any.
        """
        if not os.path.isfile(common_params[constants.ParamKeys.MODEL_PATH]):
            raise Exception(
                f"Model file {common_params[constants.ParamKeys.MODEL_PATH]} not found")

        # Check if model exists
        if os.path.isfile(os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                       f"{common_params[constants.ParamKeys.MODEL_NAME]}.xml")):
            self.get_logger().info(
                f"Cached model: {common_params[constants.ParamKeys.MODEL_NAME]}.xml")
            return 0, os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                   f"{common_params[constants.ParamKeys.MODEL_NAME]}.xml")

        cmd = f"{mo_path}"
        # Construct the cli command
        for flag, value in dict(common_params, **platform_parms).items():
            cmd += f" {flag} {value}"

        self.get_logger().info(f"Model optimizer command: {cmd}")
        tokenized_cmd = shlex.split(cmd)

        retry_count = 0
        # Retry running the optimizer if it fails due to any error
        # The optimizer command is run for MAX_OPTIMIZER_RETRY_COUNT + 1 times
        while retry_count <= constants.MAX_OPTIMIZER_RETRY_COUNT:
            self.get_logger().info(f"Optimizing model: {retry_count} of "
                                   f"{constants.MAX_OPTIMIZER_RETRY_COUNT} trials")
            proc = subprocess.Popen(tokenized_cmd, stderr=subprocess.PIPE)
            _, std_err = proc.communicate()
            if not proc.returncode:
                return 0, os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                       f"{common_params[constants.ParamKeys.MODEL_NAME]}.xml")
            std_err = re.sub(r", question #\d+", "", std_err.decode("utf-8"))
            self.get_logger().error(f"Model optimizer error info: {std_err}")
            retry_count += 1
        # Return error code 1, which means that the model optimizer failed even after retries.
        return 1, ""

    def run_optimizer_tflite(self, common_params, training_algorithm):
        """Helper method that combines the common commands with the platform specific
           commands.
        Args:
            common_params (dict): Dictionary containing the cli flags common to all
                                  model optimizer.
            training_algorithm (int): Which training algorithm is used.

        Raises:
            Exception: Custom exception if the model file is not present.

        Returns:
            tuple: Tuple whose first value is the error code and second value
                   is a string to the location of the converted model if any.
        """

        # Import Tensorflow if optimizing for TFLITE
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        import tensorflow.compat.v1 as tf

        if not os.path.isfile(common_params[constants.ParamKeys.MODEL_PATH]):
            raise Exception(
                f"Model file {common_params[constants.ParamKeys.MODEL_PATH]} not found")

        # Check if model exists
        if os.path.isfile(os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                       f"{common_params[constants.ParamKeys.MODEL_NAME]}.tflite")):
            self.get_logger().info(
                f"Cached model: {common_params[constants.ParamKeys.MODEL_NAME]}.tflite")
            return 0, os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                   f"{common_params[constants.ParamKeys.MODEL_NAME]}.tflite")

        try:
            with tf.gfile.GFile(common_params[constants.ParamKeys.MODEL_PATH], 'rb') as f:
                graph_def = tf.GraphDef()
                graph_def.ParseFromString(f.read())

            input_shapes = {}
            input_arrays = []
            output = f'main_level/agent/{constants.INPUT_HEAD_NAME_MAPPING[constants.TrainingAlgorithms(training_algorithm)]}/online/network_1/ppo_head_0/policy'

            for i, s in zip(
                    common_params[constants.APIFlags.INPUT].split(
                        constants.ParamKeys.INPUT_SHAPE_DELIM),
                    eval(f'[{common_params[constants.ParamKeys.INPUT_SHAPE]}]')):
                input_shapes[i] = s
                input_arrays.append(i)

            self.get_logger().info(f"Inputs: {str(input_shapes)}")
            self.get_logger().info(f"Output: {output}")

            converter = tf.lite.TFLiteConverter.from_frozen_graph(
                graph_def_file=common_params[constants.ParamKeys.MODEL_PATH],
                input_shapes=input_shapes,
                input_arrays=input_arrays,
                output_arrays=[output]
            )
            converter.allow_custom_ops = True

            if common_params[constants.ParamKeys.DATA_TYPE] == "FP16" or \
                    "--compress_to_fp16" in common_params:
                self.get_logger().info(f"Using float16 quantization.")
                converter.optimizations = [tf.lite.Optimize.DEFAULT]
                converter.target_spec.supported_types = [tf.float16]

            tflite_model = converter.convert()

            with open(os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                   f"{common_params[constants.ParamKeys.MODEL_NAME]}.tflite"), 'wb') as f:
                f.write(tflite_model)

            output_file = os.path.join(common_params[constants.ParamKeys.OUT_DIR],
                                       f"{common_params[constants.ParamKeys.MODEL_NAME]}.tflite")

            self.get_logger().info(f"Created TFLite model: {output_file}")

            return 0, output_file

        except:  # noqa
            # Return error code 1, which means that the model optimizer failed even after retries.
            return 1, ""

    def set_platform_param(self, platform_param, aux_inputs):
        """Helper method that creates a dictionary with the platform specific
           optimizer parameters.

        Args:
            platform_param (dict): Dictionary of available platform cli commands.
            aux_inputs (dict): Dictionary of auxiliary options for the model optimizer.

        Returns:
            dict: Dictionary with platform specific params set if present in aux_inputs.
        """
        self.get_logger().info(f"aux_inputs: {aux_inputs} ")
        set_paltform_params = {}
        for flag in platform_param:
            if flag in aux_inputs:
                set_paltform_params[flag] = aux_inputs[flag]
        return set_paltform_params

    def optimize_tf_model(self,
                          model_name,
                          model_metadata_sensors,
                          training_algorithm,
                          input_width,
                          input_height,
                          lidar_channels,
                          aux_inputs={}):
        """Helper function to run an optimizer for DeepRacer tensorflow model.

        Args:
            model_name (str): Model prefix, should be the same in the weight and symbol file.
            model_metadata_sensors (list): List of sensor input types(int) for all the sensors
                                           with which the model was trained.
            training_algorithm (int): Training algorithm key(int) for the algorithm with which
                                      the model was trained.
            input_width (int): Width of the input image to the inference engine.
            input_height (int): Height of the input image to the inference engine.
            lidar_channels (int): Number of LiDAR values that with which the LiDAR head of
                                  the model was trained.
            aux_inputs (dict, optional): Dictionary of auxiliary options for the model optimizer.
                                         Defaults to {}.

        Raises:
            Exception: Custom exception if the input height or width is less than 1.

        Returns:
            tuple: Tuple whose first value is the error code and second value
                   is a string to the location of the converted model if any.
        """
        if input_width < 1 or input_height < 1:
            raise Exception("Invalid height or width")

        common_params = self.prepare_parameters(model_name,
                                                model_metadata_sensors,
                                                training_algorithm,
                                                input_width,
                                                input_height,
                                                lidar_channels,
                                                aux_inputs)
        # Tensor Flow specific parameters.
        tf_params = {"--input_model_is_text": "",
                     "--offload_unsupported_operations_to_tf": "",
                     "--tensorflow_subgraph_patterns": "",
                     "-tensorflow_operation_patterns": "",
                     "--tensorflow_custom_operations_config_update": "",
                     "--tensorflow_use_custom_operations_config": ""}
        # Add the correct file suffix.
        common_params[constants.ParamKeys.MODEL_PATH] += ".pbtxt" if "--input_model_is_text" in aux_inputs else ".pb"

        if self._inference_engine == "TFLITE":
            return self.run_optimizer_tflite(common_params, training_algorithm)
        else:
            return self.run_optimizer_mo(constants.MODEL_OPTIMIZER_COMMAND, common_params,
                                         self.set_platform_param(tf_params, aux_inputs))


def main(args=None):

    try:
        rclpy.init(args=args)
        model_optimizer_node = ModelOptimizerNode()
        executor = MultiThreadedExecutor()
        rclpy.spin(model_optimizer_node, executor)
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        model_optimizer_node.destroy_node()

    except KeyboardInterrupt:
        pass

    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

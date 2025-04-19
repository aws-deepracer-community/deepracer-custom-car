#!/usr/bin/env python

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
deepracer_navigation_node.py

This module creates the deepracer_navigation_node which is responsible for collecting
the model inference results and mapping it to the servo message with throttle and
steering angle values based on the action space for the particular model selected.

The node defines:
    A subscriber to the /inference_pkg/rl_results topic published
    by the inference_node.
    auto_drive_publisher: A publisher that publishes /deepracer_navigation_pkg/auto_drive
                          messages with the throttle and steering angle values.
    action_space_service: A service that is called when a new model is loaded and
                          helps set the action space to be considered while mapping
                          the inference results.
    throttle_service: A service that is called to dynamically set the scale value to
                      multiply to the throttle in autonomous mode for each action.
"""

import os
import json
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from deepracer_interfaces_pkg.msg import (ServoCtrlMsg,
                                          InferResultsArray)
from deepracer_interfaces_pkg.srv import (LoadModelSrv,
                                          NavThrottleSrv)
from deepracer_navigation_pkg import constants


class DRNavigationNode(Node):
    """Node responsible for converting the output of the RL model and mapping
       it to throttle and steering values.
    """

    def __init__(self):
        """Create a DRNavigationNode.
        """
        super().__init__('deepracer_navigation_node')
        self.get_logger().info("deepracer_navigation_node started")
        # Initialize the listener for inference data
        self.infer_listener()
        # Publisher that sends driving messages to the servo
        # Create a reentrant callback group to publish autonomous drive messages.
        auto_drive_pub_msg_cb_group = ReentrantCallbackGroup()
        self.auto_drive_publisher = self.create_publisher(ServoCtrlMsg,
                                                          constants.AUTO_DRIVE_TOPIC_NAME,
                                                          1)
        # Service for dynamically setting the throttle in autonomous mode
        self.throttle_service_cb_group = ReentrantCallbackGroup()
        self.throttle_service = self.create_service(NavThrottleSrv,
                                                    constants.NAVIGATION_THROTTLE_SERVICE_NAME,
                                                    self.set_throttle_scale_cb,
                                                    callback_group=self.throttle_service_cb_group)
        # Throttle can be set dynamically through the navigation_throttle service
        self.throttle_scale = 0.0
        # Service for setting the action space
        self.action_space_service = self.create_service(LoadModelSrv,
                                                        constants.LOAD_ACTION_SPACE_SERVICE_NAME,
                                                        self.set_action_space_cb)
        # Action space that maps inference results to steering and throttle values
        self.action_space = constants.DEFAULT_ACTION_SPACE
        # Action space type passed as part of model_metadata.json
        self.action_space_type = constants.ActionSpaceTypes.DISCRETE
        # Dictionary that stores the max of the steering and max value of the throttle
        # These values are used to map the action space to valid steering and throttle values
        self.max_action_space_values = {constants.ModelMetadataKeys.STEERING: 0.0,
                                        constants.ModelMetadataKeys.SPEED: 0.0}
        # Coeffiecent for the non linear mapping of the velocity
        self.speed_mapping_coeficients = {'a': 0.0, 'b': 0.0}
        # Set the action value scales for the default space.
        self.set_action_space_scales()
        self.timer_count = 0
        self.timer = self.create_timer(5.0, self.timer_callback)
        self.get_logger().info("DeepRacer navigation node successfully created")

    def timer_callback(self):
        """Heartbeat function to keep the node alive.
        """
        self.get_logger().debug(f"Timer heartbeat {self.timer_count}")
        self.timer_count += 1

    def process_inference_data(self, inference_msg, servo_msg):
        """Helper method that selects the class with highest probability amplitude
           and maps it to angle and throttle.

        Args:
            inference_msg (InferResultsArray): Message containing all relevant
                                               inference data.
            servo (ServoCtrlMsg): Message to be published to the servo with all
                                  relevant servo data.
        """
        # Add the source_stamp header
        servo_msg.source_stamp = inference_msg.images[0].header.stamp
        # Negative value moves the car forward, positive values move the car backwards
        servo_msg.throttle = self.throttle_scale
        try:
            if self.action_space_type == constants.ActionSpaceTypes.DISCRETE:
                max_prob = max(inference_msg.results, key=lambda result: result.class_prob)
                action_id = max_prob.class_label
                servo_msg.angle = self.get_max_scaled_value(self.action_space[action_id]
                                                            [constants.ModelMetadataKeys.STEERING],
                                                            constants.ModelMetadataKeys.STEERING)
                servo_msg.throttle *= self.get_non_linearly_mapped_speed(self.action_space[action_id]
                                                                         [constants.ModelMetadataKeys.SPEED])
            elif self.action_space_type == constants.ActionSpaceTypes.CONTINUOUS:
                action_values = dict()
                for result in inference_msg.results:
                    action_values[int(result.class_label)] = max(min(result.class_prob, 1.0), -1.0)
                scaled_angle = self.scale_continuous_value(action_values[0],
                                                           -1.0,
                                                           1.0,
                                                           self.action_space[constants.ModelMetadataKeys.STEERING]
                                                           [constants.ModelMetadataKeys.CONTINUOUS_LOW],
                                                           self.action_space[constants.ModelMetadataKeys.STEERING]
                                                           [constants.ModelMetadataKeys.CONTINUOUS_HIGH])
                servo_msg.angle = self.get_max_scaled_value(scaled_angle, constants.ModelMetadataKeys.STEERING)
                scaled_throttle = self.scale_continuous_value(action_values[1],
                                                              -1.0,
                                                              1.0,
                                                              self.action_space[constants.ModelMetadataKeys.SPEED]
                                                              [constants.ModelMetadataKeys.CONTINUOUS_LOW],
                                                              self.action_space[constants.ModelMetadataKeys.SPEED]
                                                              [constants.ModelMetadataKeys.CONTINUOUS_HIGH])
                servo_msg.throttle *= self.get_non_linearly_mapped_speed(scaled_throttle)
            else:
                raise Exception("Action space type {} is not supported".format(self.action_space_type))
        except Exception as ex:
            self.get_logger().error("Error while processing data in navigation node: {}".format(ex))
            servo_msg.throttle = 0.0
            servo_msg.angle = 0.0

    def inference_cb(self, inference_msg):
        """Call back for whenever inference data is received.

        Args:
            inference_msg (InferResultsArray): Message containing all relevant inference data.
        """
        servo = ServoCtrlMsg()
        self.process_inference_data(inference_msg, servo)
        self.auto_drive_publisher.publish(servo)

    def infer_listener(self):
        """Method that registers the class to listen to inference results
        """
        self.create_subscription(InferResultsArray,
                                 constants.INFERENCE_PKG_RL_RESULTS_TOPIC,
                                 self.inference_cb,
                                 10)

    def set_throttle_scale_cb(self, req, res):
        """Callback for the navigation_throttle service. Allows clients to dynamically set the
           throttle scale value while the car is in autonomous driving mode.

        Args:
            req (NavThrottleSrv.Request): Request object with the throttle scale value.
            res (NavThrottleSrv.Response): Response object with error(int) flag to indicate
                                           if the service call was successful.

        Returns:
            NavThrottleSrv.Response: Response object with error(int) flag to indicate
                                     if the service call was successful.
        """
        self.throttle_scale = req.throttle
        self.get_logger().info(f"Setting throttle to {req.throttle}")
        res.error = 0
        return res

    def set_action_space_cb(self, req, res):
        """Callback for the load_action_space service, should be called whenever a new
           model is loaded.

        Args:
            req (LoadModelSrv.Request): Request object with the full artifact path to the
                                        loaded model.
            res (LoadModelSrv.Response): Response object with error(int) flag to indicate
                                         if the service call was successful.

        Returns:
            LoadModelSrv.Response: Response object with error(int) flag to indicate
                                   if the service call was successful.
        """
        try:
            model_dir = os.path.dirname(req.artifact_path)
            model_metadata_file = "model_metadata.json"
            with open(os.path.join(model_dir, model_metadata_file), 'r') as meta_file:
                data = json.load(meta_file)
                self.action_space = data['action_space']
                self.get_logger().info(f"Action space loaded: {self.action_space}")
            self.action_space_type = constants.ActionSpaceTypes(req.action_space_type)
            self.validate_action_space()
        except Exception as ex:
            self.action_space = constants.DEFAULT_ACTION_SPACE
            self.action_space_type = constants.ActionSpaceTypes.DISCRETE
            self.get_logger().error(f"Failed to load action space and action space type due to: {ex}")
            res.error = 1
            return res

        self.get_logger().info(f"Setting the action space: {self.action_space} and"
                               f" action space type: {self.action_space_type} ")
        self.set_action_space_scales()
        res.error = 0
        return res

    def validate_action_space(self):
        """Helper method that validates the action space for specific action space type.

        Raises:
            Exception: Raise an exception if the action space values are invalid.
        """
        valid_action_space = True
        if self.action_space_type == constants.ActionSpaceTypes.DISCRETE:
            for action_dict in self.action_space:
                if constants.ModelMetadataKeys.STEERING not in action_dict \
                  or constants.ModelMetadataKeys.SPEED not in action_dict:
                    valid_action_space = False
                    break
        elif self.action_space_type == constants.ActionSpaceTypes.CONTINUOUS:
            if constants.ModelMetadataKeys.STEERING not in self.action_space \
              or constants.ModelMetadataKeys.SPEED not in self.action_space:
                valid_action_space = False
            else:
                steering_action_dict = self.action_space[constants.ModelMetadataKeys.STEERING]
                speed_action_dict = self.action_space[constants.ModelMetadataKeys.SPEED]
                if (constants.ModelMetadataKeys.CONTINUOUS_HIGH not in steering_action_dict
                    or constants.ModelMetadataKeys.CONTINUOUS_LOW not in steering_action_dict
                    or constants.ModelMetadataKeys.CONTINUOUS_HIGH not in speed_action_dict
                    or constants.ModelMetadataKeys.CONTINUOUS_LOW not in speed_action_dict
                    or steering_action_dict[constants.ModelMetadataKeys.CONTINUOUS_HIGH]
                        <= steering_action_dict[constants.ModelMetadataKeys.CONTINUOUS_LOW]
                    or speed_action_dict[constants.ModelMetadataKeys.CONTINUOUS_HIGH]
                        <= speed_action_dict[constants.ModelMetadataKeys.CONTINUOUS_LOW]):
                    valid_action_space = False
        if not valid_action_space:
            raise Exception(f"Incorrect action space values: {self.action_space}")

    def set_action_space_scales(self):
        """Helper method that finds the the maximum action values for the action space and stores them.
           The maximum speed value is also used to update the speed mapping coefficients.
        """
        try:
            if self.action_space_type == constants.ActionSpaceTypes.DISCRETE:
                self.max_action_space_values[constants.ModelMetadataKeys.STEERING] = \
                    abs(max(self.action_space,
                            key=lambda action:
                        abs(action[constants.ModelMetadataKeys.STEERING]))
                        [constants.ModelMetadataKeys.STEERING])
                self.max_action_space_values[constants.ModelMetadataKeys.SPEED] = \
                    abs(max(self.action_space,
                            key=lambda action:
                            abs(action[constants.ModelMetadataKeys.SPEED]))
                        [constants.ModelMetadataKeys.SPEED])
            elif self.action_space_type == constants.ActionSpaceTypes.CONTINUOUS:
                self.max_action_space_values[constants.ModelMetadataKeys.STEERING] = \
                    self.action_space[constants.ModelMetadataKeys.STEERING][constants.ModelMetadataKeys.CONTINUOUS_HIGH]
                self.max_action_space_values[constants.ModelMetadataKeys.SPEED] = \
                    self.action_space[constants.ModelMetadataKeys.SPEED][constants.ModelMetadataKeys.CONTINUOUS_HIGH]
            else:
                raise(f"Incorrect action space type: {self.action_space_type}")
            # This is the solution to a*x**2 + b*x for the two points in DEFAULT_SPEED_SCALES
            self.speed_mapping_coeficients['a'] = \
                (1.0 / self.max_action_space_values[constants.ModelMetadataKeys.SPEED]**2) * \
                (2.0 * constants.DEFAULT_SPEED_SCALES[0] - 4.0 * constants.DEFAULT_SPEED_SCALES[1])
            self.speed_mapping_coeficients['b'] = \
                (1.0 / self.max_action_space_values[constants.ModelMetadataKeys.SPEED]) * \
                (4.0 * constants.DEFAULT_SPEED_SCALES[1] - constants.DEFAULT_SPEED_SCALES[0])

            self.get_logger().info(f"Action space scale set: {self.max_action_space_values} \n"
                                   f" Mapping equation params a: {self.speed_mapping_coeficients['a']}"
                                   f" b: {self.speed_mapping_coeficients['b']}")
        except Exception as ex:
            self.get_logger().error(f"Unable to detect action space scale: {ex}")

    def get_max_scaled_value(self, action_value, action_key):
        """Helper method that scales the action value based on the maximum value in the
           action space.

        Args:
            action_value (float): steering angle or speed value
            action_key (string): steering_angle or speed

        Returns:
            float: scaled action value between [0.0, 1.0]
        """
        try:
            max_value = self.max_action_space_values[action_key]
            if max_value <= 0.0:
                self.get_logger().error(f"Invalid {action_key} value {max_value}")
                return 0.0
            return float(action_value) / float(max_value)
        except Exception as ex:
            self.get_logger().error(f"Unable to scale the action value {action_key}: {ex}")
            return 0.0

    def get_non_linearly_mapped_speed(self, scaled_action_space_speed):
        """Helper method that non linearly maps the scaled speed value to a value passed
           as part of the servo message calculated as a solution to the formula y = ax^2 + bx.
           Where a and b are the coffecients in the equation of a parabola (y = ax^2 + bx) passing
           through the points [0, 0], [maximum_speed/2, 0.8] and [maximum_speed, 1.0].

        Args:
            scaled_action_space_speed (float): scaled action space speed

        Returns:
            float: non linearly mapped speed value between [0.0, 1.0]
        """
        mapped_speed = self.speed_mapping_coeficients['a'] * scaled_action_space_speed**2 + \
            self.speed_mapping_coeficients['b'] * scaled_action_space_speed
        return max(min(mapped_speed, 1.0), -1.0)

    def scale_continuous_value(self, action, min_old, max_old, min_new, max_new):
        """Helper method that return the scaled continuous action space values
           from min_old, max_old to min_new, max_new.

        Args:
            action (float): The action value to be scaled
            min_old (float): The minimum bound value before scaling
            max_old (float): The maximum bound value before scaling
            min_new (float): The minimum bound value after scaling
            max_new (float): The maximum bound value after scaling

        Returns:
            (float): scaled action value
        """
        if max_old == min_old:
            self.get_logger().error("Unsupported minimum and maximum action space bounds for scaling values. \
                min_old: {}; max_old: {}".format(min_old, max_old))
        return ((max_new - min_new) / (max_old - min_old)) * (action - min_old) + min_new


def main(args=None):
    try:
        rclpy.init(args=args)
        dr_navigation_node = DRNavigationNode()
        executor = MultiThreadedExecutor()
        rclpy.spin(dr_navigation_node, executor)

        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        dr_navigation_node.destroy_node()

    except KeyboardInterrupt:
        pass
    
    finally:
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()

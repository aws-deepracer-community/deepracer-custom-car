#!/usr/bin/env python3

import os
import re
import sys
import json 

#################################################################################
#   Copyright AWS DeepRacer Community. All Rights Reserved.                     #
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

import os
from enum import Enum

class SensorInputKeys(Enum):
    """Enum mapping sensor inputs keys(str) passed in model_metadata.json to int values,
       as we add sensors we should add inputs. This is also important for networks
       with more than one input.
    """
    observation = 1
    LIDAR = 2
    SECTOR_LIDAR = 3
    LEFT_CAMERA = 4
    FRONT_FACING_CAMERA = 5
    STEREO_CAMERAS = 6

    @classmethod
    def has_member(cls, input_key):
        """Check if the input_key passed as parameter is one of the class members.

        Args:
            input_key (str): String containing sensor input key to check.

        Returns:
            bool: Returns True if the sensor input key is supported, False otherwise.
        """
        return input_key in cls.__members__


class TrainingAlgorithms(Enum):
    """Enum mapping training algorithm value passed in model_metadata.json to int values.
    """
    clipped_ppo = 1
    sac = 2

    @classmethod
    def has_member(cls, training_algorithm):
        """Check if the training_algorithm passed as parameter is one of the class members.

        Args:
            training_algorithm (str): String containing training algorithm to check.

        Returns:
            bool: Returns True if the training algorithm is supported, False otherwise.
        """
        return training_algorithm in cls.__members__


class ModelMetadataKeys():
    """Class with keys in the model metadata.json
    """
    SENSOR = "sensor"
    LIDAR_CONFIG = "lidar_config"
    TRAINING_ALGORITHM = "training_algorithm"
    NUM_LIDAR_SECTORS = "num_sectors"
    USE_LIDAR = "use_lidar"


# Default Lidar configuration values
DEFAULT_LIDAR_CONFIG = {
    # Number of lidar sectors to feed into network
    ModelMetadataKeys.NUM_LIDAR_SECTORS: 64,
}

# Default Sector Lidar configuration values
DEFAULT_SECTOR_LIDAR_CONFIG = {
    # Number of lidar sectors to feed into network
    ModelMetadataKeys.NUM_LIDAR_SECTORS: 8
}


class SensorInputTypes(Enum):
    """Enum listing the sensors input types supported; as we add sensors we should add
       inputs. This is also important for networks with more than one input.
    """
    OBSERVATION = 1
    LIDAR = 2
    SECTOR_LIDAR = 3
    LEFT_CAMERA = 4
    FRONT_FACING_CAMERA = 5
    STEREO_CAMERAS = 6


# Mapping between the training algorithm and input head network names.
INPUT_HEAD_NAME_MAPPING = {
    TrainingAlgorithms.clipped_ppo: "main",
    TrainingAlgorithms.sac: "policy"
}


# Mapping between input names formats in the network for each input head.
# This will be used during model optimizer and model inference.
NETWORK_INPUT_FORMAT_MAPPING = {
    SensorInputTypes.OBSERVATION: "main_level/agent/{}/online/network_0/observation/observation",
    SensorInputTypes.LIDAR: "main_level/agent/{}/online/network_0/LIDAR/LIDAR",
    SensorInputTypes.SECTOR_LIDAR: "main_level/agent/{}/online/network_0/SECTOR_LIDAR/SECTOR_LIDAR",
    SensorInputTypes.LEFT_CAMERA: "main_level/agent/{}/online/network_0/LEFT_CAMERA/LEFT_CAMERA",
    SensorInputTypes.FRONT_FACING_CAMERA: "main_level/agent/{}/online/network_0/FRONT_FACING_CAMERA/FRONT_FACING_CAMERA",
    SensorInputTypes.STEREO_CAMERAS: "main_level/agent/{}/online/network_0/STEREO_CAMERAS/STEREO_CAMERAS"
}


# Mapping input channel size in the network for each input head except lidar.
INPUT_CHANNEL_SIZE_MAPPING = {
    SensorInputTypes.OBSERVATION: 1,
    SensorInputTypes.LEFT_CAMERA: 1,
    SensorInputTypes.FRONT_FACING_CAMERA: 1,
    SensorInputTypes.STEREO_CAMERAS: 2
}


# Mapping input shape format in the network for each input head.
# This will be used during model optimizer and model inference.
INPUT_SHAPE_FORMAT_MAPPING = {
    SensorInputTypes.OBSERVATION: "[{},{},{},{}]",
    SensorInputTypes.LIDAR: "[{},{}]",
    SensorInputTypes.SECTOR_LIDAR: "[{},{}]",
    SensorInputTypes.LEFT_CAMERA: "[{},{},{},{}]",
    SensorInputTypes.FRONT_FACING_CAMERA: "[{},{},{},{}]",
    SensorInputTypes.STEREO_CAMERAS: "[{},{},{},{}]"
}


class MultiHeadInputKeys(object):
    """Class to store keys required to enable multi head inputs.
    """
    INPUT_HEADS = "--input-names"
    INPUT_CHANNELS = "--input-channels"


class MOKeys(object):
    """Class that statically stores Intel"s model optimizer cli flags. Order doesnot matter.
    """
    MODEL_PATH = "--input_model"
    MODEL_NAME = "--model_name"
    DATA_TYPE = "--data_type"
    DISABLE_FUSE = "--disable_fusing"
    DISABLE_GFUSE = "--disable_gfusing"
    REV_CHANNELS = "--reverse_input_channels"
    OUT_DIR = "--output_dir"
    INPUT_SHAPE = "--input_shape"
    INPUT_SHAPE_DELIM = ","
    INPUT_SHAPE_FMT = "[{},{},{},{}]"


class APIFlags(object):
    """Class for storing API flags, get_list method order must match the APIDefaults
       get list method.
    """
    MODELS_DIR = "--models-dir"
    OUT_DIR = "--output-dir"
    IMG_FORMAT = "--img-format"
    IMG_CHANNEL = "--img-channels"
    PRECISION = "--precision"
    FUSE = "--fuse"
    SCALE = "--scale"
    INPUT = "--input"
    OUTPUT = "--output"
    MEAN_VAL = "--mean_values"
    EXT = "--extensions"

    @staticmethod
    def get_list():
        """Static method returns an ordered list of available model optimizer API flags,
           this list should maintain the same order as the get_list method of the
           APIDefaults class.

        Returns:
            list: List of class variable values.
        """
        return [APIFlags.MODELS_DIR, APIFlags.OUT_DIR, APIFlags.IMG_FORMAT, APIFlags.IMG_CHANNEL,
                APIFlags.PRECISION, APIFlags.FUSE, APIFlags.SCALE, APIFlags.INPUT,
                APIFlags.OUTPUT, APIFlags.MEAN_VAL, APIFlags.EXT]


class APIDefaults(object):
    """Class for storing API default values, get_list method order must match the APIFlags
       get list method.
    """
    MODELS_DIR = "/opt/aws/deepracer/artifacts"
    OUT_DIR = "/opt/aws/deepracer/artifacts"
    IMG_FORMAT = "BGR"
    IMG_CHANNEL = 3
    PRECISION = "FP16"
    FUSE = "ON"
    SCALE = 1
    INPUT = ""
    OUTPUT = ""
    MEAN_VAL = ""
    EXT = ""

    @staticmethod
    def get_list():
        """Static method returns an ordered list of available model optimizer API flag defaults,
           this list should maintain the same order as the get_list method of the
           APIFlags class.

        Returns:
            list: List of class variable values.
        """
        return [APIDefaults.MODELS_DIR, APIDefaults.OUT_DIR, APIDefaults.IMG_FORMAT,
                APIDefaults.IMG_CHANNEL, APIDefaults.PRECISION, APIDefaults.FUSE,
                APIDefaults.SCALE, APIDefaults.INPUT, APIDefaults.OUTPUT,
                APIDefaults.MEAN_VAL, APIDefaults.EXT]

def read_model_metadata_file(model_metatdata_file):
    """Helper method that reads the model metadata file for the model selected.

    Args:
        model_metatdata_file (str): Path to the model_metadata file.

    Returns:
        tuple: Tuple of (error_code, error_message, json object
               read from model_metadata.json file).
    """
    try:
        err_msg = ""
        if(not os.path.isfile(model_metatdata_file)):
            err_msg = "No model_metadata_file for the model selected"
            return 1, err_msg, {}
        with open(model_metatdata_file) as json_file:
            data = json.load(json_file)

        return 0, err_msg, data
    except Exception as exc:
        return 1, f"Error while reading model_metadata.json: {exc}", {}


def get_sensors(model_metatdata_json):
    """Helper method that returns the corresponding enum values for sensors in the
       model_metadata json of the model selected.

    Args:
        model_metatdata_json (dict): JSON object with contents of the model metadata file.

    Returns:
        tuple: Tuple of (error_code, error_message, list of integer values
               corresponding the sensors of the model).
    """
    try:
        sensors = None
        err_msg = ""
        if ModelMetadataKeys.SENSOR in model_metatdata_json:
            sensor_names = set(model_metatdata_json[ModelMetadataKeys.SENSOR])
            if all([SensorInputKeys.has_member(sensor_name) for sensor_name in sensor_names]):
                sensors = [SensorInputKeys[sensor_name].value for sensor_name in sensor_names]
            else:
                return 2, "The sensor configurations of your vehicle and trained model must match", []
        else:
            # To handle DeepRacer models with no sensor key
            err_msg = "No sensor key in model_metadata_file. Defaulting to observation."
            sensors = [SensorInputKeys.observation.value]

        return 0, err_msg, sensors
    except Exception as exc:
        return 1, f"Error while getting sensor names from model_metadata.json: {exc}", []


def get_training_algorithm(model_metatdata_json):
    """Helper method that returns the corresponding enum value for the training algorithm in the
       model_metadata json of the model selected.

    Args:
        model_metatdata_json (dict): JSON object with contents of the model metadata file.

    Return
        tuple: Tuple of (error_code, error_message, integer value
               corresponding the training algorithm of the model).
    """
    try:
        training_algorithm = None
        err_msg = ""
        if ModelMetadataKeys.TRAINING_ALGORITHM in model_metatdata_json:
            training_algorithm_value = model_metatdata_json[ModelMetadataKeys.TRAINING_ALGORITHM]
            if TrainingAlgorithms.has_member(training_algorithm_value):
                training_algorithm = TrainingAlgorithms[training_algorithm_value]
            else:
                return 2, "The training algorithm value is incorrect", ""
        else:
            # To handle DeepRacer models with no training_algorithm key
            print("No training algorithm key in model_metadata_file. Defaulting to clipped_ppo.")
            training_algorithm = TrainingAlgorithms.clipped_ppo.value

        return 0, err_msg, training_algorithm
    except Exception as exc:
        return 1, f"Error while getting training algorithm model_metadata.json: {exc}", ""


def load_lidar_configuration(sensors, model_metadata):
    """Helper method to load the LiDAR configuration based on type of
       preprocessing done on the LiDAR data duringthe model training.

    Args:
        sensors (list): List of integers corresponding to the sensor enum values
                        for the trained model.
        model_metadata (dict): JSON object with contents of the model metadata file.

    Returns:
        tuple: Tuple of (error_code, error_message, dictionary with model lidar configuration
               corresponding the preprocessing done on LiDAR data during model training).
    """
    try:
        # Set default values in case the 'lidar configuration' is not defined in model_metadata.json
        model_lidar_config = DEFAULT_LIDAR_CONFIG
        # Set default values for SECTOR_LIDAR if this sensor is used
        if SensorInputKeys.SECTOR_LIDAR in sensors:
            model_lidar_config = DEFAULT_SECTOR_LIDAR_CONFIG
        model_lidar_config[
            ModelMetadataKeys.USE_LIDAR
        ] = sensors and (SensorInputKeys.LIDAR in sensors
                         or SensorInputKeys.SECTOR_LIDAR in sensors)
        # Load the lidar configuration if the model uses lidar and has custom lidar configurations
        if model_lidar_config[ModelMetadataKeys.USE_LIDAR] \
           and ModelMetadataKeys.LIDAR_CONFIG in model_metadata:
            lidar_config = model_metadata[ModelMetadataKeys.LIDAR_CONFIG]
            model_lidar_config[
                ModelMetadataKeys.NUM_LIDAR_SECTORS
            ] = lidar_config[ModelMetadataKeys.NUM_LIDAR_SECTORS]
        return 0, "", model_lidar_config
    except Exception as exc:
        return 1, f"Unable to connect to device with current LiDAR configuration: {exc}", {}



def define_params(model_name,
                  model_metadata_sensors,
                  training_algorithm,
                  input_width,
                  input_height,
                  lidar_channels,
                  aux_inputs):

    aux_inputs = {}
    common_params = {}

    default_param = {}
    for flag, value in zip(APIFlags.get_list(), APIDefaults.get_list()):
        default_param[flag] = value
    # Set param values to the values to the user entered values in aux_inputs.
    for flag, value in aux_inputs.items():
        if flag in default_param:
            default_param[flag] = value

    for flag, value in default_param.items():
        if flag is APIFlags.MODELS_DIR:
            common_params[MOKeys.MODEL_PATH] = os.path.join(value, model_name)
        # Input shape is in the for [n,h,w,c] to support tensorflow models only
        elif flag is APIFlags.IMG_CHANNEL:
            common_params[MOKeys.INPUT_SHAPE] = (MOKeys.INPUT_SHAPE_FMT
                                                 .format(1,
                                                         input_height,
                                                         input_width,
                                                         value))
        elif flag is APIFlags.PRECISION:
            common_params[MOKeys.DATA_TYPE] = value
        elif flag is APIFlags.FUSE:
            if value is not APIDefaults.FUSE:
                common_params[MOKeys.DISABLE_FUSE] = ""
                common_params[MOKeys.DISABLE_GFUSE] = ""
        elif flag is APIFlags.IMG_FORMAT:
            if value is APIDefaults.IMG_FORMAT:
                common_params[MOKeys.REV_CHANNELS] = ""
        elif flag is APIFlags.OUT_DIR:
            common_params[MOKeys.OUT_DIR] = value
        # Only keep entries with non-empty string values.
        elif value:
            common_params[flag] = value

    # Override the input shape and the input flags to handle multi head inputs in tensorflow
    input_shapes = []
    input_names = []
    training_algorithm_key = TrainingAlgorithms(training_algorithm)

    for input_type in model_metadata_sensors:
        input_key = SensorInputTypes(input_type)
        if input_key == SensorInputTypes.LIDAR \
                or input_key == SensorInputTypes.SECTOR_LIDAR:
            if lidar_channels < 1:
                raise Exception("Lidar channels less than 1")
            input_shapes.append(INPUT_SHAPE_FORMAT_MAPPING[input_key]
                                .format(1, lidar_channels))
        else:
            # Input shape is in the for [n,h,w,c] to support tensorflow models only
            input_shapes.append(
                INPUT_SHAPE_FORMAT_MAPPING[input_key]
                .format(1,
                        input_height,
                        input_width,
                        INPUT_CHANNEL_SIZE_MAPPING[input_key]))
        input_name_format = NETWORK_INPUT_FORMAT_MAPPING[input_key]
        input_names.append(
            input_name_format.format(
                INPUT_HEAD_NAME_MAPPING[training_algorithm_key]))

    if len(input_names) > 0 and len(input_shapes) == len(input_names):
        common_params[MOKeys.INPUT_SHAPE] = \
            MOKeys.INPUT_SHAPE_DELIM.join(input_shapes)
        common_params[APIFlags.INPUT] = \
            MOKeys.INPUT_SHAPE_DELIM.join(input_names)

    common_params[MOKeys.MODEL_NAME] = model_name
    return common_params


def main(args=None):
    n = len(sys.argv)
    if n != 2:
        print("Wrong number of arguments. Exiting.")
        exit(1)

    dir = sys.argv[1]
    if not os.path.isdir(dir):
        print(f"Error: {dir} is not a directory.")
        exit(1)

    model_file = os.path.join(dir, "model.pb")

    _, _, model_metadata_file = read_model_metadata_file(f"{dir}/model_metadata.json")
    _, _, sensors = get_sensors(model_metadata_file)
    _, _, training_algorithm = get_training_algorithm(model_metadata_file)
    _, _, lidar_config = load_lidar_configuration(sensors, model_metadata_file)

    params = define_params(model_file, sensors, training_algorithm, 160, 120, lidar_config['num_sectors'], {} )

    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    import tensorflow.compat.v1 as tf

    with tf.gfile.GFile(model_file, 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())

    input_shapes={}
    input_arrays=[]

    for i, s in zip(params[APIFlags.INPUT].split(MOKeys.INPUT_SHAPE_DELIM), eval(f'[{params[MOKeys.INPUT_SHAPE]}]')):
        input_shapes[i] = s
        input_arrays.append(i)
    
    print("Inputs: " + str(input_shapes))

    converter = tf.lite.TFLiteConverter.from_frozen_graph(
        graph_def_file=model_file,
        input_shapes=input_shapes,
        input_arrays=input_arrays,
        output_arrays=[f'main_level/agent/{INPUT_HEAD_NAME_MAPPING[TrainingAlgorithms(training_algorithm)]}/online/network_1/ppo_head_0/policy']
    )
    converter.allow_custom_ops = True
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]    
    tflite_model = converter.convert()

    with open(os.path.join(dir,"model.tflite"), 'wb') as f:
        f.write(tflite_model)


if __name__ == "__main__":
    main()

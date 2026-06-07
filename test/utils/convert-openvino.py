#!/usr/bin/env python3

import os
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

from enum import Enum


class SensorInputKeys(Enum):
    observation = 1
    LIDAR = 2
    SECTOR_LIDAR = 3
    LEFT_CAMERA = 4
    FRONT_FACING_CAMERA = 5
    STEREO_CAMERAS = 6

    @classmethod
    def has_member(cls, input_key):
        return input_key in cls.__members__


class TrainingAlgorithms(Enum):
    clipped_ppo = 1
    sac = 2

    @classmethod
    def has_member(cls, training_algorithm):
        return training_algorithm in cls.__members__


class ModelMetadataKeys():
    SENSOR = "sensor"
    LIDAR_CONFIG = "lidar_config"
    TRAINING_ALGORITHM = "training_algorithm"
    NUM_LIDAR_SECTORS = "num_sectors"
    USE_LIDAR = "use_lidar"


DEFAULT_LIDAR_CONFIG = {
    ModelMetadataKeys.NUM_LIDAR_SECTORS: 64,
}

DEFAULT_SECTOR_LIDAR_CONFIG = {
    ModelMetadataKeys.NUM_LIDAR_SECTORS: 8
}


class SensorInputTypes(Enum):
    OBSERVATION = 1
    LIDAR = 2
    SECTOR_LIDAR = 3
    LEFT_CAMERA = 4
    FRONT_FACING_CAMERA = 5
    STEREO_CAMERAS = 6


INPUT_HEAD_NAME_MAPPING = {
    TrainingAlgorithms.clipped_ppo: "main",
    TrainingAlgorithms.sac: "policy"
}

NETWORK_INPUT_FORMAT_MAPPING = {
    SensorInputTypes.OBSERVATION: "main_level/agent/{}/online/network_0/observation/observation",
    SensorInputTypes.LIDAR: "main_level/agent/{}/online/network_0/LIDAR/LIDAR",
    SensorInputTypes.SECTOR_LIDAR: "main_level/agent/{}/online/network_0/SECTOR_LIDAR/SECTOR_LIDAR",
    SensorInputTypes.LEFT_CAMERA: "main_level/agent/{}/online/network_0/LEFT_CAMERA/LEFT_CAMERA",
    SensorInputTypes.FRONT_FACING_CAMERA: "main_level/agent/{}/online/network_0/FRONT_FACING_CAMERA/FRONT_FACING_CAMERA",
    SensorInputTypes.STEREO_CAMERAS: "main_level/agent/{}/online/network_0/STEREO_CAMERAS/STEREO_CAMERAS"
}

INPUT_CHANNEL_SIZE_MAPPING = {
    SensorInputTypes.OBSERVATION: 1,
    SensorInputTypes.LEFT_CAMERA: 1,
    SensorInputTypes.FRONT_FACING_CAMERA: 1,
    SensorInputTypes.STEREO_CAMERAS: 2
}


def read_model_metadata_file(model_metadata_file):
    try:
        if not os.path.isfile(model_metadata_file):
            return 1, "No model_metadata_file for the model selected", {}
        with open(model_metadata_file) as json_file:
            data = json.load(json_file)
        return 0, "", data
    except Exception as exc:
        return 1, f"Error while reading model_metadata.json: {exc}", {}


def get_sensors(model_metadata_json):
    try:
        sensors = None
        err_msg = ""
        if ModelMetadataKeys.SENSOR in model_metadata_json:
            sensor_names = set(model_metadata_json[ModelMetadataKeys.SENSOR])
            if all([SensorInputKeys.has_member(s) for s in sensor_names]):
                sensors = [SensorInputKeys[s].value for s in sensor_names]
            else:
                return 2, "The sensor configurations of your vehicle and trained model must match", []
        else:
            err_msg = "No sensor key in model_metadata_file. Defaulting to observation."
            sensors = [SensorInputKeys.observation.value]
        return 0, err_msg, sensors
    except Exception as exc:
        return 1, f"Error while getting sensor names from model_metadata.json: {exc}", []


def get_training_algorithm(model_metadata_json):
    try:
        training_algorithm = None
        err_msg = ""
        if ModelMetadataKeys.TRAINING_ALGORITHM in model_metadata_json:
            training_algorithm_value = model_metadata_json[ModelMetadataKeys.TRAINING_ALGORITHM]
            if TrainingAlgorithms.has_member(training_algorithm_value):
                training_algorithm = TrainingAlgorithms[training_algorithm_value]
            else:
                return 2, "The training algorithm value is incorrect", ""
        else:
            print("No training algorithm key in model_metadata_file. Defaulting to clipped_ppo.")
            training_algorithm = TrainingAlgorithms.clipped_ppo
        return 0, err_msg, training_algorithm
    except Exception as exc:
        return 1, f"Error while getting training algorithm from model_metadata.json: {exc}", ""


def load_lidar_configuration(sensors, model_metadata):
    try:
        model_lidar_config = DEFAULT_LIDAR_CONFIG.copy()
        if SensorInputKeys.SECTOR_LIDAR.value in sensors:
            model_lidar_config = DEFAULT_SECTOR_LIDAR_CONFIG.copy()
        model_lidar_config[ModelMetadataKeys.USE_LIDAR] = sensors and (
            SensorInputKeys.LIDAR.value in sensors
            or SensorInputKeys.SECTOR_LIDAR.value in sensors
        )
        if model_lidar_config[ModelMetadataKeys.USE_LIDAR] \
                and ModelMetadataKeys.LIDAR_CONFIG in model_metadata:
            lidar_config = model_metadata[ModelMetadataKeys.LIDAR_CONFIG]
            model_lidar_config[ModelMetadataKeys.NUM_LIDAR_SECTORS] = \
                lidar_config[ModelMetadataKeys.NUM_LIDAR_SECTORS]
        return 0, "", model_lidar_config
    except Exception as exc:
        return 1, f"Unable to load LiDAR configuration: {exc}", {}


def build_inputs(sensors, training_algorithm, input_width, input_height, lidar_channels):
    """Build the list of (input_name, shape) tuples for OVC.

    Returns:
        list: List of (name, shape) tuples suitable for openvino.convert_model's
              ``input`` parameter.
    """
    input_head = INPUT_HEAD_NAME_MAPPING[training_algorithm]
    inputs = []

    for sensor_value in sensors:
        input_key = SensorInputTypes(sensor_value)
        name = NETWORK_INPUT_FORMAT_MAPPING[input_key].format(input_head)

        if input_key in (SensorInputTypes.LIDAR, SensorInputTypes.SECTOR_LIDAR):
            if lidar_channels < 1:
                raise ValueError("Lidar channels must be >= 1")
            shape = [1, lidar_channels]
        else:
            channels = INPUT_CHANNEL_SIZE_MAPPING[input_key]
            shape = [1, input_height, input_width, channels]

        inputs.append((name, shape))

    return inputs


def main(args=None):
    if len(sys.argv) != 2:
        print("Usage: convert-openvino.py <model_dir>")
        sys.exit(1)

    dir_path = sys.argv[1]
    if not os.path.isdir(dir_path):
        print(f"Error: {dir_path} is not a directory.")
        sys.exit(1)

    model_file = os.path.join(dir_path, "model.pb")
    if not os.path.isfile(model_file):
        print(f"Error: model.pb not found in {dir_path}")
        sys.exit(1)

    _, _, model_metadata = read_model_metadata_file(os.path.join(dir_path, "model_metadata.json"))
    _, _, sensors = get_sensors(model_metadata)
    _, _, training_algorithm = get_training_algorithm(model_metadata)
    _, _, lidar_config = load_lidar_configuration(sensors, model_metadata)

    # training_algorithm may be returned as enum value (int) or as enum member
    if isinstance(training_algorithm, int):
        training_algorithm = TrainingAlgorithms(training_algorithm)

    lidar_channels = lidar_config.get(ModelMetadataKeys.NUM_LIDAR_SECTORS, 64)
    inputs = build_inputs(sensors, training_algorithm, 160, 120, lidar_channels)

    output_node = (
        f"main_level/agent/{INPUT_HEAD_NAME_MAPPING[training_algorithm]}"
        "/online/network_1/ppo_head_0/policy"
    )

    print("Inputs:")
    for name, shape in inputs:
        print(f"  {name}: {shape}")
    print(f"Output: {output_node}")

    import openvino as ov

    # First pass: convert without constraints to discover actual node names.
    # TF frozen graphs expose inputs with a ':0' suffix that OVC requires.
    print("Inspecting model to detect actual input/output names ...")
    temp_model = ov.convert_model(model_file)
    detected_inputs = [inp.get_any_name() for inp in temp_model.inputs]
    detected_outputs = [out.get_any_name() for out in temp_model.outputs]
    print(f"Detected inputs:  {detected_inputs}")
    print(f"Detected outputs: {detected_outputs}")

    # Match detected input names (may have ':0') to our expected names by prefix
    input_specs = []
    for (name, shape) in inputs:
        matched = next((d for d in detected_inputs if d.startswith(name)), None)
        if matched is None:
            print(f"Warning: could not match input '{name}', using as-is")
            matched = name
        input_specs.append((matched, shape))

    # Match the output node (may have ':0')
    output_spec = next((d for d in detected_outputs if d.startswith(output_node)), None)
    if output_spec is None:
        print(f"Warning: could not match output '{output_node}', using first detected: {detected_outputs[0]}")
        output_spec = detected_outputs[0]

    print(f"Using input specs: {input_specs}")
    print(f"Using output spec: {output_spec}")

    print("Converting model with OpenVINO Model Converter (OVC) ...")
    ov_model = ov.convert_model(
        model_file,
        input=input_specs,
        output=output_spec,
    )

    output_xml = os.path.join(dir_path, "model.xml")
    ov.save_model(ov_model, output_xml, compress_to_fp16=True)
    print(f"Saved OpenVINO IR model to {output_xml} (FP16 compressed)")


if __name__ == "__main__":
    main()

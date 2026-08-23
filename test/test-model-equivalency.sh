#!/usr/bin/env bash
set -e

export DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# Remove warnings
export PYTHONWARNINGS="ignore::DeprecationWarning,ignore:::setuptools.command.install"

# Prevent CUDA from kicking in
export CUDA_VISIBLE_DEVICES=""

options='m:i:f:r'
while getopts $options option
do
    case "$option" in
        i  ) IMG_DIR=$OPTARG;;
        m  ) MODEL_DIR=$OPTARG;;
        f  ) FPS=$OPTARG;;
        r  ) REGEN=1;;
        \? ) echo "Unknown option: -$OPTARG" >&2; exit 1;;
        :  ) echo "Missing option argument for -$OPTARG" >&2; exit 1;;
        *  ) echo "Unimplemented option: -$option" >&2; exit 1;;
    esac
done

if [ -z "$IMG_DIR" ] || [ -z "$MODEL_DIR" ]; then
    echo "Missing -i, -m" >&2
    exit 1
fi

# Default FPS to 10 if not provided
FPS=${FPS:-10}

source /opt/ros/jazzy/setup.bash

if [ -f $DIR/../install/setup.bash ]; then
    echo "Using DeepRacer bundle from $DIR/../install/setup.bash"
    source $DIR/../install/setup.bash
elif [ -f /opt/aws/deepracer/lib/setup.bash ]; then
    echo "Using DeepRacer bundle from /opt/aws/deepracer/lib/setup.bash"
    source /opt/aws/deepracer/lib/setup.bash
fi

cd $DIR
rosdep update --rosdistro=jazzy -q
colcon build

if [ -n "$REGEN" ]; then
    echo "Regenerating TFLite model in $MODEL_DIR ..."
    python3 "$DIR/utils/convert-tflite.py" "$MODEL_DIR"
    echo "Regenerating OpenVINO model in $MODEL_DIR ..."
    python3 "$DIR/utils/convert-openvino.py" "$MODEL_DIR"
fi

source $DIR/install/setup.bash
ros2 launch $DIR/launch/inference_comparison_test.launch.py image_dir:=$IMG_DIR model_dir:=$MODEL_DIR fps:=$FPS

# Summarize the most recently written results file
RESULTS=$(ls -t "$IMG_DIR"/results-*.json 2>/dev/null | head -1)
if [ -n "$RESULTS" ]; then
    python3 "$DIR/utils/summarize-results.py" "$RESULTS"
else
    echo "No results file found in $IMG_DIR" >&2
fi
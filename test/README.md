# DeepRacer Model Equivalency Test

Runs three inference engines against the same image frames and compares their outputs:

| Engine | Implementation |
|--------|---------------|
| **TFLite** | `inference_pkg` with `TFLITE` engine — uses XNNPACK delegate |
| **OpenVINO** | `inference_pkg` with `OV` engine — uses OVC-converted IR model |
| **TF (native)** | Internal `tf.Session` on the original frozen graph (`model.pb`) |

---

## Prerequisites

The following files must exist inside your model directory:

| File | How to create |
|------|---------------|
| `model.pb` | Original frozen TensorFlow graph (from DeepRacer training) |
| `model_metadata.json` | Training metadata (sensors, algorithm, action space) |
| `model.tflite` | `python3 utils/convert-tflite.py <model_dir>` |
| `model.xml` / `model.bin` | `python3 utils/convert-openvino.py <model_dir>` |

`model.tflite` and `model.xml` can be generated automatically by passing `-r`
to the test script (see below).

The DeepRacer ROS packages must be built and sourced (handled automatically by
the test script if `../install/setup.bash` or `/opt/aws/deepracer/lib/setup.bash`
exists).

---

## Running the test

```bash
./test-model-equivalency.sh -m <model_dir> -i <image_dir> [-f <fps>] [-r]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-m` | *(required)* | Path to model directory |
| `-i` | *(required)* | Directory of JPEG images to replay |
| `-f` | `10` | Frames per second for image playback |
| `-r` | off | Regenerate `model.tflite` and `model.xml` before running |

### Examples

```bash
# Normal run (converted models must already exist)
./test-model-equivalency.sh -m model/Sample_single_cam -i data/demo -f 5

# Regenerate converted models first, then run
./test-model-equivalency.sh -m model/Sample_single_cam -i data/demo -r
```

The script will:
1. Build `test_pkg` with `colcon`
2. *(if `-r`)* Run `utils/convert-tflite.py` and `utils/convert-openvino.py` to
   produce `model.tflite` and `model.xml` / `model.bin` in the model directory
3. Launch four nodes via `launch/inference_comparison_test.launch.py`:
   - `inference_comparison_node` — image playback, native TF inference, result aggregation
   - `sensor_fusion_node` — forwards compressed images to the inference nodes
   - `inference_node` (TFLite namespace) — runs TFLite inference
   - `inference_node` (OV namespace) — runs OpenVINO inference
4. Stream all images at the requested FPS; native TF inference runs synchronously
   on a background thread for each frame
5. Wait for all pending inference results, then write a `results-<timestamp>.json`
   file into the image directory
6. Shut down the entire launch stack when `inference_comparison_node` finishes
7. Automatically run `utils/summarize-results.py` on the new results file

---

## Output

A `results-<timestamp>.json` file is written to the image directory containing:

```
{
  "model": "<model_dir>",
  "model_metadata": { ... },
  "summary": {
    "tflite": <frames received>,
    "ov":     <frames received>,
    "tf":     <frames inferred>,
    "match":  <frames where all three agree>,
    "mismatch": <frames where they disagree>
  },
  "frames": {
    "<timestamp_ns>": {
      "filename": "...",
      "tflite": { "time": { "stamp": ..., "diff": <ns> }, "results": { "0": p0, ... } },
      "ov":     { ... },
      "tf":     { ... },
      "summary": {
        "action_diff": { "0": tflite0 - ov0, ... },
        "best": {
          "tflite": { "action": <idx>, "value": <prob> },
          "ov":     { "action": <idx>, "value": <prob> },
          "tf":     { "action": <idx>, "value": <prob> }
        }
      }
    },
    ...
  }
}
```

`diff` in `time` is the wall-clock latency for TFLite and OV (nanoseconds from
image timestamp to result receipt), and the elapsed inference time for the native
TF engine.

---

## Analysing results

The summary is printed automatically at the end of `test-model-equivalency.sh`.
You can also run it manually on any saved results file:

```bash
python3 utils/summarize-results.py <results-file.json> [--no-frames] [--no-dist] [--csv out.csv]
```

| Option | Description |
|--------|-------------|
| *(default)* | Full report: header, summary, latency table, per-frame table, action distribution |
| `--no-frames` | Skip the per-frame table |
| `--no-dist` | Skip the action distribution table |
| `--csv FILE` | Also export results to a CSV file |

The report shows:

| Section | Contents |
|---------|----------|
| **Summary** | Frame counts per engine, match/mismatch count and percentage |
| **Latency / Inference Time** | Min, mean, median, max, stdev per engine with a relative bar chart |
| **Per-frame results** | Chosen action index, probability, and latency for each engine per frame, with ✓/✗ agreement marker |
| **Action distribution** | How many times each action was chosen per engine with bar charts |

---

## Architecture

```
inference_comparison_node  ──publishes──►  sensor_fusion_node
        │                                        │
        │  (internal TF session.run)             ▼
        │                               inference_node (TFLite)
        │                               inference_node (OV)
        │                                        │
        └──subscribes to rl_results ◄────────────┘
```

The `required="true"` attribute on `inference_comparison_node` means any exit
(clean or crash) triggers a shutdown of the entire launch stack.

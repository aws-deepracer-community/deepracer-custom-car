# Camera Control Implementation Plan

This document outlines the roadmap for implementing a web interface to control camera settings via `camera_ros` (libcamera) in the DeepRacer system.

## 🎯 Objective
Expose `libcamera` controls through ROS 2 parameters and provide a modern, dynamic UI in the vehicle's web dashboard to adjust these settings in real-time.

---

## 🛠 Phase 1: Backend Implementation (`webserver_pkg`)

The backend acts as an intermediary between the Web UI and the ROS 2 parameter server. We will use Flask to expose RESTful endpoints that interact with the `camera_ros` node.

### 1.1 API Definition
- [x] Create `/src/aws-deepracer-webserver-pkg/webserver_pkg/webserver_pkg/camera_api.py`.
- [x] Implement `GET /api/camera/params`: Returns discovered editable parameters from `/camera_pkg/camera_node`, which is provided by `camera_ros` from `src/external/camera_ros`.
- [x] Implement `POST /api/camera/param/<param_name>`: Receives new parameter values and updates ROS 2 parameters on the camera node.
- [x] Replace the initial mock response with live ROS 2 parameter service calls.

### 1.2 ROS 2 Integration
- [x] **Discovery Logic:** Query `/camera_pkg/camera_node` through standard ROS 2 parameter services: `list_parameters`, `get_parameters`, and `describe_parameters`.
- [x] **Command Execution:** Set parameter values through the standard `set_parameters` service using the shared webserver ROS node, rather than shelling out to `ros2 param`.
- [x] **Dependency:** Add `rcl_interfaces` to `webserver_pkg/package.xml` because ROS 2 parameter services and parameter value messages are defined there.
- [x] **Error Handling:** Return structured errors when the camera parameter services are unavailable, request bodies are invalid, values cannot be represented as ROS parameters, or `camera_ros` rejects an update.

### 1.3 Camera Parameter Exposure Policy
- [x] Treat `camera_ros` dynamic parameters as libcamera controls. Names are discovered at runtime and generally match libcamera control names such as `ExposureTime`, `AnalogueGain`, `AeEnable`, `AwbEnable`, `ColourGains`, `Brightness`, `Contrast`, `Saturation`, and `Sharpness`.
- [x] Filter out read-only parameters based on ROS parameter descriptors.
- [x] Denylist static stream configuration and unsafe runtime controls from the web API: `camera`, `role`, `format`, `width`, `height`, `sensor_mode`, `orientation`, `camera_info_url`, `frame_id`, `use_node_time`, `use_sim_time`, `jpeg_quality`, and `FrameDurationLimits`.
- [x] Block `FrameDurationLimits` specifically because it controls frame duration/FPS, and changing FPS is not appropriate for DeepRacer perception timing.

---

## 🎨 Phase 2: Frontend Implementation (`console/website`)

The frontend provides an intuitive interface for users to interact with camera hardware using React and TypeScript.

### 2.1 Data & Types
- [x] Define `CameraParameter` and `ParamValue` interfaces in `console/website/src/common/types.ts`.
- [x] Add logic to handle ROS parameter value types returned by the backend: `boolean`, `integer`, `double`, `string`, and arrays of those types.
- [x] Avoid assuming mock-style lowercase names such as `exposure`, `gain`, or `white_balance`; the UI should render discovered libcamera control names.

### 2.2 API Integration (Custom Hooks)
- [x] Create `use-camera.ts` in `console/website/src/components/common/hooks/`.
- [x] Implement state management for loading, error, and current parameter states.
- [x] Implement the fetching logic (`useEffect`) to sync UI with ROS 2 parameters on mount/refresh.

### 2.3 UI Components
- [x] Create `CameraSettingsContainer.tsx` in `console/website/src/components/settings/`.
- [/] **Smart Inputs:** Build a component that renders the correct input type based on parameter metadata:
  - Sliders or numeric inputs for scalar numeric ranges, using descriptor `min`, `max`, and `step` when available.
  - Toggles for booleans such as `AeEnable` and `AwbEnable`.
  - Multi-value editors for array controls such as `ColourGains` when exposed by the camera.
  - Keep FPS/frame-duration controls hidden because `FrameDurationLimits` is blocked by the backend.
- [/] **Visual Feedback:** Add loading indicators and success/error toasts when settings are applied.

### 2.4 Navigation & Layout Integration
- [x] Update `src/components/pages/settings.tsx` or create a new page to include the Camera Settings section.
- [x] Ensure responsive layout works on both tablets (mobile view) and desktop views used for configuration.

---

## 🧪 Phase 3: Verification & Testing

### 3.1 Manual ROS 2 Validation
- [x] Verify that `camera_ros` actually exposes the parameters via CLI:
  `ros2 param list /camera_pkg/camera`
- [x] Test manual parameter changes using terminal to ensure hardware responsiveness.
- [x] Validate backend module syntax:
  `python3 -m py_compile src/aws-deepracer-webserver-pkg/webserver_pkg/webserver_pkg/camera_api.py`

### 3.2 Unit & Integration Testing (Frontend)
- [ ] Create unit tests for `CameraSettingsContainer` and custom hooks in the console project, following existing patterns in the codebase.

### 3.3 End-to-End (E2E) Testing
- [ ] **Full Loop Test:** Change a setting in the Web UI and verify via CLI that the ROS 2 parameter updated successfully.
- [ ] **Robustness Test:** Verify the system behaves gracefully when a camera is disconnected or a parameter update fails.

---
## 📝 Research & Technical Context Notes

### Hardware Layer (`libcamera`)
*   **Driver Dependency:** This feature is highly dependent on `camera_ros` mapping `libcamera` controls to ROS 2 parameters. If the driver doesn't expose a control (like "Focus") as a parameter, it won't appear in our UI.
*   **Parameter Source:** `/camera_pkg/camera_node` is the runtime node name for the `camera_ros` camera node. The implementation should be guided by `src/external/camera_ros`, not the legacy/local `camera_pkg/src/camera_node.cpp` wrapper.
*   **Control Names:** Dynamic parameters are generated from libcamera controls and use libcamera-style names, not normalized web UI names. The frontend can add labels, but the API should preserve the real parameter name.
*   **FPS Safety:** `FrameDurationLimits` maps to frame duration/FPS. It is intentionally blocked from web configuration because changing it can affect DeepRacer inference timing and control behavior.
*   **Latency:** Camera settings often require an immediate update. We must ensure the webserver-to-ROS bridge is performant enough to avoid significant lag during manual adjustments.

### Software Architecture
*   **Existing Pattern:** The existing Web Server uses a "Blueprint" pattern for modularity (see `device_info_api.py`). This project will follow that same architecture.
*   **Backend Implementation:** `camera_api.py` uses the shared webserver ROS node and standard `rcl_interfaces` parameter services (`ListParameters`, `GetParameters`, `DescribeParameters`, `SetParameters`). This avoids subprocess calls to `ros2 param`.
*   **Frontend Design:** The frontend follows a "Container/Presenter" or "Page/Component" pattern common in React applications, where logic is kept in hooks and UI in components.

### Security
*   All new API endpoints should respect the existing authentication mechanisms implemented in `login.py` to ensure only authorized users can modify hardware settings.

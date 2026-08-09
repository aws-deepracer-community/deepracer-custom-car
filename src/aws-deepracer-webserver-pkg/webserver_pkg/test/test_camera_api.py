import importlib.util
import json
import sys
import types
from pathlib import Path

from flask import Flask


CAMERA_API_PATH = Path(__file__).resolve().parents[1] / "webserver_pkg" / "camera_api.py"


def _load_camera_api_module(monkeypatch):
    fake_webserver_pkg = types.ModuleType("webserver_pkg")
    fake_webserver_pkg.__path__ = []

    fake_webserver_publisher_node = types.ModuleType("webserver_pkg.webserver_publisher_node")
    fake_webserver_publisher_node.get_webserver_node = lambda: None

    fake_utility = types.ModuleType("webserver_pkg.utility")
    fake_utility.call_service_sync = lambda *args, **kwargs: None

    fake_rcl_interfaces = types.ModuleType("rcl_interfaces")
    fake_rcl_interfaces_msg = types.ModuleType("rcl_interfaces.msg")
    fake_rcl_interfaces_srv = types.ModuleType("rcl_interfaces.srv")

    class FakeParameterValue:
        def __init__(self):
            self.type = None
            self.bool_value = None
            self.integer_value = None
            self.double_value = None
            self.string_value = None
            self.byte_array_value = []
            self.bool_array_value = []
            self.integer_array_value = []
            self.double_array_value = []
            self.string_array_value = []

    class FakeParameterType:
        PARAMETER_BOOL = "bool"
        PARAMETER_INTEGER = "integer"
        PARAMETER_DOUBLE = "double"
        PARAMETER_STRING = "string"
        PARAMETER_BYTE_ARRAY = "byte_array"
        PARAMETER_BOOL_ARRAY = "bool_array"
        PARAMETER_INTEGER_ARRAY = "integer_array"
        PARAMETER_DOUBLE_ARRAY = "double_array"
        PARAMETER_STRING_ARRAY = "string_array"

    class FakeParameter:
        def __init__(self, name="", value=None):
            self.name = name
            self.value = value

    class FakeRequest:
        def __init__(self, *args, **kwargs):
            self.names = []
            self.parameters = []
            self.depth = None
            self.values = []
            self.descriptors = []
            self.results = []

    class FakeSetParameters:
        Request = FakeRequest

    class FakeListParameters:
        Request = FakeRequest

    class FakeGetParameters:
        Request = FakeRequest

    class FakeDescribeParameters:
        Request = FakeRequest

    fake_rcl_interfaces_msg.ParameterValue = FakeParameterValue
    fake_rcl_interfaces_msg.ParameterType = FakeParameterType
    fake_rcl_interfaces_msg.Parameter = FakeParameter
    fake_rcl_interfaces_srv.ListParameters = FakeListParameters
    fake_rcl_interfaces_srv.GetParameters = FakeGetParameters
    fake_rcl_interfaces_srv.DescribeParameters = FakeDescribeParameters
    fake_rcl_interfaces_srv.SetParameters = FakeSetParameters

    monkeypatch.setitem(sys.modules, "webserver_pkg", fake_webserver_pkg)
    monkeypatch.setitem(sys.modules, "webserver_pkg.webserver_publisher_node", fake_webserver_publisher_node)
    monkeypatch.setitem(sys.modules, "webserver_pkg.utility", fake_utility)
    monkeypatch.setitem(sys.modules, "rcl_interfaces", fake_rcl_interfaces)
    monkeypatch.setitem(sys.modules, "rcl_interfaces.msg", fake_rcl_interfaces_msg)
    monkeypatch.setitem(sys.modules, "rcl_interfaces.srv", fake_rcl_interfaces_srv)
    fake_webserver_pkg.webserver_publisher_node = fake_webserver_publisher_node
    fake_webserver_pkg.utility = fake_utility
    fake_rcl_interfaces.msg = fake_rcl_interfaces_msg
    fake_rcl_interfaces.srv = fake_rcl_interfaces_srv

    module_name = "camera_api_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, CAMERA_API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_persists_camera_value_when_camera_service_is_unavailable(monkeypatch, tmp_path):
    module = _load_camera_api_module(monkeypatch)
    settings_path = tmp_path / "camera.json"
    monkeypatch.setattr(module, "CAMERA_SETTINGS_FILE_PATH", str(settings_path))

    monkeypatch.setattr(module, "_call_parameter_service", lambda *args, **kwargs: None)

    app = Flask(__name__)
    app.register_blueprint(module.CAMERA_API_BLUEPRINT)
    with app.test_request_context(
        "/api/camera/param/Brightness",
        method="POST",
        json={"value": 42},
    ):
        response = module.set_camera_param("Brightness")

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert json.loads(settings_path.read_text())["Brightness"] == 42


def test_applies_persisted_camera_values_when_available(monkeypatch, tmp_path):
    module = _load_camera_api_module(monkeypatch)
    settings_path = tmp_path / "camera.json"
    settings_path.write_text(json.dumps({"Brightness": 6, "AeEnable": True}))
    monkeypatch.setattr(module, "CAMERA_SETTINGS_FILE_PATH", str(settings_path))

    set_calls = []

    def fake_call_parameter_service(service_type, service_name, service_request):
        if service_name == "set_parameters":
            set_calls.append(service_request)
            return types.SimpleNamespace(results=[types.SimpleNamespace(successful=True, reason=None)])
        return None

    monkeypatch.setattr(module, "_call_parameter_service", fake_call_parameter_service)

    module._apply_pending_camera_parameters()

    assert len(set_calls) == 2
    applied_names = [parameter.name for request in set_calls for parameter in request.parameters]
    assert applied_names == ["AeEnable", "Brightness"]

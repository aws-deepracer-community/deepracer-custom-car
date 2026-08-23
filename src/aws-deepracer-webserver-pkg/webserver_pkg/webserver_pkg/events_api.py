#!/usr/bin/env python

#################################################################################
#   Copyright AWS DeepRacer Community. All Rights Reserved.                    #
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
events_api.py

Server-Sent Events (SSE) endpoint.  Clients connect to GET /api/events and
receive a persistent text/event-stream response.  Events are pushed by ROS
topic callbacks via the broadcast_sse_event() function in
webserver_publisher_node.py.

Supported event types:
    imu_stop  — IMU safety stop triggered; data is the stop reason
                ("crash" or "pickup")
"""

import json
import queue

from flask import Blueprint, Response, stream_with_context

import webserver_pkg.webserver_publisher_node as wpn

EVENTS_API_BLUEPRINT = Blueprint("events_api", __name__)

_KEEPALIVE_TIMEOUT_S = 15   # seconds between SSE keepalive comments
_CLIENT_QUEUE_DEPTH = 10    # max buffered events per client


@EVENTS_API_BLUEPRINT.route("/api/events")
def sse_stream():
    """Stream Server-Sent Events to the caller.

    The response is kept open indefinitely.  A comment-only keepalive is
    sent every _KEEPALIVE_TIMEOUT_S seconds so proxies and browsers do not
    time out the connection.
    """
    def generate():
        client_queue: queue.Queue = queue.Queue(maxsize=_CLIENT_QUEUE_DEPTH)
        wpn.register_sse_client(client_queue)
        try:
            # Immediate keepalive so the browser sees a response right away.
            yield ":\n\n"
            while True:
                try:
                    event = client_queue.get(timeout=_KEEPALIVE_TIMEOUT_S)
                    yield (
                        f"event: {event['event']}\n"
                        f"data: {json.dumps(event['data'])}\n\n"
                    )
                except queue.Empty:
                    # Send an SSE comment to keep the connection alive.
                    yield ":\n\n"
        finally:
            wpn.unregister_sse_client(client_queue)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx/proxy buffering
        },
    )

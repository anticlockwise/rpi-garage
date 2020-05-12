"""
To control opening/closing of garage from signals from
AWS IoT.
"""
from __future__ import print_function

import json
import gpiozero
import time

from awscrt import auth, io, mqtt, http
from awsiot import iotshadow
from .sensor import CLOSE, OPEN, GarageDoorSensor


class GarageDoorRelay:
    def __init__(self, relay_pin, inching_timeout=0.5):
        self._relay_pin = relay_pin
        self._inching_timeout = inching_timeout
        self._relay = gpiozero.OutputDevice(self._relay_pin)

    def signal(self):
        # Implement inching of 0.5 seconds
        self._relay.on()
        time.sleep(self._inching_timeout)
        self._relay.off()


class GarageDoorControlListener:
    def __init__(
        self,
        config: dict,
        garage_door_relay: GarageDoorRelay,
        sensor: GarageDoorSensor,
        device_shadow: iotshadow.IotShadowClient,
    ):
        self._endpoint_id = config['id']
        self._thing_name = config['thingName']
        self._garage_door_relay = garage_door_relay
        self._device_shadow = device_shadow
        self._sensor = sensor
        self._correlation_token = None

    def listen(self):
        self._device_shadow.subscribe_to_update_shadow_accepted(
            request=iotshadow.UpdateShadowSubscriptionRequest(self._thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._shadow_update_accepted,
        )
        print("Subscribed to device shadow updates...")
        self._sensor.listen(
            activate_func=lambda: self._report_status("opened"),
            deactivate_func=lambda: self._report_status("closed"),
        )
        print("Listening to REED sensor changes...")

    def _on_publish_update_shadow(self, future):
        future.result()
        print("Update request published.")

    def _report_status(self, status):
        print("Gotten status: {}".format(status))
        update_request = iotshadow.UpdateShadowRequest(
            thing_name=self._thing_name,
            state=iotshadow.ShadowState(
                reported={
                    "doorStatus": status,
                    "correlationToken": self._correlation_token,
                    "endpointId": self._endpoint_id,
                },
                desired={
                    "endpointId": self._endpoint_id,
                    "correlationToken": self._correlation_token,
                },
            ),
        )
        future = self._device_shadow.publish_update_shadow(
            update_request, qos=mqtt.QoS.AT_LEAST_ONCE
        )
        future.add_done_callback(self._on_publish_update_shadow)
        self._correlation_token = None

    def _shadow_update_accepted(self, response: iotshadow.UpdateShadowResponse):
        state = response.state
        if state:
            desired_state = state.desired
            if desired_state:
                door_status = desired_state.get("doorStatus")
                if door_status == "signaled":
                    current_status = self._sensor.read()
                    new_desired_state = "closed" if current_status == OPEN else "opened"
                    current_state = "closed" if current_status == CLOSE else "opened"
                    self._correlation_token = desired_state.get("correlationToken")
                    request = iotshadow.UpdateShadowRequest(
                        thing_name=self._thing_name,
                        state=iotshadow.ShadowState(
                            reported={
                                "doorStatus": current_state,
                                "correlationToken": self._correlation_token,
                                "endpointId": self._endpoint_id,
                            },
                            desired={
                                "doorStatus": new_desired_state,
                                "correlationToken": self._correlation_token,
                                "endpointId": self._endpoint_id,
                            },
                        ),
                    )
                    future = self._device_shadow.publish_update_shadow(
                        request, qos=mqtt.QoS.AT_LEAST_ONCE
                    )
                    future.add_done_callback(self._on_publish_update_shadow)
                    self._garage_door_relay.signal()

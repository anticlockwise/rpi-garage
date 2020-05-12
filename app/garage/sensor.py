from __future__ import print_function

import gpiozero
import json
import time
from awsiot import iotshadow


CLOSE = 0
OPEN = 1


class GarageDoorSensor:
    def __init__(self, sensor_pin):
        self._sensor_pin = sensor_pin
        self._sensor = gpiozero.DigitalInputDevice(pin=sensor_pin)

    def read(self):
        return self._sensor.value

    def listen(self, activate_func, deactivate_func):
        self._sensor.when_activated = activate_func
        self._sensor.when_deactivated = deactivate_func


class GarageDoorSensorListener:
    def __init__(self, sensor, device_shadow: iotshadow.IotShadowClient):
        self._sensor = sensor
        self._device_shadow = device_shadow

    def listen(self):
        self._sensor.listen(lambda: self._report_status("opened"),
                            lambda: self._report_status("closed")
                            )
        self._device_shadow.subscribe_to_update_shadow_accepted(self._shadow_update)
        self._device_shadow.shadowGet(self._shadow_get, 5)
        self._device_shadow.shadowRegisterDeltaCallback(
            self._shadow_callback_delta)

    def _report_status(self, status, client_token):
        self._device_shadow.shadowUpdate(json.dumps({
            "state": {
                "reported": {
                    "doorStatus": status
                }
            },
            "clientToken": client_token
        }), self._shadow_update, 5)

    def _shadow_callback_delta(self, payload, response_status, token):
        print("Delta response status from reed sensor: {}".format(response_status))
        payload_dict = json.loads(payload)
        print("~~~~~~~ DELTA ~~~~~~~~")
        print("Payload: {}".format(payload))
        print("~~~~~~~~~~~~~~~~~~~~~~")

        state = payload_dict["state"]
        door_status = state.get("doorStatus", "")

    def _shadow_update(self, response: iotshadow.UpdateShadowResponse):
        if response_status == "timeout":
            print("Update request " + token + " time out!")
        if response_status == "accepted":
            print("~"*30)
            print("Update request with token: {} accepted".format(token))
            print("Door status: {}".format(payload))
            print("~"*30)
        if response_status == "rejected":
            print("Update request {} rejected!".format(token))

    def _shadow_get(self, payload, response_status, token):
        print("From reed sensor")
        if response_status == "timeout":
            print("Get request {} time out!".format(token))
        if response_status == "accepted":
            payload_dict = json.loads(payload)
            print("~"*30)
            print("Get request with token: {} accepted".format(token))
            print("Payload: {}".format(payload))
            print("~"*30)
        if response_status == "rejected":
            print("Get request with token {} rejected".format(token))
            print("Rejected payload: {}".format(payload))

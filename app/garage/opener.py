"""
To control opening/closing of garage from signals from
AWS IoT.
"""
import json
import gpiozero
import time

from awscrt import auth, io, mqtt, http
from awsiot import iotshadow


CLOSE = 0
OPEN = 1


class GarageDoorStatus:
    ENDPOINT_ID_PROP = "endpointId"
    CORRELATION_TOKEN_PROP = "correlationToken"
    DOOR_STATUS_PROP = "doorStatus"

    SIGNALED = "signaled"
    CLOSED = "closed"
    OPENED = "opened"

    def __init__(self, endpoint_id, door_status=None, correlation_token=None):
        self._endpoint_id = endpoint_id
        self._door_status = door_status
        self._correlation_token = correlation_token

    @property
    def endpoint_id(self):
        return self._endpoint_id

    @property
    def door_status(self):
        return self._door_status

    @property
    def correlation_token(self):
        return self._correlation_token

    def json(self):
        rval = {
            self.ENDPOINT_ID_PROP: self.endpoint_id,
            self.CORRELATION_TOKEN_PROP: self.correlation_token,
        }
        if self.door_status:
            rval[self.DOOR_STATUS_PROP] = self.door_status
        return rval


class GarageDoorSensor:
    def __init__(self, sensor_pin):
        self._sensor_pin = sensor_pin
        self._sensor = gpiozero.DigitalInputDevice(pin=sensor_pin)

    def read(self):
        return self._sensor.value

    def listen(self, activate_func, deactivate_func):
        self._sensor.when_activated = activate_func
        self._sensor.when_deactivated = deactivate_func


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
        self._endpoint_id = config["id"]
        self._thing_name = config["thingName"]
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
            activate_func=lambda: self._report_status(GarageDoorStatus.OPENED),
            deactivate_func=lambda: self._report_status(GarageDoorStatus.CLOSED),
        )
        print("Listening to REED sensor changes...")

    def _on_publish_update_shadow(self, future):
        future.result()
        print("Update request published.")

    def _report_status(self, status):
        print("Gotten status: {}".format(status))
        reported_status = GarageDoorStatus(
            endpoint_id=self._endpoint_id,
            door_status=status,
            correlation_token=self._correlation_token,
        )
        desired_status = GarageDoorStatus(
            endpoint_id=self._endpoint_id, correlation_token=self._correlation_token
        )
        update_request = iotshadow.UpdateShadowRequest(
            thing_name=self._thing_name,
            state=iotshadow.ShadowState(
                reported=reported_status.json(), desired=desired_status.json(),
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
                door_status = desired_state.get(GarageDoorStatus.DOOR_STATUS_PROP)
                if door_status == GarageDoorStatus.SIGNALED:
                    current_status = self._sensor.read()
                    new_desired_state = (
                        GarageDoorStatus.CLOSED
                        if current_status == OPEN
                        else GarageDoorStatus.OPENED
                    )
                    current_state = (
                        GarageDoorStatus.CLOSED
                        if current_status == CLOSE
                        else GarageDoorStatus.OPENED
                    )
                    self._correlation_token = desired_state.get(
                        GarageDoorStatus.CORRELATION_TOKEN_PROP
                    )

                    reported_state_obj = GarageDoorStatus(
                        self._endpoint_id, current_state, self._correlation_token
                    )
                    desired_state_obj = GarageDoorStatus(
                        self._endpoint_id, new_desired_state, self._correlation_token
                    )
                    request = iotshadow.UpdateShadowRequest(
                        thing_name=self._thing_name,
                        state=iotshadow.ShadowState(
                            reported=reported_state_obj.json(),
                            desired=desired_state_obj.json(),
                        ),
                    )
                    future = self._device_shadow.publish_update_shadow(
                        request, qos=mqtt.QoS.AT_LEAST_ONCE
                    )
                    future.add_done_callback(self._on_publish_update_shadow)
                    self._garage_door_relay.signal()

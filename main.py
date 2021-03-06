from __future__ import absolute_import

import argparse
import json
from app.garage.opener import (
    GarageDoorControlListener,
    GarageDoorRelay,
    GarageDoorSensor,
)
from awscrt import io
from awsiot import iotshadow, mqtt_connection_builder


CLIENT_ID_CONTROLLER = "GaragePiController"


def initialize_shadow(config):
    endpoint_id = config["id"]
    client_id = "{}-{}".format(CLIENT_ID_CONTROLLER, endpoint_id)
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=config["endpoint"],
        cert_filepath=config["certificatePath"],
        pri_key_filepath=config["privateKeyPath"],
        ca_filepath=config["rootCAPath"],
        client_bootstrap=client_bootstrap,
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=6,
    )
    print(
        "Connectin to {} with client ID '{}'...".format(config["endpoint"], client_id)
    )
    connected_future = mqtt_connection.connect()

    shadow_client = iotshadow.IotShadowClient(mqtt_connection)

    connected_future.result()
    print("Connected and created device shadow for {}".format(client_id))

    return shadow_client


def initialize(config_location):
    config = None
    with open(config_location) as f:
        config = json.load(f)
    if not config:
        raise RuntimeError("Error loading config file for the device")
    relay = GarageDoorRelay(config["relayPin"])
    sensor = GarageDoorSensor(config["reedPin"])

    device_shadow_controller = initialize_shadow(config)

    return GarageDoorControlListener(config, relay, sensor, device_shadow_controller)


def options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        default="/opt/rpigarage/conf.json",
        dest="config_location",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = options()
    config_location = args.config_location
    controller = initialize(config_location)
    controller.listen()
    while True:
        pass

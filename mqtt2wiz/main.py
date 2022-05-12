#!/usr/bin/env python
import asyncio
import collections
import random
import colorsys
import json
from typing import Dict
from dataclasses import dataclass
from contextlib import AsyncExitStack, asynccontextmanager
from random import randrange
from asyncio_mqtt import Client, MqttError

from mqtt2wiz import log
from mqtt2wiz.config import Cfg

from pywizlight import wizlight
from pywizlight import PilotBuilder


@dataclass
class WizDevice:
    topic: str
    name: str
    host: str
    wiz: wizlight

# indexed by unique key WizDevice.topic
device_list: Dict[str, WizDevice] = {}
running = True

async def main_loop():
    global device_list
    global running

    tasks = set()
    
    logger.debug("Starting main event processing loop")
    cfg = Cfg()
    mqtt_broker_ip = cfg.mqtt_host
    mqtt_client_id = cfg.mqtt_client_id

    async with AsyncExitStack() as stack:
        # Keep track of the asyncio tasks that we create, so that we can cancel them on exit
        stack.push_async_callback(cancel_tasks, tasks)

        # Connect to the MQTT broker
        client = Client(hostname=mqtt_broker_ip, client_id=mqtt_client_id, keepalive=0)
        await stack.enter_async_context(client)

        # Messages that doesn't match a filter will get sent to MQTT_Receive_Callback
        messages = await stack.enter_async_context(client.unfiltered_messages())
        task = asyncio.create_task(MQTT_Receive_Callback(messages))
        tasks.add(task)

        # Create the device list and subscribe to their topics
        for device_name, config in cfg.devices.items():
            device_topic = cfg.mqtt_topic(device_name)
            device_host = cfg.devices.get(device_name, {}).get('host')
            device_list[device_topic] = WizDevice(device_topic, device_name, device_host, wizlight(device_host))
            logger.debug(f"Adding {device_list[device_topic]} to device list")
            await client.subscribe(device_topic)
            logger.debug(f"Subscribing to topic {device_topic}")

        # Subscribe to topic to control mqtt2wiz
        await client.subscribe("mqtt2wiz_control")

        # task = asyncio.create_task(MQTT_Post(client))
        # tasks.add(task)

        # Wait for everything to complete (or fail due to, e.g., network errors)
        await asyncio.gather(*tasks)  

async def MQTT_Receive_Callback(messages):
    global device_list
    global running

    async for message in messages:
        logger.debug(f"{message.topic} | {message.payload.decode()}")

        # Check if the received message topic matches one of our devices
        if device_list.get(message.topic, None):

            try:
                json_state = json.loads(message.payload.decode())
                is_json = True
            except ValueError as e:
                # logger.debug(f"MQTT_Receive_Callback received non-json payload")
                is_json = False
            except TypeError as e:
                # logger.debug(f"MQTT_Receive_Callback received non-json payload")
                is_json = False

            if is_json == True:

                if 'state' in json_state and json_state['state'] == "on":
                    try:
                        await device_list[message.topic].wiz.turn_on(PilotBuilder(colortemp=3000, brightness=255))
                        logger.debug(f"turn_on device {device_list[message.topic].name} @ {device_list[message.topic].host}")
                    except Exception as e:
                        logger.debug(e)

                if 'state' in json_state and json_state['state'] == "off":
                    try:
                        await device_list[message.topic].wiz.turn_off()
                        logger.debug(f"turn_off device {device_list[message.topic].name} @ {device_list[message.topic].host}")
                    except Exception as e:
                        logger.debug(e)

                if 'brightness' in json_state:
                    value = int(json_state['brightness'])
                    try:
                        await device_list[message.topic].wiz.turn_on(PilotBuilder(brightness=value))
                        logger.debug(f"turn_on device {device_list[message.topic].name} @ {device_list[message.topic].host} with brightness {value}")
                    except Exception as e:
                        logger.debug(e)
                
                if 'temperature' in json_state:
                    value = int(json_state['temperature'])
                    try:
                        await device_list[message.topic].wiz.turn_on(PilotBuilder(colortemp=value))
                        logger.debug(f"turn_on device {device_list[message.topic].name} @ {device_list[message.topic].host} with colortemp {value}")
                    except Exception as e:
                        logger.debug(e)

            if message.payload.decode() == 'on':
                try:
                    await device_list[message.topic].wiz.turn_on(PilotBuilder(colortemp=3000, brightness=255))
                    logger.debug(f"turn_on device {device_list[message.topic].name} @ {device_list[message.topic].host}")
                except Exception as e:
                    logger.debug(e)

            if message.payload.decode() == 'off':
                try:
                    await device_list[message.topic].wiz.turn_off()
                    logger.debug(f"turn_off device {device_list[message.topic].name} @ {device_list[message.topic].host}")
                except Exception as e:
                    logger.debug(e)

            if "#" in message.payload.decode(): #parse as Hex RGB
                value = message.payload.decode().lstrip('#')
                lv = len(value)
                wanted_rgb = tuple(int(value[i:i+lv//3], 16) for i in range(0, lv, lv//3))
                #hsv_norm = tuple(x/255 for x in wanted_rgb)
                #wanted_hsv = colorsys.rgb_to_hsv(*hsv_norm)
                new_rgbw = (wanted_rgb[0], wanted_rgb[1], wanted_rgb[2], 0) #gave up trying to find an appropriate rgbw from given rgb. set w to 0
                try:
                    await device_list[message.topic].wiz.turn_on(PilotBuilder(rgbw=new_rgbw))
                    logger.debug(f"turn_on device {device_list[message.topic].name} @ {device_list[message.topic].host} with color {new_rgbw}")
                except Exception as e:
                    logger.debug(e)

        if message.topic == "mqtt2wiz_control":
            if message.payload.decode() == 'shutdown':
                running = False
                break
        if message.topic == "mqtt2wiz_control":
            if message.payload.decode() == 'restart':
                break

# async def MQTT_Post(client):
#     while True:
#         message = randrange(100)
#         print(f'[topic="/mqtt2wiz_test_topic/"] Publishing message={message}')
#         await client.publish("/mqtt2wiz_test_topic/", message, qos=1)
#         await asyncio.sleep(2)

async def cancel_tasks(tasks):
    logger.debug(f"cancel_tasks tasks={tasks}")
    for task in tasks:
        if task.done():
            continue
        try:
            task.cancel()
            await task
        except asyncio.CancelledError:
            pass

async def main():
    global running
    # Run the main_loop indefinitely. Reconnect automatically if the connection is lost.
    reconnect_interval = Cfg().reconnect_interval
    while running:
        try:
            await main_loop()
        except MqttError as error:
            logger.debug(f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
            logger.debug(f"finally: await asyncio.sleep(reconnect_interval) running={running}")
            await asyncio.sleep(reconnect_interval)
        except (KeyboardInterrupt, SystemExit):
            logger.debug("got KeyboardInterrupt")
            running = False
            break
        except asyncio.CancelledError:
            logger.debug(f"main(): got asyncio.CancelledError running={running}")
            running = False
            break
        except Exception as error:
            logger.debug(f'Error "{error}".')
            running = False
            break


if __name__ == "__main__":
    logger = log.getLogger()
    log.initLogger()

    knobs = Cfg().knobs
    if isinstance(knobs, collections.abc.Mapping):
        if knobs.get("log_to_console"):
            log.log_to_console()
        if knobs.get("log_level_debug"):
            log.set_log_level_debug()

    logger.info("mqtt2wiz process started")
    asyncio.run(main())
    logger.debug("mqtt2wiz process stopped")

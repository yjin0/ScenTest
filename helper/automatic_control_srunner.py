#!/usr/bin/env python

# Copyright (c) 2018 Intel Labs.
# authors: German Ros (german.ros@intel.com)
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""Example of automatic vehicle control from client side."""

from __future__ import print_function

import argparse
import logging
import random
import sys
import time

import carla
from agents.navigation.basic_agent import BasicAgent
from agents.navigation.constant_velocity_agent import ConstantVelocityAgent

def game_loop(args):
    """Main loop of the simulation"""

    world = None
    player = None
    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(20.0)

        world = client.get_world()
        # Wait for the ego vehicle
        while player is None:
            print("Waiting for the ego vehicle...")
            time.sleep(1)
            print(world.get_actors())
            possible_vehicles = world.get_actors().filter('vehicle.*')
            for vehicle in possible_vehicles:
                if vehicle.attributes['role_name'] == 'ego_vehicle':
                    player = vehicle
                    break
        
        print("Ego vehicle found!")


        agent = BasicAgent(player)
        spawn_points = world.get_map().get_spawn_points()
        destination = random.choice(spawn_points).location
        agent.set_destination(destination)

        while True:
            if agent.done():
                print("The target has been reached, stopping the simulation")
                break

            control = agent.run_step()
            control.manual_gear_shift = False
            player.apply_control(control)

    finally:
        if world is not None:
            settings = world.get_settings()
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None
            world.apply_settings(settings)

def main():
    """Main method"""

    argparser = argparse.ArgumentParser(
        description='CARLA Automatic Control Client')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    args = argparser.parse_args()

    logging.basicConfig(format='%(levelname)s: %(message)s')

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        game_loop(args)

    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()

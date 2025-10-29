#!/usr/bin/env python3
import carla
import time
import sys
import argparse
import os
from datetime import datetime
import random

from agents.navigation.basic_agent import BasicAgent


class Recorder:
    def __init__(self, client, world, output_dir="recordings"):
        self.client = client
        self.world = world
        self.output_dir = output_dir
        self.recording_start_time = None
        self.is_recording = False
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def start_recording(self):
        if not self.is_recording:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_name = f"recording_{timestamp}"
            self.client.start_recorder(f"{self.output_dir}/{self.recording_name}.log", True)
            self.recording_start_time = time.time()
            self.is_recording = True
            print(f"Started recording: {self.recording_name}")
    
    def stop_recording(self):
        if self.is_recording:
            self.client.stop_recorder()
            duration = time.time() - self.recording_start_time
            print(f"Stopped recording: {self.recording_name}")
            print(f"Recording duration: {duration:.2f} seconds")
            self.is_recording = False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run CARLA at 100 FPS')
    parser.add_argument('--host', default='127.0.0.1', help='IP of the host server (default: 127.0.0.1)')
    parser.add_argument('--port', default=2000, type=int, help='TCP port to listen to (default: 2000)')
    parser.add_argument('--record', action='store_true', help='Start recording immediately')
    parser.add_argument('--output-dir', default='recordings', help='Directory to save recordings (default: recordings)')
    args = parser.parse_args()

    # Connect to the CARLA server
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)


    # Get the world
    world = client.get_world()

    # Get the current settings
    settings = world.get_settings()

    # Set fixed time step for 100 FPS (1/100 = 0.01 seconds)
    settings.fixed_delta_seconds = 0.05

    # Enable synchronous mode
    settings.synchronous_mode = True

    # Apply the settings
    world.apply_settings(settings)

    xodr_file_path = os.path.join("/home/si9h/car/SCTest/opscenarios/ARG_Carcarana-1_3_I-1-1.xodr")
    with open(xodr_file_path, 'r') as f_xodr:
        opendrive_content = f_xodr.read()
        print(f"Successfully loaded OpenDRIVE content from {xodr_file_path}")
    world = client.generate_opendrive_world(opendrive_content)
    world.apply_settings(settings)
    
    actor_list = []
    vehicle = None # Initialize vehicle
    try:
        # Spawn a hero vehicle
        print("Attempting to spawn a hero vehicle...")
        blueprint_library = world.get_blueprint_library()
        # Try to find a common vehicle blueprint, e.g., Tesla Model 3
        vehicle_bp = blueprint_library.find('vehicle.tesla.model3')
            
        if vehicle_bp:
            if vehicle_bp.has_attribute('role_name'):
                vehicle_bp.set_attribute('role_name', 'hero')
            else:
                print(f"Warning: Blueprint {vehicle_bp.id} does not have 'role_name' attribute.")

            spawn_points = world.get_map().get_spawn_points()
            spawn_point = spawn_points[6]

            vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
            if vehicle is not None:
                actor_list.append(vehicle)
                print(f"Spawned vehicle {vehicle.type_id} (id: {vehicle.id}) with role_name 'hero'.")

                # Initialize BasicAgent to drive from spawn_points[0] to spawn_points[10]
                agent = BasicAgent(vehicle) # Default target speed is 20 km/h
                start_spawn_point = spawn_point
                destination_spawn_point = spawn_points[12]

                agent.set_destination(destination_spawn_point.location)
                print(f"Hero vehicle (id: {vehicle.id}) navigating from {start_spawn_point.location} to {destination_spawn_point.location} using BasicAgent.")

            else:
                print(f"Error: Failed to spawn hero vehicle using blueprint {vehicle_bp.id} at {spawn_point}.")
        else:
            print("Error: Could not find any suitable vehicle blueprint.")

        # Initialize recorder
        recorder = Recorder(client, world, args.output_dir)
        
        # Start recording if requested
        if args.record:
            recorder.start_recording()

        print("CARLA is now running at 100 FPS")
        print("Press 'R' to toggle recording")
        print("Press Ctrl+C to exit")

        # Keep the script running
        while True:
            # Tick the world
            world.tick()

            if vehicle is not None and 'agent' in locals():
                if agent.done():
                    print("Destination reached by BasicAgent!")
                    vehicle.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0)) # Stop the car
                    if recorder.is_recording:
                        recorder.stop_recording()
                    print("Exiting script.")
                    sys.exit()  # Exit the script
                else:
                    vehicle.apply_control(agent.run_step()) # Apply control to the vehicle

                # Update spectator to follow the hero vehicle
                spectator = world.get_spectator()
                v_transform = vehicle.get_transform()

                # Print vehicle velocity for diagnostics
                # velocity = vehicle.get_velocity()
                # print(f"Vehicle velocity: x={velocity.x:.2f}, y={velocity.y:.2f}, z={velocity.z:.2f} (speed: {velocity.length():.2f} m/s)")
                
                # Position spectator: 10 units behind, 3 units above the vehicle's center
                spectator_location = v_transform.location - 10.0 * v_transform.get_forward_vector() + carla.Location(z=3.0)
                
                # Spectator rotation: align yaw with vehicle and pitch down for a good view
                spectator_rotation = carla.Rotation(pitch=-20.0, yaw=v_transform.rotation.yaw)
                
                spectator.set_transform(carla.Transform(spectator_location, spectator_rotation))
            
            # Check for key press (non-blocking)
            if sys.stdin.isatty():
                import select
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    key = sys.stdin.read(1)
                    if key.lower() == 'r':
                        if recorder.is_recording:
                            recorder.stop_recording()
                        else:
                            recorder.start_recording()
            
            time.sleep(0.001)  # Small sleep to prevent CPU overload

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Stop recording if active
        if 'recorder' in locals() and recorder.is_recording:
            recorder.stop_recording()

        # Destroy spawned actors
        if 'client' in locals() and actor_list: # actor_list will be defined
            print("\nDestroying spawned actors...")
            client.apply_batch([carla.command.DestroyActor(actor) for actor in actor_list])
            print("Spawned actors destroyed.")
            
        # Reset settings to default
        if 'world' in locals():
            settings = world.get_settings()
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None
            world.apply_settings(settings)
        print("CARLA settings have been reset to default")

if __name__ == '__main__':
    main()
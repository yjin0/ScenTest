import carla
import time
import logging
import subprocess
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# !!! IMPORTANT: Configure this path to your CARLA installation !!!
# Example: "/opt/carla-simulator/CarlaUE4.sh" or "~/CARLA_0.9.13/CarlaUE4.sh"
CARLA_EXECUTABLE_PATH = "/home/si9h/Carla15/CarlaUE4.sh"  # PLEASE UPDATE THIS

DEFAULT_CARLA_HOST = 'localhost'
DEFAULT_CARLA_PORT = 2000
DEFAULT_TIMEOUT = 5.0  # seconds

def _manage_carla_processes(action: str):
    """
    Manages CARLA server processes (start, kill).

    Args:
        action (str): "start" or "kill".

    Returns:
        subprocess.Popen object if action is "start" and successful, None otherwise.
    """
    if action == "kill":
        logger.info("Attempting to kill CARLA processes...")
        try:
            # Using pkill to find processes by name
            # CarlaUE4-Linux- is more specific for the actual game process
            subprocess.run(["pkill", "-f", "CarlaUE4-Linux-"], capture_output=True, text=True, check=False)
            # CarlaUE4.sh is for the script that might launch it
            p_sh = subprocess.run(["pkill", "-f", "CarlaUE4.sh"], capture_output=True, text=True, check=False)
            
            if p_sh.returncode == 0:
                logger.info("Successfully sent kill signal to CARLA-related processes.")
            elif p_sh.returncode == 1:  # pkill returns 1 if no processes matched
                logger.info("No CARLA processes found running.")
            else:
                logger.warning(f"pkill command for CarlaUE4.sh exited with {p_sh.returncode}.")
                if p_sh.stdout.strip(): logger.debug(f"  Stdout: {p_sh.stdout.strip()}")
                if p_sh.stderr.strip(): logger.debug(f"  Stderr: {p_sh.stderr.strip()}")
        except FileNotFoundError:
            logger.error("Error: 'pkill' command not found. Please ensure it is installed and in your PATH.")
        except Exception as e:
            logger.error(f"An error occurred while trying to kill CARLA processes: {e}")
        return None

    elif action == "start":
        resolved_path = os.path.expanduser(CARLA_EXECUTABLE_PATH)
        if not os.path.isfile(resolved_path) or not os.access(resolved_path, os.X_OK):
            logger.error(f"Error: CARLA executable not found or not executable at '{resolved_path}'.")
            logger.error("Please update CARLA_EXECUTABLE_PATH in this script.")
            return None

        logger.info(f"Attempting to start CARLA server from: {resolved_path}")
        try:
            # Added -opengl, common for servers. Add other args like -quality-level=Low if needed.
            server_process = subprocess.Popen(
                [resolved_path, "-benchmark", "fps=60",], 
                # [resolved_path, "-benchmark", "fps=60",], 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from the current terminal
            )
            logger.info(f"CARLA server process started with PID: {server_process.pid}. It will run in the background.")
            logger.info("Allowing time for the server to initialize (approx. 10-15s)...")
            time.sleep(15) # Increased sleep time for server to be fully ready
            return server_process
        except Exception as e:
            logger.error(f"An error occurred while trying to start CARLA server: {e}")
            return None
    else:
        logger.error(f"Invalid action '{action}' for _manage_carla_processes.")
        return None

def check_carla_alive(host=DEFAULT_CARLA_HOST, port=DEFAULT_CARLA_PORT, timeout=DEFAULT_TIMEOUT):
    """
    Checks if a CARLA server is alive and responding on the given host and port.
    """
    logger.info(f"Attempting to connect to CARLA server at {host}:{port} with timeout {timeout}s...")
    try:
        client = carla.Client(host, port)
        client.set_timeout(timeout)
        client.get_server_version() 
        logger.info(f"Successfully connected to CARLA server at {host}:{port}.")
        return True
    except RuntimeError as e:
        if "time-out" in str(e).lower() or "refused" in str(e).lower():
            logger.info(f"CARLA server at {host}:{port} is not reachable: {e}")
        else:
            logger.error(f"Runtime error connecting to CARLA at {host}:{port}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while checking CARLA server: {e}")
        return False

def kill_carla():
    """
    Kills all running CARLA server processes.
    """
    logger.info("Executing kill_carla()...")
    _manage_carla_processes(action="kill")
    logger.info("kill_carla() completed. Check system processes if issues persist.")

def start_carla():
    """
    Starts the CARLA server in the background.
    Uses CARLA_EXECUTABLE_PATH defined in this script.
    Returns the server process object if successful, None otherwise.
    """
    logger.info("Executing start_carla()...")
    server_process = _manage_carla_processes(action="start")
    if server_process:
        logger.info(f"start_carla() initiated server process {server_process.pid}.")
        if check_carla_alive():
            logger.info("CARLA server confirmed to be running after start.")
        else:
            logger.warning("CARLA server did NOT become reachable after start attempt. Check server logs.")
    else:
        logger.warning("start_carla() failed to initiate server process.")
    logger.info("start_carla() completed.")
    return server_process

def restart_carla():
    """
    Restarts the CARLA server: kills existing processes, then starts a new one.
    Returns the new server process object if successful, None otherwise.
    """
    logger.info("Executing restart_carla()...")
    logger.info("Step 1: Killing existing CARLA processes.")
    kill_carla()
    logger.info("Waiting briefly after killing processes (5s)...")
    time.sleep(5)  # Wait for processes to fully terminate
    logger.info("Step 2: Starting new CARLA server instance.")
    server_process = start_carla() # This already includes a check_carla_alive
    logger.info("restart_carla() completed.")
    return server_process

if __name__ == '__main__':
    logger.info("Running CARLA Utility Script (utility.py) for testing...")
    logger.info(f"Using CARLA executable path: {CARLA_EXECUTABLE_PATH}")
    if CARLA_EXECUTABLE_PATH == "/path/to/your/carla/CarlaUE4.sh" or not os.path.exists(os.path.expanduser(CARLA_EXECUTABLE_PATH)):
        logger.warning("\nWARNING: CARLA_EXECUTABLE_PATH is a placeholder or points to a non-existent file.")
        logger.warning("Please edit utility.py and set it to your actual CarlaUE4.sh location.")
        logger.warning("Aborting further interactive tests to prevent errors.")
    else:
        logger.info("\n--- Initial check_carla_alive ---")
        is_initially_alive = check_carla_alive()
        logger.info(f"Initial CARLA server status: {'ALIVE' if is_initially_alive else 'NOT ALIVE/REACHABLE'}.")

        # --- Interactive Testing --- 
        print("\n--- Interactive CARLA Management --- ")
        while True:
            current_status = 'ALIVE' if check_carla_alive(timeout=2.0) else 'NOT ALIVE'
            print(f"\nCurrent CARLA status: {current_status}")
            print("Options: (1) Check Status, (2) Start, (3) Kill, (4) Restart, (q) Quit")
            choice = input("Enter choice: ").strip().lower()

            if choice == '1':
                # Status already printed
                pass
            elif choice == '2':
                if current_status == 'ALIVE':
                    logger.info("CARLA is already running.")
                else:
                    start_carla()
            elif choice == '3':
                if current_status == 'NOT ALIVE':
                    logger.info("CARLA is not running, nothing to kill.")
                else:
                    kill_carla()
            elif choice == '4':
                restart_carla()
            elif choice == 'q':
                logger.info("Exiting interactive test.")
                break
            else:
                logger.warning("Invalid choice. Please try again.")
            time.sleep(1) # Brief pause before re-checking status for the loop

    logger.info("\nUtility script testing finished.")

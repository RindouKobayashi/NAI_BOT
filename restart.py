import sys
import subprocess
import os
import logging
import time
from pathlib import Path

# Store the venv Python path when this script is first run
PYTHON_PATH = sys.executable

# Create logs directory if it doesn't exist
logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'restart.log'),
        logging.StreamHandler()
    ]
)

def restart_bot():
    try:
        # Get the directory containing this script
        script_dir = Path(__file__).parent.absolute()
        
        # Change to the script directory
        os.chdir(script_dir)
        
        logging.info("Waiting 2 seconds before starting new bot instance...")
        # Add delay to ensure previous instance is fully closed
        time.sleep(2)
        
        logging.info("Starting new bot instance...")
        # Use absolute path for main.py
        main_path = script_dir / "main.py"
        
        # Set up process creation flags based on platform
        kwargs = {
            'cwd': script_dir,
            'env': os.environ.copy()
        }
        
        # On Windows, hide the console window
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo
        else:
            # On Unix-like systems, use default process creation
            pass
            
        # Create new process using the stored venv Python path
        process = subprocess.Popen(
            [PYTHON_PATH, str(main_path)],
            **kwargs
        )
        logging.debug(f"Python interpreter process started with PID: {process.pid} (Note: The actual Discord bot process will have a different PID)")
        
    except Exception as e:
        logging.error(f"Error restarting bot: {e}")
        logging.exception("Full traceback:")

if __name__ == "__main__":
    restart_bot()

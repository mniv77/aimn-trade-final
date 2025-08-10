# /run_worker.py
# Command for PythonAnywhere Always-on task: python /home/USER/aimn/run_worker.py
from app.worker import run_forever
if __name__ == "__main__":
    run_forever(poll_sec=60)
# tasks.py

import time

def background_task(duration):
    """Simulates a long-running task."""
    print(f"Task started, will take {duration} seconds.")
    time.sleep(duration)
    print("Task completed!")
    return "Done"

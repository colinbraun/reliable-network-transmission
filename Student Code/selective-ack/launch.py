#!/usr/bin/env python

import subprocess
import time

# PYTHON="python3.8"
PYTHON="python3"

# You need to change this to point to whatever config you're using
CONFIG_PATH="/home/electro/repos/lab-project-2-reliable-transmission-colinbraun/TestConfig/config3.ini"

# Change this to the path of the file you're sending
SEND_FILE_PATH="to_send_small.txt"

# Change this to the path of the file you're creating 
RECV_FILE_PATH="received.txt"

# Change this to point to the emulator
EMULATOR_PATH="../../Emulator/emulator.py"

def launch():

    # Start emulator in background
    emulator = subprocess.Popen([PYTHON, EMULATOR_PATH, CONFIG_PATH])

    # Start receiver in background
    receiver = subprocess.Popen([PYTHON, "receiver.py", CONFIG_PATH])

    time.sleep(1)

    # Start sender in background
    sender = subprocess.Popen([PYTHON, "sender.py", CONFIG_PATH])

    # block until sender is finished
    sender.wait()

    receiver.kill()

    time.sleep(1)

    # check if emulator is alive
    if emulator.poll() is None:
        print("Error, expected emulator to be done but it's still running.")
        emulator.kill()
        exit(1)

    # Compare the output of our two 
    diff = subprocess.run(["diff", SEND_FILE_PATH, RECV_FILE_PATH])

    if diff.returncode != 0:
        print("Error, some diff between sent and received files")
        exit(1)
    else:
        print("SUCCESS!")


if __name__ == "__main__":

    launch()

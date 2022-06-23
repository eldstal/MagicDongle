
# These are the heuristics supported, which help determine if a device is accepted by the host.
# The key is the name of the heuristic,
# the value is a dict of of { description, device_types=[], handler=class) }

# The class shall expose three methods:
# - setup will be called right after the device is created
# - test will be called after any user-configured test duration (--test-duration)
# - cleanup will be called before the device is torn down
#
# All methods will be called with (conf, devspec, gadget_path)
#
# test_function should return True if the device is deemed to have been active, i.e. it is
# recognized and accepted by the target USB host.

import copy
import time

import status

import heur.net.rx
import heur.serial.rx

import stimulation

HEURISTICS = {

  "net.rx": {
              "description": "Test if any data is received on the interface. Combine with --net-send-pcap to stimulate the host",
              "device_types": [ "net" ],
              "handler": heur.net.rx.RX
            },

  "serial.rx": {
              "description": "Test if any data is received on the serial port.",
              "device_types": [ "serial" ],
              "handler": heur.serial.rx.RX
            },
}

def list_heuristics(conf):
  return copy.deepcopy(HEURISTICS)


def user_friendly_device(conf, dev, path):
  devpath = None
  if dev["type"] == "net":
    devpath = heur.net.util.find_iface(conf, dev, path)
  elif dev["type"] == "serial":
    devpath = heur.serial.util.find_tty(conf, dev, path)
  if devpath is None:
    return path
  return devpath

def expand_heuristics_list(conf, pattern_list):
  if pattern_list is None:
    if conf.create_device:
      pattern_list = []
    elif conf.test_multiple_devices:
      pattern_list = ["all"]
    else:
      pattern_list = []

  all_heuristics = [ n for n,v in HEURISTICS.items() ]

  if "all" in pattern_list:
    return all_heuristics
  else:
    # Only allow the ones we actually know.
    return list(set(pattern_list) & set(all_heuristics))

# Provide a loaded and active gadget
# returns True heuristic tests indicate an active device
# returns False if the device appears inactive
# This is controlled by --and
def test_device(conf, dev, path):

  time.sleep(conf.setup_duration)

  # Send traffic or otherwise futz around with the new interface
  # Maybe we can make the host advertise itself!
  stimulation.stimulate_device(conf, dev, path)

  tests = {}
  for name, spec in HEURISTICS.items():
    if dev["type"] in spec["device_types"]:
      tests[name] = spec["handler"]()

  if len(tests) == 0:
    status.warn(f"No tests relevant for device {dev['name']} of type {dev['type']}.")
    return False

  if len(tests) > 1:
    status.info(f"{len(tests)} tests relevant for this device: {list(tests.keys())}")

  for name,obj in tests.items():
    try:
      obj.setup(conf, dev, path)
    except Exception as e:
      status.error(f"Failed to set up heuristic {name}: " + str(e))

  time.sleep(conf.test_duration)

  results = []
  for name,obj in tests.items():
    passed = False
    try:
      passed = obj.test(conf, dev, path)
    except Exception as e:
      status.error(f"Failed to measure heuristic {name}: " + str(e))

    results.append(passed)

  for name,obj in tests.items():
    try:
      obj.cleanup(conf, dev, path)
    except Exception as e:
      status.error(f"Failed to clean up after heuristic {name}: " + str(e))


  if conf.any:
    return any(results)
  else:
    return all(results)



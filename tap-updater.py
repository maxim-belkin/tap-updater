#!/usr/bin/env python3

import argparse
import os
import subprocess

from glob import glob
from os.path import splitext
from pprint import pprint

from collections import defaultdict

description = """
Determine batches in which it is safe to update packages in a tap.
"""

parser = argparse.ArgumentParser(description=description)
parser.add_argument('tap', help="Tap you'd like to update packages in.")
parser.add_argument("-d", "--debug", help="Display debugging messages.", action="store_true")
parser.add_argument("-v", "--verbose", help="Display verbose messages.", action="count", default=0)
parser.add_argument("--skip", dest='skiplist', help="White-space-separated list of formulae to skip.", nargs='*', default=[])
args = parser.parse_args()

tap_name = args.tap
skiplist = args.skiplist
VERBOSE = args.verbose
DEBUG = args.debug

# Tap folder
command = ["brew", "--repo", tap_name]
process = subprocess.run(command, capture_output=True)
this_tap_folder = process.stdout.decode("ascii").strip()

os.chdir(f"{this_tap_folder}/Formula")
formulae = sorted([ splitext( x )[0] for x in glob("*.rb") ])

outdated = {}
deps = {}

for formula in formulae:

  print(f"{formula:40s}", end='', flush=True)
  try:

    # 1. Skip what has to be skipped
    if formula in skiplist:
      if VERBOSE: print("skipping")
      continue

    # 2. Check if there is a new version of the formula
    command = ["brew", "livecheck", "-n", f"{tap_name}/{formula}"]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").strip()

    # 3. Go to the next formula if the current one is up-to-date
    if not stdout: print("\b"*40, end=''); continue

    # 4. Go to the next formula if output is not what we can process
    if " : " not in stdout or " ==> " not in stdout:
      if VERBOSE: print("Can't process output of 'brew livecheck'")
      continue

    # 5. Capture old and new versions
    old_version, new_version = stdout.split(" : ")[1].split(' ==> ')
    outdated[formula] = [old_version, new_version]

    if VERBOSE: print(f"{old_version:^12s} ~> {new_version:^12s}")

    command = ["brew", "deps", "--include-build", "--include-test", "--full-name", f"{tap_name}/{formula}"]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").split()

    # deps - deps from the tap being analyzed
    deps[formula] = list(map(lambda x: x.split("/")[-1], filter(lambda x: x.startswith(tap_name), stdout)))

    if DEBUG and deps[formula]:
      if not VERBOSE: print("")
      print(" - [DEBUG] dependencies:", ", ".join(deps[formula]))

    if not VERBOSE and not DEBUG:
      print("\b"*40, end='')

  except KeyboardInterrupt:
    if formula: print(f"Interrupted. I was processing '{formula}'")
    exit(130)
  except:
    if formula: print(f"Errored out. I was processing '{formula}'")
    exit(1)

# outdated_deps - deps from the tap being analyzed that are out of date
outdated_deps = {formula: list(filter(lambda x: x in outdated, deps[formula])) for formula in outdated}


# Sort by the number of outdated dependencies
sorted_outdated_deps = sorted(outdated_deps.items(), key = lambda x: len(x[1]))

# Check that there are at least SOME outdated dependencies
# that don't depend on other outdated dependencies
if all(deps[1]  for deps in sorted_outdated_deps):
  print(f"""Something is not right:
        All outdated dependencies in '{tap_name}' depend on each other.
        This can't be right. Please report this error to us by creating an issue.""")

separator = '=' * 96
print(f"{separator}\n{'Formula':40s}|{'Version change':^30s}| (Outdated) Dependencies\n{separator}")
for element in sorted_outdated_deps:
  formula = element[0]
  print(f"{formula:40s}| {outdated[formula][0]:^12s} ~> {outdated[formula][1]:^12s} |", " ".join(element[1]))
print(separator)

batches = defaultdict(list)
previous = 0

for element in sorted_outdated_deps:
  deps = element[1]
  key = len(deps)
  if previous and all([dep not in batches[previous] for dep in deps]):
      key = previous
  else:
      key = previous + 1

  batches[key].append(element[0])
  previous = key

for batch in batches:
  print(f"Batch {batch}:", " ".join(batches[batch]))

if DEBUG:
  print(" - [DEBUG]")
  pprint(sorted_outdated_deps)

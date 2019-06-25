#!/usr/bin/env python3

import os
import subprocess

from glob import glob
from os.path import splitext
from pprint import pprint

from collections import defaultdict

DEBUG = False

tap_name = "linuxbrew/xorg"

# Skipping these because the new versions that 'livecheck'
# gets for them are all wrong
skiplist = [
    "libvdpau-va-gl",
    "mesa",
    "libva-intel-driver",
    "libva"
    ]

# Tap folder
command = ["brew", "--repo", tap_name]
process = subprocess.run(command, capture_output=True)
this_tap_folder = process.stdout.decode("ascii").strip()

os.chdir(f"{this_tap_folder}/Formula")
formulae = sorted([ splitext( x )[0] for x in glob("*.rb") ])

outdated = {}
deps = {}
outdated_deps = {}

for formula in formulae:
  try:
    if formula in skiplist: print(f"{formula:20s} skipping"); continue
    command = ["brew", "livecheck", "-n", f"{tap_name}/{formula}"]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").strip()

    if not stdout: continue
    if " : " not in stdout or " ==> " not in stdout: continue

    old_version, new_version = stdout.split(" : ")[1].split(' ==> ')
    outdated[formula] = [old_version, new_version]
    print(f"{formula:20s} {old_version}\t{new_version}".expandtabs())

    command = ["brew", "deps", "--include-build", "--include-test", "--full-name", f"{tap_name}/{formula}"]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").split()
    this_tap_deps = list(map(lambda x: x[15:], filter(lambda x: x.startswith(tap_name), stdout)))
    deps[formula] = this_tap_deps
    if DEBUG: print(this_tap_deps)

  except KeyboardInterrupt:
    if formula: print(f"I was processing '{formula}'")
    continue
    # exit(130)

for formula in outdated:
  outdated_deps[formula] = list(filter(lambda x: x in outdated, deps[formula]))

# Sort by the number of outdated dependencies
sorted_outdated_deps = sorted(outdated_deps.items(), key = lambda x: len(x[1]))

# Check that there are at least SOME outdated dependencies
# that don't depend on other outdated dependencies
if all(deps[1]  for deps in sorted_outdated_deps):
  print(f"""Something is not right:
        All outdated dependencies in '{tap_name}' depend on each other.
        This can't be right. Please report this error to us by creating an issue.""")

print(f"\n{'='*40}\n{'Formula':20s} (Outdated) Dependencies\n{'='*40}")
for element in sorted_outdated_deps:
  print(f"{element[0]:20s}|", " ".join(element[1]))
print('='*40)

batches = defaultdict(list)
previous = -1

for element in sorted_outdated_deps:
  deps = element[1]
  key = len(deps)
  if previous >=0 and all([dep not in batches[previous] for dep in deps]):
      key = previous
  else:
      key = previous + 1

  batches[key].append(element[0])
  previous = key

for batch in batches:
  print(f"Batch {batch}:", " ".join(batches[batch]))

if DEBUG: pprint(sorted_outdated_deps)

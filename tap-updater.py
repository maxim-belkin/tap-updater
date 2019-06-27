#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys

from glob import glob
from pprint import pprint

from collections import defaultdict

description = """
Determine batches in which it is safe to update packages in a tap.
"""

parser = argparse.ArgumentParser(description=description)
group = parser.add_mutually_exclusive_group()
group.add_argument("-v", "--verbose", help="Display verbose messages.", action="count", default=0)
group.add_argument("-q", "--quiet", help="Suppress any intermediate output.", action="store_true")
parser.add_argument("-d", "--debug", help="Display debugging messages.", action="store_true")
parser.add_argument('taps_or_formulae', help="Taps or formulae you'd like to update.", nargs='+')
parser.add_argument('-a', '--all', help="Don't limit analysis to formulae in a single tap even if only one tap is provided", action="store_true")
parser.add_argument("-s", "--skip", help="White-space-separated list of formulae to skip.", nargs='+', metavar='formula', default=[])
parser.add_argument("--no-summary", help="Hide summary table (Default: False)", action="store_true")
args = parser.parse_args()

taps_or_formulae = args.taps_or_formulae
skiplist = args.skip

VERBOSE = args.verbose
DEBUG = args.debug
QUIET = args.quiet
SUMMARY = not args.no_summary
PROCESS_ALL_FORMULAE = args.all

# 'known_taps': taps that we know of
command = ["brew", "tap"]
process = subprocess.run(command, capture_output=True)
known_taps = process.stdout.decode("ascii").split()
del process, command

formulae = set()
single_tap = len(taps_or_formulae) == 1
formula_file = {}

for element in taps_or_formulae:

  if element in known_taps:
    # IF: This is a tap we know.

    tap_name = element

    # Tap folder
    command = ["brew", "--repo", tap_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      print(process.stderr.decode("ascii").strip(), file=sys.stderr)
      exit(1)

    this_tap_folder = process.stdout.decode("ascii").strip()
    if not os.path.exists(this_tap_folder):
      print(f"Error: '{this_tap_folder}' does not exist", file=sys.stderr)
      exit(1)

    if os.path.exists(f"{this_tap_folder}/Formula"):
      os.chdir(f"{this_tap_folder}/Formula")
    else:
      os.chdir(this_tap_folder)

    rbfiles = glob("*.rb")
    names = (os.path.splitext( rbfile )[0] for rbfile in rbfiles)
    full_names = list(f"{tap_name}/{name}" for name in names)

    formulae = formulae.union(full_names)
    # tap[f] = tap_name for f in addition

    for full_name, rbfile in zip(full_names, rbfiles):
      formula_file[full_name] = f"{os.path.abspath('.')}/{rbfile}"

  else:
    # ELSE:
    # This is not a tap we know...
    # So we assume that this is a formula.
    # We (could but) don't want to tap any new taps

    if element.count("/") == 0:
      # 0 slashes -- "core" formula    (e.g.: gcc)
      formula_name = element
      tap_name = "homebrew/core"
    elif element.count("/") == 2:
      # 2 slashes -- full-name formula (e.g.: linuxbrew/xorg/mesa)
      formula_name = element.split("/")[-1]
      tap_name = "/".join(element.split("/")[:2])
    else:
      print(f"Skipping {element} because its name is suspicious...")
      continue

    full_formula_name = f"{tap_name}/{formula_name}"
    command = ["brew", "formula", full_formula_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      print(f"Error: can't process {element}:\n", process.stderr.decode("ascii").strip())
      exit(1)

    formula_file[full_formula_name] = process.stdout.decode("ascii").strip()
    formulae = formulae.union([full_formula_name])


if PROCESS_ALL_FORMULAE:
  command = ["brew", "deps", "--include-build", "--include-test", "--full-name", "--union", *list(formulae)]
  process = subprocess.run(command, capture_output=True)
  extra_formulae = process.stdout.decode("ascii").split()
  extra_formulae = set([f"homebrew/core/{x}" if x.count("/") == 0 else x for x in extra_formulae])

  for element in extra_formulae:
    if VERBOSE: print(element)
    if element.count("/") != 2:
      print(f"Error: can not process {element}.")
      exit(1)

    formula_name = element.split("/")[-1]
    tap_name = "/".join(element.split("/")[:2])

    full_formula_name = f"{tap_name}/{formula_name}"
    command = ["brew", "formula", full_formula_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      print(f"Error: can't process {element}:\n", process.stderr.decode("ascii").strip())
      exit(1)

    formula_file[full_formula_name] = process.stdout.decode("ascii").strip()
    formulae = formulae.union([full_formula_name])

deps = {}
old_versions = {}
new_versions = {}

for formula in formulae:

  if not QUIET: print(formula, end=' ', flush=True)

  try:

    # 1. Skip what has to be skipped
    if formula in skiplist:
      if VERBOSE: print("skipping")
      continue

    # 2. Check if there is a new version of the formula
    command = ["brew", "livecheck", "-n", formula]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").strip()

    # 3. Go to the next formula if the current one is up-to-date
    # For all sorcery see:
    # https://en.m.wikipedia.org/wiki/ANSI_escape_code#CSI_sequences
    if not stdout:
      if not QUIET: print("\033[2K\033[1G", end='')
      continue

    # 4. Go to the next formula if output is not what we can process
    if " : " not in stdout or " ==> " not in stdout:
      if VERBOSE: print("Can't process output of 'brew livecheck'")
      continue

    # 5. Capture old and new versions
    old_versions[formula], new_versions[formula] = stdout.split(" : ")[1].split(' ==> ')

    if VERBOSE: print(f"{old_versions[formula]} ~> {new_versions[formula]}")

    command = ["brew", "deps", "--include-build", "--include-test", "--full-name", formula]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").split()

    # deps - deps (up-to-date and outdated)
    deps[formula] = [f"homebrew/core/{x}" if x.count("/") == 0 else x for x in stdout]

    # Don't analyse formulae from other taps when not required
    if single_tap and not PROCESS_ALL_FORMULAE:
      tap_name = formula.rsplit("/", 1)[0]
      deps[formula] = list(filter(lambda x: x.startswith(tap_name), deps[formula]))

    if DEBUG and deps[formula]:
      if not VERBOSE: print("")
      print(f"DEBUG deps[{formula}]:", ", ".join(deps[formula]))

    if not VERBOSE and not DEBUG and not QUIET:
      print("\033[2K\033[1G", end='')

  except KeyboardInterrupt:
    if formula: print(f"Interrupted. I was processing '{formula}'")
    exit(130)
  except:
    if formula: print(f"Errored out. I was processing '{formula}'")
    exit(1)

# outdated_deps - deps (from the tap being analyzed) that are outdated
outdated_deps = {formula: list(filter(lambda x: x in old_versions, deps[formula])) for formula in old_versions}

# sorted_outdated_deps - outdated_deps sorted by the number of outdated dependencies
sorted_outdated_deps = sorted(outdated_deps.items(), key = lambda x: len(x[1]))

# Check that there are at least SOME outdated dependencies
# that don't depend on other outdated dependencies
if all(deps[1]  for deps in sorted_outdated_deps):
  print(f"""Something is not right:
        All outdated dependencies in '{tap_name}' depend on each other.
        This can't be right. Please report this error to us by creating an issue.""")

if SUMMARY:
  fname_length = list(map(lambda x: len(x[0]), sorted_outdated_deps))
  old_vers_len = [len(old_versions[f]) for f in old_versions]
  new_vers_len = [len(new_versions[f]) for f in new_versions]
  deps_lengths = list(map(lambda x: len(" ".join(x[1]))+1, sorted_outdated_deps))

  col1_len = str(max(fname_length + [7]) + 2) # 7 == len("Formula")
  col2_len = str(max(old_vers_len + [15]) + 2) # 15 == len("Current version")
  col3_len = str(max(new_vers_len + [11]) + 2) # 11 == len("New version")
  col4_len = str(min(max(deps_lengths + [21]), 32) + 2) # 21 == len("Outdated dependencies")
  separator = '=' * eval(f"{col1_len}+{col2_len}+{col3_len}+{col4_len}+3")

  header = (
        f"\n{separator}\n"
        f"{'Formula':{'^' + col1_len}}|"
        f"{'Current version':{'^' + col2_len}}|"
        f"{'New version':{'^' + col3_len}}|"
        f"{'Outdated dependencies':{'^' + col4_len}}"
        f"\n{separator}"
      )

  print(header)
  for element in sorted_outdated_deps:
    formula = element[0]
    last_column = " " + " ".join(element[1])
    table_line = (
      f"{formula:{col1_len}}|"
      f"{old_versions[formula]:{'^' + col2_len}}|"
      f"{new_versions[formula]:{'^' + col3_len}}|"
      f"{last_column:{col4_len}}"
        )
    print(table_line)
  print(f"{separator}\n")

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

if batches[1]:
  print("\nSuggested commands for updating formulae in Batch 1:\n")
  for formula in batches[1]:
    pattern = rf'\s*url "([^ ]*{old_versions[formula]}[^ ]*)"'
    #filename = f"{this_tap_folder}/Formula/{formula}.rb"
    filename = formula_file[formula]
    with open(filename, 'r') as fid:
      for line in fid:
        match = re.search(pattern, line)
        if match:
          old_url = match.group(1)
          new_url = old_url.replace(old_versions[formula], new_versions[formula], -1)
          print(f'brew bump-formula-pr --no-browse --url={new_url} {tap_name}/{formula}')

  print((
    "\nPlease verify that URLs exist before executing the above commands! "
    "Consider adding 'version \"x.y.z\" to the formula if detected 'new_version' is likely "
    " to cause problems for Homebrew version detection mechanism"
    ))

if DEBUG:
  print(" - [DEBUG]")
  pprint(sorted_outdated_deps)

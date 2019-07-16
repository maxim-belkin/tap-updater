#!/usr/bin/env python3

import argparse
import logging
import os
import pprint
import re
import subprocess
import sys

from collections import defaultdict
from glob import glob

description = """
Determine batches in which it is safe to update individual formulae and taps.
"""

parser = argparse.ArgumentParser(description=description)
group = parser.add_mutually_exclusive_group()
group.add_argument("-v", "--verbose", help="Display verbose messages.", action="count", default=0)
group.add_argument("-q", "--quiet", help="Suppress any intermediate output.", action="count", default=0)
parser.add_argument("-d", "--debug", help="Display debugging messages.", action="store_true")
parser.add_argument('-a', '--all', help="Don't limit analysis to formulae in a single tap even if only one tap is specified.", action="store_true")
parser.add_argument("-s", "--skip", help="White-space-separated list of formulae to skip.", nargs='+', metavar='formula', default=[])
parser.add_argument("--log-file", help="Log file name (Default: tap_updater.log).", action="store", metavar='file', default='tap_updater.log')
parser.add_argument('taps_or_formulae', help="Taps or formulae you'd like to update.", nargs='+')
args = parser.parse_args()

# Process command-line arguments
TAPS_OR_FORMULAE = args.taps_or_formulae
SKIPLIST = args.skip
VERBOSE = args.verbose
DEBUG = args.debug
QUIET = args.quiet
PROCESS_ALL_TAPS = args.all
LOGFILE = args.log_file

logger = logging.getLogger("TAP UPDATER")
logger.level = 1
formatter = logging.Formatter('%(levelname)-8s %(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logfile = logging.FileHandler(LOGFILE)
logfile.level = 10 # DEBUG for now
logfile.formatter = formatter
# console = logging.StreamHandler()
# console.level = 50 # CRITICAL only...
# console.formatter = formatter
logger.addHandler(logfile)
# logger.addHandler(console)

def quit(args):
  print("\033[2K\033[1G", end='')
  exit(args)

def log(message, level=20, indent=0, prefix=''):
  """Write message to the screen and to the log file."""

  if not isinstance(level, (int, float)):
    raise ValueError(f"""Unknown message level: {level}""")

  if not isinstance(prefix, str):
    raise ValueError(f"""Prefix must be of type str. Provided: {type(prefix)} (prefix={prefix})""")

  message_level = level + (VERBOSE - QUIET)*10
  # To suppress messages:
  #    level 20 requires QUIET = 1
  #    level 30 requires QUIET = 2
  #    level 40 requires QUIET = 3
  #    level 50 requires QUIET = 4
  if isinstance(message, str):
    lines = message.split("\n")
  elif isinstance(message, (list, tuple)):
    lines = [str(x) for x in message]
  else:
    lines = [pprint.pformat(message)]

  for n, x in enumerate(lines, 1):
    prefix0 = f"{n:3}. " if prefix == 'enum' else prefix
    line = "  " * indent + prefix0 + x
    if message_level > 10 or DEBUG:
      print("\033[2K\033[1G" + line, end='', flush=True)
      if DEBUG: print()
    logger.log(level, line)

log("Starting 'Tap Updater'")

# 'KNOWN_TAPS': taps that we know
command = ["brew", "tap"]
process = subprocess.run(command, capture_output=True)
KNOWN_TAPS = process.stdout.decode("ascii").split()
del process, command
log("Local taps")
log(KNOWN_TAPS, indent=1, prefix='enum')

formulae = set()
formula_file = {}
# SINGLE_TAP = len(TAPS_OR_FORMULAE) == 1
TAP_NAME = None

# Process command-line arguments
for element in TAPS_OR_FORMULAE:
  log("Processing: %s" % element)
  if element in KNOWN_TAPS: # IF: This is a tap we know.
    log("%s is a tap" % element, level=10)
    tap_name = element

    # 1. Detect tap location
    # CREATED VARIABLE: 'this_tap_folder'
    command = ["brew", "--repo", tap_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log(process.stderr.decode("ascii").strip(), level=50)
      exit(1)
    this_tap_folder = process.stdout.decode("ascii").strip()
    del command, process

    # Formulae can be stored in different subfolders, if at all.
    # User specified a tap, so we want to get a list of all 
    # formulae in that tap.
    for suffix in ["Formula", "HomebrewFormula", ""]:
      if os.path.exists(f"{this_tap_folder}/{suffix}"):
        os.chdir(f"{this_tap_folder}/{suffix}")
        break
    del suffix

    # Find all *.rb files
    rbfiles = glob("*.rb")
    if not rbfiles: continue # I mean, who would do that?... but, you know,...

    # Remove .rb from filenames
    names = (os.path.splitext( rbfile )[0] for rbfile in rbfiles)

    # Prefix tap name to formulae names
    full_names = list(f"{tap_name}/{name}" for name in names)

    # Add formulae from this tap to the list of formulae to check
    formulae = formulae.union(full_names)

    for full_name, rbfile in zip(full_names, rbfiles):
      formula_file[full_name] = f"{os.path.abspath('.')}/{rbfile}"

    del rbfiles, names, full_names

  else: # This is not a tap we know...

    # We assume that this is a formula.
    # We (could but) don't tap any new taps

    n_slashes = element.count("/")

    if n_slashes == 0:
      # 0 slashes -- "core" formula    (e.g.: gcc)
      formula_name = element
      tap_name = "homebrew/core"
      log("%s is a core formula" % element, level=10)
    elif n_slashes == 2:
      # 2 slashes -- full-name formula (e.g.: linuxbrew/xorg/mesa)
      formula_name = element.split("/")[-1]
      tap_name = "/".join(element.split("/")[:2])
      log("%s is a '%s' formula" % (element, tap_name), level=10)
    elif n_slashes == 1:
      # 1 slash -- tap (e.g. linuxbrew/xorg) but it is not tapped
      log("Skipping '%s' because it looks like a tap. Consider tapping it before using 'Tap Updater'." % element, level=30)
      continue
    else:
      log("Can not process '%s" % element, level=50)
      exit(1)

    del n_slashes

    full_formula_name = f"{tap_name}/{formula_name}"
    command = ["brew", "formula", full_formula_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log("Error: can't process %s:\n%s" % (element, process.stderr.decode("ascii").strip()), level=50)
      exit(1)

    formula_file[full_formula_name] = process.stdout.decode("ascii").strip()
    formulae = formulae.union([full_formula_name])

  # this is after if/else and inside 'for element in'
  log(f"""Tap: {tap_name}""", level=10)
  log("Formula(e): %s" % "\n    ".join(formulae), level=10)

  if not PROCESS_ALL_TAPS:
    if TAP_NAME is not None and TAP_NAME != tap_name:
      logg(f"Error processing {element}: Can't process formulae from different taps without '-a' flag.", level=50)
      exit(1)
    TAP_NAME = tap_name

if len(formulae) == 0:
  log("No formulae to process.", level=50)
  exit(1)

#######################################################################################

log("Obtaining dependencies (including those necessary for building and testing)")
command = ["brew", "deps", "--include-build", "--include-test", "--full-name", "--union", *list(formulae)]
process = subprocess.run(command, capture_output=True)
extra_formulae = process.stdout.decode("ascii").split()
extra_formulae = set([f"homebrew/core/{x}" if x.count("/") == 0 else x for x in extra_formulae])

if not PROCESS_ALL_TAPS:
  log(f"Filtering out dependencies from taps other than {TAP_NAME}")
  log(f"Formulae before filtering: {len(extra_formulae)}")
  extra_formulae = list(filter(lambda x: x.startswith(TAP_NAME), extra_formulae))
  log(f"Formulae after filtering: {len(extra_formulae)}")


log("Adding %d formulae" % len(extra_formulae))

for num, element in enumerate(extra_formulae, 1):
    log(element, level=10, indent=1, prefix=f"{num:3}. ")

    formula_name = element.split("/")[-1]
    tap_name = "/".join(element.split("/")[:2])

    command = ["brew", "formula", element]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log("\nError: can't process %s:\n%s" % (element, process.stderr.decode("ascii").strip()), level=50)
      exit(1)

    location = process.stdout.decode("ascii").strip()
    if element in formula_file and  location != formula_file[element]:
      log(f"Old location: '{formula_file[element]}'\nNew location: '{location}'\n", level=50)
      exit(1)
    formula_file[element] = location
    formulae = formulae.union([element])

    # Erase current line
    if not QUIET: print("\033[2K\033[1G", end='')


#### Done adding additional dependencies

deps = {}
old_versions = {}
new_versions = {}

# Now 'formulae' includes formulae (from taps or individual)
# specified on the command line as well as all dependencies.
for formula in formulae:
  if not QUIET: print(f"Checking {formula}...", end=' ', flush=True)
  log(f"Checking {formula}...")
  # Using 'try/except' to catch interrupts
  try:

    # 1. Skip what has to be skipped
    if formula in SKIPLIST:
      if VERBOSE: print("skipping")
      log("skipping %s" % formula, level=10)
      continue

    # logger.debug("Processing %s" % formula)

    # 2. Check if there is a new version of the formula
    command = ["brew", "livecheck", "-n", formula]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").strip()

    # 3. Go to the next formula if the current one is up-to-date
    # Sorcery is described here:
    # https://en.m.wikipedia.org/wiki/ANSI_escape_code#CSI_sequences
    if not stdout:
      if not QUIET: print("\033[2K\033[1G", end='')
      continue

    # 4. Go to the next formula if output is not what we can process
    if " : " not in stdout or " ==> " not in stdout:
      log("%s: can't process output of 'brew livecheck'" % formula, level=30)
      continue

    # 5. Capture old and new versions
    old_versions[formula], new_versions[formula] = stdout.split(" : ")[1].split(' ==> ')

    # if VERBOSE:
    log("new version found: %s => %s" % (old_versions[formula], new_versions[formula]))

    # Find dependencies of the current formula
    command = ["brew", "deps", "--include-build", "--include-test", "--full-name", formula]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").split()
    del command, process

    # deps - deps (up-to-date and outdated)
    deps[formula] = [f"homebrew/core/{x}" if x.count("/") == 0 else x for x in stdout]

    # Don't analyze dependencies from other taps when not required
    if not PROCESS_ALL_TAPS:
      tap_name = formula.rsplit("/", 1)[0]
      deps[formula] = list(filter(lambda x: x.startswith(tap_name), deps[formula]))

    if deps[formula]:
      log("Dependencies:%s" % "".join("\n* " + x for x in deps[formula]), level=10, indent=1)

    if not VERBOSE and not DEBUG and not QUIET:
      print("\033[2K\033[1G", end='')

  except KeyboardInterrupt:
    if formula: log(f"Interrupted. I was processing '{formula}'")
    exit(130)
  except:
    if formula: log(f"Errored out. I was processing '{formula}'")
    exit(1)

# outdated_deps - deps (from the tap being analyzed) that are outdated
outdated_deps = {formula: list(filter(lambda x: x in old_versions, deps[formula])) for formula in old_versions}

# sorted_outdated_deps - outdated_deps sorted by the number of outdated dependencies
sorted_outdated_deps = sorted(outdated_deps.items(), key = lambda x: len(x[1]))

# Check that there are at least SOME outdated dependencies
# that don't depend on other outdated dependencies

if sorted_outdated_deps and all(d[1] for d in sorted_outdated_deps):
  message = f"""\
      Something is not right:
      All outdated dependencies in depend on each other.
      This can't be right. Please report this error to us by creating an issue."""
  log(message, level=40)

if not sorted_outdated_deps: log("Nothing to update.\n")

if QUIET < 2 and sorted_outdated_deps:
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
        f"{separator}\n"
        f"{'Formula':{'^' + col1_len}}|"
        f"{'Current version':{'^' + col2_len}}|"
        f"{'New version':{'^' + col3_len}}|"
        f"{'Outdated dependencies':{'^' + col4_len}}"
        f"\n{separator}"
      )

  log(header)

  for element in sorted_outdated_deps:
    formula = element[0]
    last_column = " " + " ".join(element[1])
    table_line = (
      f"{formula:{col1_len}}|"
      f"{old_versions[formula]:{'^' + col2_len}}|"
      f"{new_versions[formula]:{'^' + col3_len}}|"
      f"{last_column:{col4_len}}"
        )
    log(table_line)
  log(f"{separator}")

batches = defaultdict(list)
previous = 0

for element in sorted_outdated_deps:
  deps = element[1]
  if previous and all([dep not in batches[previous] for dep in deps]):
      key = previous
  else:
      key = previous + 1

  batches[key].append(element[0])
  previous = key

for batch in batches:
  log(f'Batch {batch}: {" ".join(batches[batch])}')

if batches[1]:
  log("Suggested commands for updating formulae in Batch 1:")
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
          log("brew bump-formula-pr --no-browse --url=%s %s" % (new_url, formula), indent=1)
          break
      else:
          log("%s: couldn't match url in the formula file" % formula, level=40, indent=1)

  log(
    """
Please verify that URLs exist before executing the above commands!
Consider adding 'version \"x.y.z\"' to the formula if detected 'new_version' is likely
to cause problems for Homebrew version detection mechanism.
    """
    )

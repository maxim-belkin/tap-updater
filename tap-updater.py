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
from pathlib import Path

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
###

# Set up the logger
logger = logging.getLogger("TAP UPDATER")
logger.level = 1
formatter = logging.Formatter('%(levelname)-8s %(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logfile = logging.FileHandler(LOGFILE)
logfile.level = 10 # DEBUG for now
logfile.formatter = formatter
logger.addHandler(logfile)

# console = logging.StreamHandler()
# console.level = 50 # CRITICAL only...
# console.formatter = formatter
# logger.addHandler(console)

def format_message(message, *, prefix='', indent=0):
  """Format message into a list of lines for logging purposes."""

  if isinstance(message, str):
    lines = message.split("\n")
  elif isinstance(message, (list, tuple, set)):
    lines = message #[format_message(x, prefix=prefix, indent=indent) for x in message]
  else:
    if DEBUG:
      lines = [pprint.pformat(message)]
    else:
      raise ValueError(f"""Unknown message type: {type(message)}.""")

  if prefix.startswith(('enum', 'num', 'ind')):
    start = 0 if prefix.startswith('ind') else 1
    lines = [f"{index:3}. {line}" for line, index in zip(lines, range(start, len(lines) + start))]
  elif prefix:
    lines = [f"{prefix} {line}" for line in lines]

  if indent:
    lines = ["  " * indent + line for line in lines]

  return lines


def log(message, *, level=20, indent=0, prefix='', exit_with_code=None):
  """Write message to the screen and to the log file."""

  if not isinstance(level, int):
    raise ValueError(f"""Unknown message level type: {type(level)}. Level must be integer.""")
  elif level < logger.level:
    if DEBUG:
      log(f"Not recording message with level {level}.\nThe message was:\n{message}", level=logger.level)
    else:
      raise ValueError(f"""Level ({level}) can not be lower than that of the logger ({logger.level})""")

  if not isinstance(indent, int):
    raise ValueError(f"""Unknown message indent level type: {type(indent)}.""")
  elif indent < 0:
    raise ValueError(f"""Indent can not be negative. Supplied value: {indent}.""")

  if not isinstance(prefix, str):
    raise ValueError(f"""Message prefix must be of type 'str'.""")

  worthiness = level + (VERBOSE - QUIET)*10
  # To suppress messages:
  # level 20 ==> QUIET = 1
  # level 30 ==> QUIET = 2
  # level 40 ==> QUIET = 3
  # level 50 ==> QUIET = 4

  lines = format_message(message, prefix=prefix, indent=indent)

  for line in lines:
    logger.log(level, line)

    if worthiness > 10 or DEBUG:
      # Erase line and print it to the screen
      print("\033[2K\033[1G" + line, end='', flush=True)
      if DEBUG: print()

  if isinstance(exit_with_code, int):
    exit(exit_with_code)

## End of 'log' function

# from https://stackoverflow.com/a/312464/7410631
def chunks(object, n):
  """Yield successive n-sized chunks from 'object'."""
  if not hasattr(object, '__len__'): object = [object]
  if not hasattr(object, '__getitem__'): object = list(object) # sets have no 'getitem'
  for i in range(0, len(object), n): yield object[i : i+n]

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
TAP_NAME = None

if SKIPLIST:
  SKIP_TAPS = []
  SKIP_FORMULAE = []
  for item in SKIPLIST:
    n = item.count("/")
    if n not in range(3):
      log(f"Don't know how to interprete {item} in skip list", exit_with_code=1)
    if n == 0:
      SKIP_FORMULAE.append(f"homebrew/core/{item}")
    elif n == 1:
      SKIP_TAPS.append(item)
    else:
      SKIP_FORMULAE.append(item)


# Process command-line arguments
for element in TAPS_OR_FORMULAE:
  log("Processing command-line argument: %s" % element)

  # skip elements that match items in the skip-list
  if element in SKIPLIST:
      log("%s " % element, level=10)
      continue

  if element in KNOWN_TAPS: # IF: This is a tap we know.
    log("%s is a tap" % element, level=10)
    tap_name = element

    # 1. Detect tap location
    # CREATED VARIABLE: 'this_tap_folder'
    command = ["brew", "--repo", tap_name]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log(process.stderr.decode("ascii").strip(), level=50, exit_with_code=1)
    this_tap_folder = process.stdout.decode("ascii").strip()
    del command, process
    log("Tap location: %s" % this_tap_folder, level=10)

    # Formulae can be stored in different subfolders, if at all.
    # User specified a tap, so we want to get a list of all 
    # formulae in that tap.
    for suffix in ["Formula", "HomebrewFormula", ""]:
      if os.path.exists(f"{this_tap_folder}/{suffix}"):
        os.chdir(f"{this_tap_folder}/{suffix}")
        break
    del suffix
    log("Folder with formulae is located at %s" % os.path.abspath("."), level=10)

    # Find all *.rb files
    rbfiles = glob("*.rb")
    if not rbfiles: continue # I mean, who would do that?... but, you know,...
    log("Found %d formulae" % len(rbfiles), level=10)

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

    command = ["brew", "formula", element]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log("Error: can't process %s:\n%s" % (element, process.stderr.decode("ascii").strip()), level=50, exit_with_code=1)

    rbfile_location = Path(process.stdout.decode("ascii").strip())
    formula_name = rbfile_location.stem
    tap_name = "/".join(rbfile_location.parts[-4:-2]).replace("homebrew-","")

    full_formula_name = f"{tap_name}/{formula_name}"

    if full_formula_name in SKIPLIST or formula_name in SKIPLIST:
      log("skipping %s" % element, level=10, prefix='!')
      continue

    formula_file[full_formula_name] = rbfile_location
    formulae = formulae.union([full_formula_name])

  # this is after if/else and inside 'for element in'
  # log(f"""Tap: {tap_name}""", level=10)
  # log("Formula(e):", level=10)
  # log(formulae, level=10, indent=1, prefix='enum')

  if not PROCESS_ALL_TAPS:
    if TAP_NAME is not None and TAP_NAME != tap_name:
      log(f"Error processing {element}: can't process formulae from different taps.\nConsider using '-a' flag.", level=50, exit_with_code=1)
    TAP_NAME = tap_name

if len(formulae) == 0:
  log("No formulae to process.", level=50, exit_with_code=0)

#######################################################################################

log("Obtaining dependencies (including those necessary for building and testing)")
extra_formulae = set()
for chunk in chunks(formulae, 5):
  command = ["brew", "deps", "--include-build", "--include-test", "--full-name", "--union", *chunk]
  process = subprocess.run(command, capture_output=True)
  deps = process.stdout.decode("ascii").split()
  deps = set([f"homebrew/core/{d}" if d.count("/") == 0 else d for d in deps])
  extra_formulae.update(deps)
  if DEBUG: print(".", end='', flush=True)
if DEBUG: print()

extra_formulae.difference_update(formulae)
log("Found %d build- and test-time dependencies" % len(extra_formulae))
log(extra_formulae, indent=1, prefix='num')

if extra_formulae and not PROCESS_ALL_TAPS:
  log(f"Filtering out dependencies from taps other than {TAP_NAME}.")
  log("Hint: use `-a` (`--all`) flag to skip this step.")

  len_before = len(extra_formulae)
  extra_formulae = list(filter(lambda x: x.startswith(TAP_NAME) and x not in formulae, extra_formulae))
  log(f"before: {len_before} formula(e)", level=10, indent=1)
  log(f"after: {len(extra_formulae)} formula(e)", level=10, indent=1)


log("Adding %d dependencies" % len(extra_formulae))

for num, element in enumerate(extra_formulae, 1):
    log(element, level=10, indent=1, prefix=f"{num:3}. ")

    formula_name = element.split("/")[-1]
    tap_name = "/".join(element.split("/")[:2])

    command = ["brew", "formula", element]
    process = subprocess.run(command, capture_output=True)
    if process.stderr:
      log("\nError: can't process %s:\n%s" % (element, process.stderr.decode("ascii").strip()), level=50, exit_with_code=1)

    location = process.stdout.decode("ascii").strip()
    if element in formula_file and  location != formula_file[element]:
      log(f"Old location: '{formula_file[element]}'\nNew location: '{location}'\n", level=50, exit_with_code=1)
    formula_file[element] = location
    formulae.update([element])

#### Done adding additional dependencies

deps = {}
old_versions = {}
new_versions = {}

# Now 'formulae' includes formulae (from taps or individual)
# specified on the command line as well as all dependencies.

log("Checking %d formulae" % len(formulae))
for formula in formulae:

  log(f"Checking {formula}...", indent=1, prefix='*')

  # Using 'try/except' to catch interrupts
  try:

    # 1. Skip what has to be skipped
    if formula in SKIPLIST:
      log("skipping %s" % formula, level=10, indent=2, prefix='!')
      continue

    # 2. Check if there is a new version of the formula
    command = ["brew", "livecheck", "-n", formula]
    process = subprocess.run(command, capture_output=True)
    stdout = process.stdout.decode("ascii").strip()

    # 3. Go to the next formula if the current one is up-to-date
    if not stdout:
      continue

    # 4. Go to the next formula if output is not what we can process
    if " : " not in stdout or " ==> " not in stdout:
      log("%s: can't process output of 'brew livecheck'" % formula, level=30, indent=2, prefix='!')
      continue

    # 5. Capture old and new versions
    old_versions[formula], new_versions[formula] = stdout.split(" : ")[1].split(' ==> ')

    # if VERBOSE:
    log("new version found: %s => %s" % (old_versions[formula], new_versions[formula]), indent=2, prefix='-')

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
      log("dependencies:", level=10, indent=2, prefix="-")
      log(deps[formula], level=10, indent=3, prefix="num")

    if not VERBOSE and not DEBUG and not QUIET:
      print("\033[2K\033[1G", end='')

  except KeyboardInterrupt:
    if formula: log(f"Interrupted. I was processing '{formula}'", exit_with_code=130)
  except:
    if formula: log(f"Errored out. I was processing '{formula}'", exit_with_code=1)

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

# Homebrew Tap Updater

[Tap Updater](https://github.com/maxim-belkin/tap-updater) is a tool
that figures out the order in which it is safe to update packages
in a Homebrew tap.

## How to use

Tap Updater can be used to figure out the order in which to update formulae
in a single tap:

```sh
./tap-updater.py linuxbrew/xorg
```

Or it can be used to figure out the order in which to update a single formula
with all of its (outdated) dependencies:

```sh
./tap-updater.py linuxbrew/xorg/mesa
```

By default, Tap Updater assumes that dependencies from other taps are up-to-date.
You can instruct Tap Updater to check all dependencies regardless of the tap they're in with `-a` / `--all` flag:

```sh
./tap-updater.py -a linuxbrew/xorg/mesa
```

To skip some formulae in a tap from analysis, use `--skip` flag
followed by the formulae you'd like to skip:

```sh
./tap-updater.py linuxbrew/xorg --skip mesa libvai libvdpau-va-gl
```

Here is an example of output produced by Tap Updater:

```
$ python3 tap-updater.py  linuxbrew/extra

=====================================================================
   Formula   | Current version | New version | Outdated dependencies
=====================================================================
aws-vault    |      4.6.0      |    4.6.1    |
lm_sensors   |      3.4.0      |    3-5-0    |
singularity  |      2.6.0      | 3.3.0-rc.1  |
strace       |      4.24       |     5.1     |
=====================================================================

Batch 1: aws-vault lm_sensors singularity strace
Please verify that suggested URLs exist before proceeding!
brew bump-formula-pr --url=https://github.com/99designs/aws-vault/archive/v4.6.1.tar.gz linuxbrew/extra/aws-vault
brew bump-formula-pr --url=https://ftp.gwdg.de/pub/linux/misc/lm-sensors/lm_sensors-3-5-0.tar.bz2 linuxbrew/extra/lm_sensors
brew bump-formula-pr --url=https://github.com/singularityware/singularity/releases/download/3.3.0-rc.1/singularity-3.3.0-rc.1.tar.gz linuxbrew/extra/singularity
brew bump-formula-pr --url=https://github.com/strace/strace/releases/download/v5.1/strace-5.1.tar.xz linuxbrew/extra/strace
```

Tap Updater outputs "batches" of formulae in which packages can be updated.
Formulae in a specific batch can be updated in any order.
However, PRs to update formulae from the next batch should not be created
until all formulae from the current batch have been updated.

**Important:** Create Pull Requests to update formulae in **_Batch 1_**.

The process of creating PRs to update formulae is (still) semi-automatic:
you can use `brew bump-formula-pr --url=... formula-name` suggested by
Tap Updater but make sure to check that suggested URLs exist.

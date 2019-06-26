# Homebrew Tap Updater

[Tap Updater](https://github.com/maxim-belkin/tap-updater) is a tool
that figures out the order in which it is safe to update packages
in a Homebrew tap.

## How to use

Execute the script followed by the tap name, for example, like so:

```sh
./tap-updater.py linuxbrew/xorg
```

To skip some formulae in a tap from analysis, use `--skip` flag
followed by the formulae you'd like to skip:

```sh
./tap-updater.py linuxbrew/xorg --skip mesa libvai libvdpau-va-gl
```

Here is an example of output produced by Tap Updater:

```
================================================================================================
Formula                                 |        Version change        | (Outdated) Dependencies
================================================================================================
lm_sensors                              |    3.4.0     ~>    3-5-0     |
man-db                                  |    2.8.4     ~>    2.8.5     |
singularity                             |    2.6.0     ~>  3.3.0-rc.1  |
strace                                  |     4.24     ~>     5.1      |
================================================================================================
Batch 1: lm_sensors man-db singularity strace
```

Tap Updater outputs "batches" of formulae in which packages can be updated.
Formulae in a specific batch can be updated in any order.
However, PRs to update formulae from the next batch should not be created
until all formulae from the current batch have been updated.

**Important:** Create Pull Requests to update formulae in **_Batch 1_**.

The process of creating PRs to update formulae is (still) semi-automatic
(you can use `brew bump-formula-pr --url=... formula-name`).

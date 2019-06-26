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

## Output

Tap Updater outputs "batches" of formulae in which packages can be updated.
Formulae in a specific batch can be updated in any order.
However, PRs to update formulae from the next batch should not be created
until all formulae from the current batch have been updated.

As a rule of thumb: always look at **Batch 1**: you can always create PRs to
update formulae in this batch.

The process of creating PRs to update formulae is (still) semi-automatic
(you can use `brew bump-formula-pr --url=... formula-name`).

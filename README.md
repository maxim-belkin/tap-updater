# Linuxbrew/xorg updater

This is a (Python) script for the maintainers of [Linuxbrew/xorg][linuxbrew-xorg]
to figure out the order in which to update packages.

To run, simply execute the script (`./xorg-updater.py`) or use your Python3
interpreter to execute the script, for example:

```sh
python3 xorg-updater.py
```

The script outputs "batches" in which packages can be updated.
Formulae in a specific batch can be updated in any order.
However, PRs to update formulae from the next batch should not be created
until all formulae from the current batch have been updated.

The process of creating PRs to update formulae is still semi-automatic... 

[linuxbrew-xorg]: https://github.com/Linuxbrew/homebrew-xorg

# Homebrew Tap Updater

[Tap Updater](https://github.com/maxim-belkin/tap-updater) is a tool
that figures out the order in which it is safe to update packages
in a Homebrew tap.

## How to use

Tap Updater can be used to figure out the order in which to update...

### formulae in a single tap:

    ```sh
    ./tap-updater.py linuxbrew/xorg
    ```

### a formula with all of its (outdated) dependencies from the same tap:

    ```sh
    ./tap-updater.py linuxbrew/xorg/mesa
    ```

### a formula with all of its (outdated) dependencies from any tap:

    ```sh
    ./tap-updater.py -a linuxbrew/xorg/mesa
    ```

### all currently installed formulae:

    ```sh
    ./tap-updater.py $(brew list)
    ```

## Additional arguments


### `-s` | `--skip`
To exclude formulae, use `-s` or `--skip` flag followed by the formulae you'd like to skip.
Note, because `--skip` accepts arbitrary number of parameters, specify it 
AFTER the formulae and taps you'd like to process. Example:

    ```sh
    ./tap-updater.py linuxbrew/xorg --skip linuxbrew/xorg/mesa linuxbrew/xorg/libva linuxbrew/xorg/libvdpau-va-gl
    ```

### `-v` | `--verbose`

Enable verbose output. Mutually exclusive with `-q` | `--quiet`.

### `-q` | `--quiet`

Silence any output. Mutually exclusive with `-v` | `--verbose`.

### `-d` | `--debug`

Enable output of additional low-level information useful for debugging issues.

### `-h` | `--help`

Display help/usage information.

### `--no-summary`

Don't display summary table at the end of analysis.

### `--log-file`

Specify name of the log file (Default: `tap_updater.log`). Example:

    ```sh
    ./tap-updater.py --log-file xorg.log linuxbrew/xorg
    ```

## Examples

### Process (all) formulae in a tap (`linuxbrew/extra`):

    ```
    $ ./tap-updater.py linuxbrew/extra

    =====================================================================================
               Formula           | Current version | New version | Outdated dependencies 
    =====================================================================================
    linuxbrew/extra/singularity  |      2.6.0      | 3.3.0-rc.1  |                       
    linuxbrew/extra/strace       |       5.1       |     5.2     |                       
    =====================================================================================

    Batch 1: linuxbrew/extra/singularity linuxbrew/extra/strace

    Suggested commands for updating formulae in Batch 1:

    brew bump-formula-pr --no-browse --url=https://github.com/singularityware/singularity/releases/download/3.3.0-rc.1/singularity-3.3.0-rc.1.tar.gz linuxbrew/extra/singularity
    brew bump-formula-pr --no-browse --url=https://github.com/strace/strace/releases/download/v5.2/strace-5.2.tar.xz linuxbrew/extra/strace

        | Please verify that URLs exist before executing the above commands!
        | Consider adding 'version "x.y.z"' to the formula if detected 'new_version' is likely
        | to cause problems for Homebrew version detection mechanism.
    ```

### Process formulae in a tap (`linuxbrew/extra`) and _all_ of their dependencies in other taps
but skip some formulae (`linuxbrew/extra/singularity`).

    ```
    $ ./tap-updater.py linuxbrew/extra --all --skip linuxbrew/extra/singularity

    ================================================================================
            Formula         | Current version | New version | Outdated dependencies
    ================================================================================
    linuxbrew/extra/strace  |       5.1       |     5.2     |
    homebrew/core/nettle    |      3.4.1      |    3.5.1    |
    homebrew/core/sqlite    |     3.28.0      |   3.29.0    |
    ================================================================================

    Batch 1: linuxbrew/extra/strace homebrew/core/nettle homebrew/core/sqlite

    Suggested commands for updating formulae in Batch 1:

    brew bump-formula-pr --no-browse --url=https://github.com/strace/strace/releases/download/v5.2/strace-5.2.tar.xz linuxbrew/extra/strace
    brew bump-formula-pr --no-browse --url=https://ftp.gnu.org/gnu/nettle/nettle-3.5.1.tar.gz homebrew/core/nettle

        | Please verify that URLs exist before executing the above commands!
        | Consider adding 'version "x.y.z"' to the formula if detected 'new_version' is likely
        | to cause problems for Homebrew version detection mechanism.
    ```

Tap Updater outputs "batches" of formulae in which packages can be updated.
Formulae in a specific batch can be updated in any order.
However, PRs to update formulae from the next batch should not be created
until all formulae from the current batch have been updated.

**Important:** Create Pull Requests to update formulae in **_Batch 1_**.

The process of creating PRs to update formulae is (still) semi-automatic:
you can use `brew bump-formula-pr --url=... formula-name` suggested by
Tap Updater but make sure to check that suggested URLs exist.

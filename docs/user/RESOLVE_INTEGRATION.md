# DaVinci Resolve Integration

The Resolve Integration is a small launcher, not a second copy of the AI Director application.

## Architecture

The standalone AI Director desktop application owns the UI, settings, local model/runtime orchestration, updates and backend state.

The separate Resolve Workflow Integration launcher is installed into Resolve's Workflow Integration plugin location and launches/foregrounds the standalone current-user application.

The launcher deliberately does **not** ship another Electron UI/runtime, another model server, another MCP stack or another updater.

## Installation scope

The standalone application is current-user scoped.

The Resolve Integration is machine-scoped and requires elevation. The main Setup can invoke its exact embedded child installer through the Windows `runas` path, or you can run the separate:

`DaVinci Resolve AI Director Integration Setup <version>.exe`

The machine-scoped installer owns its own uninstall registration and plugin files. The core application installer is deliberately prevented from directly mutating that ownership surface.

## Assisted installer behavior

The main installer currently offers a default-checked Resolve Integration option.

- On a fresh install, unchecking it installs only the standalone application.
- Existing integration-preservation behavior is not the supported first-release upgrade procedure. Before installing a newer AI Director release, uninstall the previous Resolve Integration through its separate Windows entry, then install the new integration when wanted.
- The integration can be installed or repaired later with the separate installer artifact.

## Launch behavior

When invoked by Resolve, the launcher searches for the installed standalone AI Director application in the current user's normal application location, removes contaminating inherited Electron/Node/Resolve/Python/CUDA environment variables, marks the launch as Resolve-originated, starts the standalone application and exits.

This separation avoids embedding the full desktop runtime inside Resolve's plugin directory.

## After installing or updating the integration

If DaVinci Resolve was already open, restart Resolve so it reloads the Workflow Integration plugin.

Then use Resolve's Workflow Integration menu to launch AI Director. If nothing happens, first confirm that the standalone application is still installed for the current Windows user.

## Uninstall

The core application and Resolve Integration have separate uninstall ownership. If you want to remove both, uninstall both components through Windows installed-app controls.

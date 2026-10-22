# DaVinci Resolve Integration

Resolve Integration is a small launcher that lets DaVinci Resolve start or foreground the standalone AI Director application.

It is **not** a second copy of AI Director and does not contain another model server or updater.

## Install

The main AI Director installer can install Resolve Integration for you. A separate Integration installer is also available on the same GitHub Release.

The desktop application is installed for the current Windows user. Resolve Integration is machine-scoped and therefore requires a Windows elevation prompt.

## Use

After installation, launch AI Director from Resolve's Workflow Integration menu.

If Resolve was open while the integration was installed or updated, restart Resolve first.

If nothing happens:

1. confirm the standalone AI Director application is installed for the current Windows user;
2. restart DaVinci Resolve;
3. reinstall or repair Resolve Integration from the current release if needed.

## Upgrading

When upgrading AI Director, uninstall the existing Resolve Integration entry before installing the new release, then enable/install the integration again if you use it.

## Uninstall

Resolve Integration has its own Windows uninstall entry. Removing the desktop application does not automatically remove the machine-scoped Resolve launcher.

See [Installation](INSTALLATION.md).

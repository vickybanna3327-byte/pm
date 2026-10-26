# Scripts AGENTS.md

## Purpose

This directory contains the local runtime scripts used to start and stop the application. The scripts are intentionally lightweight so the project can be started consistently across macOS, Linux, and Windows environments.

## Current scripts

- `start.sh` for bash-based environments such as macOS and Linux
- `stop.sh` for bash-based environments such as macOS and Linux
- `start.ps1` for PowerShell-based environments on Windows
- `stop.ps1` for PowerShell-based environments on Windows
- `start.bat` for cmd-based Windows startup
- `stop.bat` for cmd-based Windows shutdown

## Intended behavior

The scripts are designed to start the FastAPI app with Uvicorn on port 8000 and stop any process that is currently listening on that port.

## Future maintenance

If the application later gains additional services or a Dockerized workflow, these scripts should be extended to start the correct container or process composition while keeping the single-host developer experience simple.

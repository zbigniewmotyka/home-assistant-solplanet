# Development Guide

This guide will help you set up the development environment for the Solplanet integration.

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) for VS Code

## Getting Started

### 1. Open the Project in Dev Container

1. Open the project folder in Visual Studio Code
2. When prompted, click "Reopen in Container" (or press `F1` and select "Dev Containers: Reopen in Container")
3. Wait for the container to build and start (this may take a few minutes on first run)

### 2. Start Home Assistant

Once the dev container is running:

1. Open the Command Palette (`F1` or `Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Type "Tasks: Run Task"
3. Select **"Start Home Assistant"**

Alternatively, you can use the keyboard shortcut `Ctrl+Shift+B` / `Cmd+Shift+B` to run the default build task.

### 3. Access Home Assistant

Once Home Assistant starts, it will be available at:

**http://localhost:7123**

The initial startup may take a minute or two. You can monitor the startup progress in the VS Code terminal.

## Development Workflow

- The integration code is located in the `custom_components/solplanet/` directory
- Any changes you make to the code will be reflected in the running Home Assistant instance
- You may need to restart Home Assistant to see some changes take effect
- Use the VS Code terminal to run commands inside the dev container

## Troubleshooting

- If Home Assistant fails to start, check the terminal output for error messages
- To restart Home Assistant, stop the current task and run "Start Home Assistant" again
- If you encounter issues with the dev container, try rebuilding it: `F1` → "Dev Containers: Rebuild Container"


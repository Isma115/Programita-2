# Programita 2

A modular, visually attractive Tkinter application with a modern dark theme and tabbed interface.

## Project Structure

The project follows a modular architecture separating UI and Logic:

- **`main.py`**: Entry point of the application.
- **`src/app.py`**: Main application assembly.
- **`src/logic/controller.py`**: Handles application logic and navigation.
- **`src/ui/`**: User Interface components.
  - **`styles.py`**: Centralized configuration for the modern dark theme.
  - **`layout.py`**: Main window structure with custom navigation.
  - **`tabs/`**: Individual tab views ("Code" and "Documentation").

## How to Run

1. Ensure you have Python installed.
2. Run the application from the root directory:

```bash
python main.py
```

## Build macOS App (`.app`)

From the project root:

```bash
./scripts/build_macos_app.sh
```

Output:

- `dist/Programita 2.app`
- `dist/Programita 2-macOS.zip`

### macOS global hotkeys

`Shift + Left Click` and `Cmd/Ctrl + V` global listeners require:

- PyObjC runtime modules (`Quartz`, `HIServices`, `ApplicationServices`) available at build time.
- macOS permissions granted to the built app in:
  - `System Settings -> Privacy & Security -> Accessibility`
  - `System Settings -> Privacy & Security -> Input Monitoring`

## Features

- **Modern Dark Interface**: Custom styled `ttk` widgets.
- **Modular Design**: Easy to extend with new tabs or logic.
- **Navigation**: Switch between "Code" and "Documentation" views.
- **AI Selector Configurable**: The available IAs are loaded from `ias_disponibles.txt` using the format `Nombre | URL`.
# Programita-2
# Programita-2

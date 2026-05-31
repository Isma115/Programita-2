# Programita 2

Aplicación de escritorio en `Tkinter` para trabajar con código y documentación: cargar proyectos, agrupar ficheros por secciones/regiones, generar prompts y mantener documentación técnica.

## Qué hace

- Vista **Código** para preparar prompts con contexto real del proyecto.
- Vista **Documentación** para editar Markdown, previsualizar y gestionar estructura documental.
- Búsqueda rápida tipo paleta (`Ctrl/Cmd + F`).
- Flujos de pegado inteligente y hotkeys globales (configurables por `config.json`).
- Gestión de secciones (`sections/`) y segmentos (`segments/`) en JSON.

## Requisitos

- Python 3.10+ recomendado.
- Dependencias de `requirements.txt`.
- En macOS, para hotkeys globales: permisos de Accesibilidad y Monitorización de entrada.

## Instalación

Desde la raíz del proyecto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Ejecutar

```bash
python main.py
```

## Uso rápido (paso a paso)

### 1) Cargar proyecto de código

1. Abre la pestaña **Código**.
2. Usa el botón `+` para añadir un proyecto.
3. Cambia entre proyectos con los botones de proyecto anterior/siguiente.
4. Filtra por ruta y por extensiones para acotar el contexto.

### 2) Generar prompt para IA

1. Selecciona sección/subsección/región en el panel derecho.
2. Escribe tu petición en **Mensaje para IA**.
3. Pulsa el botón **Enviar** o usa `Ctrl/Cmd + Enter`.

### 3) Trabajar documentación

1. Abre la pestaña **Documentación**.
2. Pulsa **Abrir** para elegir carpeta docs.
3. Edita en modo texto o vista previa.
4. Guarda con **Guardar** o `Ctrl/Cmd + S`.

## Atajos de teclado (completos)

> Nota: en macOS usa `Cmd` donde en Windows/Linux se usa `Ctrl`.

### Globales de la app

- `Ctrl/Cmd + F`: abre el buscador global (Search Overlay).

### Hotkeys globales (sistema)

- `Shift + Click izquierdo` (global): lanza el pegado inteligente.
- `Ctrl/Cmd + C` y después `Ç` (en una ventana corta de tiempo): regiona el portapapeles y pega automáticamente.
- `Ctrl/Cmd + V` (solo durante pegado dinámico activo): avanza al siguiente fichero del flujo.

Notas:
- El atajo con `Ç` depende de distribución de teclado que tenga esa tecla.
- De forma avanzada, el flujo `C + Ç` también acepta `Alt/Option` y `Fn` como modificador.
- En macOS estos hotkeys requieren permisos del sistema (Accesibilidad + Monitorización de entrada).

### Search Overlay (buscador global)

- `Enter`: ejecuta el activo/comando seleccionado.
- `↑` / `↓`: mover selección.
- `Esc`: no cierra el overlay (queda consumido).  
  Para cerrarlo: clic fuera o perder foco.

### Pestaña Código

- En **Mensaje para IA**:
  - `Ctrl/Cmd + Enter`: copiar/generar prompt (misma acción que botón Enviar).

### Pestaña Documentación

- En editor Markdown:
  - `Ctrl/Cmd + S`: guardar documento.
  - `Ctrl/Cmd + Z`: deshacer.
  - `Ctrl/Cmd + Y`: rehacer.
- En panel de código (derecha):
  - `Ctrl/Cmd + S`: guardar fichero.
  - `Ctrl/Cmd + Z`: deshacer.
  - `Ctrl/Cmd + Y`: rehacer.
- En árbol de secciones:
  - `Backspace`: eliminar sección/documento seleccionado (con confirmación).

Zoom (editor y vista previa):
- `Ctrl/Cmd + +` o `Ctrl/Cmd + =`: aumentar zoom.
- `Ctrl/Cmd + -`: reducir zoom.
- `Ctrl/Cmd + 0`: resetear zoom.
- También funcionan variantes de teclado numérico (`KP_Add`, `KP_Subtract`, `KP_0`).

### Ventana "Prompt" (Documentación)

- `Ctrl/Cmd + ←`: prompt anterior.
- `Ctrl/Cmd + →`: prompt siguiente.
- `Esc`: cerrar ventana.

### Editor de bloque Markdown (popup de edición)

- `Tab`: indentar.
- `Shift + Tab` (o `ISO_Left_Tab`): desindentar.
- `Ctrl/Cmd + Enter`: guardar cambios.
- `Esc`: cerrar.

### Popup de edición Arbitrary (smart paste)

- `Ctrl/Cmd + F`: mostrar búsqueda interna.
- `Ctrl/Cmd + Z`: deshacer.
- `Ctrl/Cmd + Y`: rehacer.
- `Cmd + Shift + Z` (macOS): rehacer.
- `Ctrl/Cmd + V`: pegado personalizado conservando indentación.
- `Tab`: indentar.
- `Shift + Tab`: desindentar.

En barra de búsqueda interna:
- `Enter`: siguiente coincidencia.
- `Shift + Enter`: coincidencia anterior.
- `Esc`: ocultar barra de búsqueda.

### Otros popups

- Popup "Volver a memoria":
  - `Enter`: restaurar selección.
  - `Esc`: cerrar.
- Popups de creación de región/segmento/smart region:
  - `Esc`: cerrar.
- Editor de diagramas HTML:
  - `Delete` o `Backspace`: eliminar elemento seleccionado (si no estás escribiendo en un campo de texto).

## Configuración

- Archivo de configuración: `config.json`.
- Puedes ajustar, entre otros:
  - proyecto y docs recientes,
  - modo de salida (`return_files`, `return_chunks`, `return_regions`),
  - autoguardado docs,
  - filtros y límites,
  - `enable_hotkeys` para activar/desactivar hotkeys globales.

## Estructura del proyecto

- `main.py`: entrada principal.
- `src/app.py`: ensamblado de UI y lógica.
- `src/logic/`: controlador, configuración, hotkeys y lógica de negocio.
- `src/ui/`: layout, estilos, pestañas y popups.
- `sections/`: secciones de código en JSON.
- `segments/`: segmentos de código en JSON.
- `scripts/build_macos_app.sh`: build para `.app` en macOS.

## Build macOS (`.app`)

```bash
chmod +x scripts/build_macos_app.sh
./scripts/build_macos_app.sh
```

Salida:

- `dist/Programita 2.app`
- `dist/Programita 2-macOS.zip`

## Solución rápida de problemas

- Si no funcionan hotkeys globales en macOS: revisa permisos de Accesibilidad y Monitorización de entrada, luego reinicia la app.
- Si no carga secciones/segmentos: comprueba rutas en `config.json`.
- Si una combinación no responde: prueba la variante `Cmd` (macOS) o `Ctrl` (Windows/Linux) y verifica foco del widget correcto.

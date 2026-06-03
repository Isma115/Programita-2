# Agent Instructions: Division by Component Regions

## Goal

When you divide code into regions, treat each region as a real component-level block, not as a random fragment.

The objective is to make the code easier to navigate, review, and replace later.

## Core Rule

Each region must describe one concrete component or one clearly bounded UI/domain block.

Use names such as:

- `Tabla de usuarios`
- `Formulario de login`
- `Seccion lateral izquierda`
- `Modal de confirmacion`
- `Cabecera del panel`
- `Panel de filtros`
- `Vista de detalle`

Avoid generic names such as:

- `Componente`
- `Bloque`
- `Parte 1`
- `Seccion A`
- `Utils`

If the block is not a real component or a meaningful UI/domain unit, do not create a region for it.

## Region Name Format

Use this structure:

`#region Nombre del componente | Tipo | Descripcion`

Where:

- `Nombre del componente` is the concrete component name.
- `Tipo` is one of `Vista`, `Funcionalidad`, `Backend`, `Estilo`, `Modal`, `Formulario`, `Tabla`, `Sidebar`, `Panel`, or another precise label.
- `Descripcion` explains what the region does in one short phrase.

Example:

`#region Tabla de usuarios | Vista | listado y acciones sobre usuarios`

## Syntax Rules

Always use the comment syntax native to the file language.

Examples:

- JavaScript / TypeScript / C++ / Java:
  - `// #region ...`
  - `// #endregion`
- Python / Shell:
  - `# #region ...`
  - `# #endregion`
- SQL / Lua:
  - `-- #region ...`
  - `-- #endregion`
- CSS / C-style block comments:
  - `/* #region ... */`
  - `/* #endregion */`
- HTML / XML:
  - `<!-- #region ... -->`
  - `<!-- #endregion -->`
- JSX / TSX or embedded template expressions:
  - use the same language comment style, but keep it valid inside the host syntax
  - if the file is inside braces or another wrapper, preserve that wrapper without breaking syntax

Do not invent a marker that the language cannot parse.

## Placement Rules

- Use one region per meaningful component or block.
- Do not nest regions inside other regions.
- Keep region boundaries aligned with complete logical units.
- Do not split a single component into tiny technical pieces unless the file is genuinely composed of separate component-level blocks.
- Prefer the outermost meaningful block that still has a clear business or UI purpose.

## What Counts As a Region

Good candidates:

- modal windows
- tables
- forms
- sidebars
- headers
- footers
- panels
- filters
- detail views
- step flows
- backend handlers with a clear responsibility
- feature-specific service blocks

Bad candidates:

- individual inputs
- single buttons
- one-off constants
- tiny helper functions
- trivial getters/setters
- isolated style declarations with no component meaning

## Naming Guidance

Name regions after the real component or feature they represent.

Prefer:

- `Formulario de login`
- `Tabla de usuarios`
- `Seccion lateral izquierda`
- `Cabecera de declaracion de cultivo`
- `Modal de confirmacion de borrado`

Avoid:

- `Helpers`
- `Misc`
- `Block 1`
- `Section A`

If a component has a well-known role, describe that role first.

## Working Method

1. Inspect the file and identify the meaningful component boundaries.
2. Detect the comment syntax used by the file.
3. Create only non-nested regions.
4. Write a precise component name as the first field of the region header.
5. Add a short type and description.
6. Preserve valid syntax and indentation.
7. If a region cannot be expressed cleanly, skip it rather than forcing it.

## Output Expectations

When you produce regioned code:

- return only the final code
- keep the original behavior unchanged
- preserve formatting as much as possible
- preserve existing comments unless they conflict with the region markers

## Minimal Example

```tsx
{// #region Formulario de login | Formulario | captura de credenciales y acceso}
// ...codigo del formulario...
{// #endregion}
```

```python
# #region Tabla de usuarios | Vista | listado y gestion de usuarios
# ...codigo de la tabla...
# #endregion
```

## Final Check

Before finishing, verify:

- each region has a concrete component name
- the syntax matches the file language
- regions are not nested
- region names are descriptive and specific
- the block covers a meaningful unit of code

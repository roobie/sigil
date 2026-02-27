# Sigil for VS Code

Display and manage [sigil](../../) code bookmarks directly in VS Code.

## Features

- **Gutter indicators** — yellow circles on bookmarked lines, red for stale
- **Hover tooltips** — description and tags on mouseover
- **Sidebar panel** — browse all bookmarks, click to jump
- **Quick pick** — fuzzy search across all bookmarks (`Ctrl+Shift+S G`)
- **Navigation** — jump between bookmarks in the current file
- **File watcher** — auto-refreshes when bookmarks change externally (CLI usage)

## Prerequisites

The `sg` CLI must be on your PATH. See the [main README](../../) for installation.

## Keybindings

| Key | Command |
|-----|---------|
| `Ctrl+Shift+S A` | Add bookmark at cursor |
| `Ctrl+Shift+S D` | Delete bookmark at cursor |
| `Ctrl+Shift+S N` | Next bookmark in file |
| `Ctrl+Shift+S P` | Previous bookmark in file |
| `Ctrl+Shift+S G` | Go to bookmark (fuzzy search) |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `sigil.command` | `sg` | Path to the sigil CLI |

## Development

```bash
cd editors/vscode
npm install
npm run compile
# Then press F5 in VS Code to launch the extension host
```

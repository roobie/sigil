import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { execFile } from "child_process";

// ── Types ──

interface Bookmark {
  id: string;
  file: string;
  line: number;
  tags: string[];
  desc: string;
  status: string;
  created: string;
  accessed: string;
  checked: string;
}

// ── State ──

let bookmarks: Bookmark[] = [];
let gutterValid: vscode.TextEditorDecorationType;
let gutterStale: vscode.TextEditorDecorationType;
let watcher: vscode.FileSystemWatcher | undefined;
let treeProvider: BookmarkTreeProvider;

// ── Activation ──

export function activate(ctx: vscode.ExtensionContext) {
  // Gutter decoration types
  gutterValid = vscode.window.createTextEditorDecorationType({
    gutterIconPath: makeGutterIcon(ctx, "valid"),
    gutterIconSize: "80%",
  });
  gutterStale = vscode.window.createTextEditorDecorationType({
    gutterIconPath: makeGutterIcon(ctx, "stale"),
    gutterIconSize: "80%",
  });

  // Sidebar tree view
  treeProvider = new BookmarkTreeProvider();
  vscode.window.registerTreeDataProvider("sigilBookmarks", treeProvider);

  // Commands
  ctx.subscriptions.push(
    vscode.commands.registerCommand("sigil.addBookmark", cmdAdd),
    vscode.commands.registerCommand("sigil.deleteBookmark", cmdDelete),
    vscode.commands.registerCommand("sigil.nextBookmark", () => cmdNav("next")),
    vscode.commands.registerCommand("sigil.prevBookmark", () => cmdNav("prev")),
    vscode.commands.registerCommand("sigil.validate", cmdValidate),
    vscode.commands.registerCommand("sigil.refresh", refresh),
    vscode.commands.registerCommand("sigil.gotoBookmark", cmdGoto),
    vscode.commands.registerCommand("sigil.openBookmark", cmdOpenBookmark)
  );

  // Watch .sigil/bookmarks.jsonl for external changes
  const pattern = new vscode.RelativePattern(
    vscode.workspace.workspaceFolders?.[0] ?? "",
    ".sigil/bookmarks.jsonl"
  );
  watcher = vscode.workspace.createFileSystemWatcher(pattern);
  watcher.onDidChange(() => refresh());
  watcher.onDidCreate(() => refresh());
  watcher.onDidDelete(() => refresh());
  ctx.subscriptions.push(watcher);

  // Refresh on editor switch
  ctx.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => decorateActive())
  );

  // Refresh on save
  ctx.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(() => refresh())
  );

  // Initial load
  refresh();
}

export function deactivate() {
  gutterValid?.dispose();
  gutterStale?.dispose();
  watcher?.dispose();
}

// ── Loading bookmarks ──

function sigilRoot(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) return undefined;
  const root = folders[0].uri.fsPath;
  if (fs.existsSync(path.join(root, ".sigil", "bookmarks.jsonl"))) {
    return root;
  }
  return undefined;
}

function loadBookmarks(): Bookmark[] {
  const root = sigilRoot();
  if (!root) return [];

  const jsonlPath = path.join(root, ".sigil", "bookmarks.jsonl");
  if (!fs.existsSync(jsonlPath)) return [];

  try {
    const content = fs.readFileSync(jsonlPath, "utf-8");
    return content
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as Bookmark);
  } catch {
    return [];
  }
}

function refresh() {
  bookmarks = loadBookmarks();
  decorateActive();
  treeProvider.refresh();
}

// ── Gutter decorations ──

function decorateActive() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  const root = sigilRoot();
  if (!root) return;

  const filePath = vscode.workspace.asRelativePath(editor.document.uri, false);

  const fileBookmarks = bookmarks.filter((bm) => bm.file === filePath);

  const validRanges: vscode.DecorationOptions[] = [];
  const staleRanges: vscode.DecorationOptions[] = [];

  for (const bm of fileBookmarks) {
    const lineIdx = bm.line - 1;
    if (lineIdx < 0 || lineIdx >= editor.document.lineCount) continue;

    const range = new vscode.Range(lineIdx, 0, lineIdx, 0);
    const tags = bm.tags?.length ? `[${bm.tags.join(", ")}]` : "";
    const hoverMessage = new vscode.MarkdownString(
      `**Sigil** ${tags}\n\n${bm.desc || "(no description)"}` +
        `\n\n*Status: ${bm.status}*`
    );

    const option: vscode.DecorationOptions = { range, hoverMessage };

    if (bm.status === "stale" || bm.status === "missing_file") {
      staleRanges.push(option);
    } else {
      validRanges.push(option);
    }
  }

  editor.setDecorations(gutterValid, validRanges);
  editor.setDecorations(gutterStale, staleRanges);
}

// ── Gutter icon SVGs ──

function makeGutterIcon(
  ctx: vscode.ExtensionContext,
  kind: "valid" | "stale"
): vscode.Uri {
  const color = kind === "valid" ? "%23e5c07b" : "%23e06c75";
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">` +
    `<circle cx="8" cy="8" r="5" fill="${color}"/>` +
    `</svg>`;

  const iconDir = path.join(ctx.extensionPath, "icons");
  if (!fs.existsSync(iconDir)) {
    fs.mkdirSync(iconDir, { recursive: true });
  }
  const iconPath = path.join(iconDir, `${kind}.svg`);
  fs.writeFileSync(iconPath, svg);
  return vscode.Uri.file(iconPath);
}

// ── CLI invocation ──

function sgCommand(): string {
  return vscode.workspace.getConfiguration("sigil").get("command", "sg");
}

function runSg(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = sigilRoot();
    if (!root) return reject(new Error("Not in a sigil project"));

    execFile(sgCommand(), args, { cwd: root }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(stderr || err.message));
      } else {
        resolve(stdout);
      }
    });
  });
}

// ── Commands ──

async function cmdAdd() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  const filePath = vscode.workspace.asRelativePath(editor.document.uri, false);
  const line = editor.selection.active.line + 1;
  const location = `${filePath}:${line}`;

  const tags = await vscode.window.showInputBox({
    prompt: "Tags (comma-separated, or leave empty)",
    placeHolder: "bug, todo, important",
  });
  if (tags === undefined) return; // cancelled

  const desc = await vscode.window.showInputBox({
    prompt: "Description",
    placeHolder: "Why is this location important?",
  });
  if (desc === undefined) return;

  const args = ["add", location];
  if (tags) args.push("-t", tags);
  if (desc) args.push("-d", desc);

  try {
    const output = await runSg(args);
    vscode.window.showInformationMessage(output.trim().split("\n")[0]);
    refresh();
  } catch (e: any) {
    vscode.window.showErrorMessage(`Sigil: ${e.message}`);
  }
}

async function cmdDelete() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  const filePath = vscode.workspace.asRelativePath(editor.document.uri, false);
  const curLine = editor.selection.active.line + 1;

  const bm = bookmarks.find(
    (b) => b.file === filePath && b.line === curLine
  );
  if (!bm) {
    vscode.window.showInformationMessage("Sigil: no bookmark on this line");
    return;
  }

  const confirm = await vscode.window.showWarningMessage(
    `Delete bookmark "${bm.desc || bm.id}"?`,
    "Delete",
    "Cancel"
  );
  if (confirm !== "Delete") return;

  try {
    await runSg(["delete", bm.id]);
    refresh();
  } catch (e: any) {
    vscode.window.showErrorMessage(`Sigil: ${e.message}`);
  }
}

function cmdNav(direction: "next" | "prev") {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  const filePath = vscode.workspace.asRelativePath(editor.document.uri, false);
  const curLine = editor.selection.active.line + 1;

  const lines = bookmarks
    .filter((b) => b.file === filePath)
    .map((b) => b.line)
    .sort((a, b) => a - b);

  let target: number | undefined;
  if (direction === "next") {
    target = lines.find((l) => l > curLine);
  } else {
    target = [...lines].reverse().find((l) => l < curLine);
  }

  if (target !== undefined) {
    const pos = new vscode.Position(target - 1, 0);
    editor.selection = new vscode.Selection(pos, pos);
    editor.revealRange(new vscode.Range(pos, pos));

    const bm = bookmarks.find(
      (b) => b.file === filePath && b.line === target
    );
    if (bm) {
      const tags = bm.tags?.length ? `[${bm.tags.join(",")}] ` : "";
      vscode.window.setStatusBarMessage(`Sigil: ${tags}${bm.desc}`, 3000);
    }
  } else {
    vscode.window.showInformationMessage(
      `Sigil: no more bookmarks ${direction === "next" ? "below" : "above"}`
    );
  }
}

async function cmdValidate() {
  try {
    const output = await runSg(["validate", "--fix"]);
    vscode.window.showInformationMessage(
      output.trim().split("\n").slice(0, 3).join(" · ")
    );
    refresh();
  } catch (e: any) {
    vscode.window.showErrorMessage(`Sigil: ${e.message}`);
  }
}

async function cmdGoto() {
  if (!bookmarks.length) {
    vscode.window.showInformationMessage("Sigil: no bookmarks in project");
    return;
  }

  const items = bookmarks.map((bm) => {
    const tags = bm.tags?.length ? `[${bm.tags.join(",")}] ` : "";
    return {
      label: `${tags}${bm.desc || "(no description)"}`,
      description: `${bm.file}:${bm.line}`,
      detail: bm.status !== "valid" ? `⚠ ${bm.status}` : undefined,
      bookmark: bm,
    };
  });

  const picked = await vscode.window.showQuickPick(items, {
    placeHolder: "Search bookmarks…",
    matchOnDescription: true,
  });

  if (picked) {
    openBookmark(picked.bookmark);
  }
}

function cmdOpenBookmark(bm: Bookmark) {
  openBookmark(bm);
}

async function openBookmark(bm: Bookmark) {
  const root = sigilRoot();
  if (!root) return;

  const uri = vscode.Uri.file(path.join(root, bm.file));
  const doc = await vscode.workspace.openTextDocument(uri);
  const editor = await vscode.window.showTextDocument(doc);

  const pos = new vscode.Position(bm.line - 1, 0);
  editor.selection = new vscode.Selection(pos, pos);
  editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
}

// ── Sidebar tree view ──

class BookmarkTreeProvider
  implements vscode.TreeDataProvider<BookmarkTreeItem>
{
  private _onDidChangeTreeData = new vscode.EventEmitter<
    BookmarkTreeItem | undefined
  >();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  refresh() {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: BookmarkTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: BookmarkTreeItem): BookmarkTreeItem[] {
    if (element) return []; // flat list, no children

    // Group by file
    const byFile = new Map<string, Bookmark[]>();
    for (const bm of bookmarks) {
      const list = byFile.get(bm.file) || [];
      list.push(bm);
      byFile.set(bm.file, list);
    }

    const items: BookmarkTreeItem[] = [];
    for (const [file, bms] of byFile) {
      for (const bm of bms.sort((a, b) => a.line - b.line)) {
        items.push(new BookmarkTreeItem(bm));
      }
    }
    return items;
  }
}

class BookmarkTreeItem extends vscode.TreeItem {
  constructor(public readonly bookmark: Bookmark) {
    const tags = bookmark.tags?.length ? `[${bookmark.tags.join(",")}] ` : "";
    super(`${tags}${bookmark.desc || "(no description)"}`);

    this.description = `${bookmark.file}:${bookmark.line}`;
    this.tooltip = new vscode.MarkdownString(
      `**${bookmark.file}:${bookmark.line}**\n\n` +
        `${bookmark.desc || ""}\n\n` +
        `Tags: ${bookmark.tags?.join(", ") || "none"}\n\n` +
        `Status: ${bookmark.status}`
    );

    this.iconPath = new vscode.ThemeIcon(
      bookmark.status === "stale" || bookmark.status === "missing_file"
        ? "warning"
        : "bookmark",
      bookmark.status === "stale" || bookmark.status === "missing_file"
        ? new vscode.ThemeColor("editorWarning.foreground")
        : new vscode.ThemeColor("editorInfo.foreground")
    );

    this.command = {
      command: "sigil.openBookmark",
      title: "Open",
      arguments: [bookmark],
    };
  }
}

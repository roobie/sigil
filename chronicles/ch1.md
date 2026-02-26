# Chronicle: From Vision to MVP

## The Initial Vision

We began with a clear need: **a standalone CLI tool to bookmark code locations (file:line) with metadata and querying capabilities**, stored in a VCS-friendly format. The goal was to navigate large codebases more effectively than grep or IDE search alone.

## The Expanded Ambition

Early in our discussion, we recognized that a simple line-based bookmark system would be fragile. The real power would come from:

- **Semantic understanding** - Bookmarks that understand code structure, not just line numbers
- **Editor integration** - Native UX in developers' primary tools
- **Change tracking** - Automatic updates when code moves, warnings when it changes significantly

This vision was compelling: a tool that truly understands your codebase and maintains stable reference points even as code evolves.

## The Reality Check

As we explored the conceptual challenges, a pattern emerged: **nearly every "nice to have" feature introduced fundamental complexity**:

**Semantic anchoring** requires solving the philosophical problem of code identity across modifications—a problem with no single right answer, only heuristics that work sometimes.

**Multi-language support** means dealing with dozens of different LSP implementations, language semantics, and edge cases. Each language is effectively a separate project.

**Concurrent modifications** surface classic distributed systems problems. Bookmarks are local state referencing shared state, creating synchronization challenges that Git's model doesn't naturally handle.

**Refactoring detection** would require either deep IDE integration (fragile, editor-specific) or sophisticated program analysis (research-level difficulty).

**Staleness detection** is subjective—what makes a bookmark "stale" depends on why it was created, information the tool doesn't have.

## The Turning Point

The critical insight was recognizing the **adoption challenge**. Even if we solved all the technical problems, developers would only adopt the tool if:

1. It works reliably (no false positives, no performance issues)
2. It integrates seamlessly into existing workflows
3. It provides immediate value without extensive setup
4. It's 10x better than alternatives for its specific use case

Complex features increase the surface area for bugs and performance problems. They require more documentation, more configuration, more mental overhead. Each feature is a barrier to adoption.

## The Decision

We chose to **optimize for usefulness and reliability over sophistication**. The reasoning:

**A simple tool that works perfectly beats a sophisticated tool that works inconsistently.** Developers will tolerate limitations if the tool is reliable and fast. They won't tolerate a tool that gives false warnings or breaks their workflow.

**Real usage reveals real priorities.** We can theorize about which features matter, but actual users will tell us through their pain points. Build the minimum, learn from usage, then expand.

**Incremental complexity is manageable.** Starting simple allows us to add features one at a time, validating each addition before moving forward. Starting complex means debugging interactions between half-finished features.

**VCS-friendly storage enables experimentation.** With plain-text bookmarks, users can manually edit, script against, and understand the data. This creates a path for power users to extend the tool before we build official features.

## The Path Forward

The MVP acknowledges reality:
- Bookmarks will break when code changes significantly (accept this)
- Manual recovery is acceptable initially (provide good tools for it)
- Single-editor support is sufficient (expand later based on demand)
- Line-based bookmarks are simple and understandable (add semantics incrementally)

This approach lets us ship something useful in weeks, not months, and learn what actually matters.

---

# Technical Design Spec: Codebase Bookmark MVP

## Overview

**Name**: `sigil` (or similar)

**Purpose**: A standalone CLI tool for bookmarking code locations with metadata, stored in a VCS-friendly format, with optional editor integration.

**Design Philosophy**: Simple, fast, reliable. Optimize for the common case (bookmarks remain valid) while providing good recovery tools for the uncommon case (bookmarks become stale).

---

## Core Requirements

### Functional Requirements

1. **Create bookmarks** with file path, line number, tags, and description
2. **List bookmarks** with filtering by tags, file, or text search
3. **Navigate to bookmarks** by opening the file in an editor
4. **Delete bookmarks** individually or in bulk
5. **Validate bookmarks** by checking if context lines still match
6. **Update bookmarks** when line numbers change but context matches
7. **Export/import** bookmarks for sharing or backup

### Non-Functional Requirements

1. **VCS-friendly storage** - Plain text format (JSON or YAML)
2. **Fast operations** - All commands complete in <100ms for typical usage
3. **Editor agnostic** - CLI works independently; editor integration is optional
4. **Cross-platform** - Works on Linux, macOS, Windows
5. **Zero configuration** - Works out of the box with sensible defaults

---

## Data Model

### Bookmark Structure

```json
{
  "id": "bm_1709123456_a3f5",
  "file": "src/parser.rs",
  "line": 156,
  "context": {
    "before": "fn parse_expression(input: &str) -> Result<Expr> {",
    "target": "    let tokens = tokenize(input)?;",
    "after": "    build_ast(tokens)"
  },
  "metadata": {
    "tags": ["parser", "bug"],
    "description": "Edge case with nested expressions",
    "created": "2026-02-15T10:30:00Z",
    "accessed": "2026-02-20T14:22:00Z"
  },
  "validation": {
    "status": "valid",
    "last_checked": "2026-02-26T09:15:00Z"
  }
}
```

### Storage Format

**File location**: `.sigil/bookmarks.json` in repository root (or `~/.sigil/global.json` for global bookmarks)

**Structure**:
```json
{
  "version": "1.0",
  "repository": {
    "root": "/home/user/projects/myapp",
    "remote": "https://github.com/user/myapp.git"
  },
  "bookmarks": [
    { /* bookmark object */ }
  ]
}
```

**Design decisions**:
- **JSON over YAML** - Easier to parse, better tooling support, still human-readable
- **Context lines** - Store 1 line before, target line, 1 line after for validation
- **Relative file paths** - Portable across machines and checkouts
- **Timestamp tracking** - Enables "recently used" sorting and staleness heuristics
- **Status field** - Tracks validation state without re-checking on every operation

---

## CLI Interface

### Commands

```bash
# Create a bookmark
sigil add <file>:<line> [--tags tag1,tag2] [--desc "description"]
sigil add src/main.rs:42 --tags bug,urgent --desc "Memory leak here"

# List bookmarks
sigil list [--tags tag1,tag2] [--file pattern] [--stale]
sigil list --tags bug
sigil list --file "src/parser.*"
sigil list --stale  # Show only potentially stale bookmarks

# Show bookmark details
sigil show <id>
sigil show bm_1709123456_a3f5

# Navigate to bookmark (opens in $EDITOR or configured editor)
sigil goto <id>
sigil goto bm_1709123456_a3f5

# Update bookmark (change tags, description, or line number)
sigil update <id> [--line N] [--tags tag1,tag2] [--desc "new description"]

# Delete bookmark
sigil delete <id>
sigil delete --tags old  # Delete all bookmarks with tag "old"

# Validate all bookmarks
sigil validate [--fix]  # --fix attempts to auto-update line numbers

# Search bookmark descriptions and tags
sigil search "memory leak"

# Export/import
sigil export bookmarks.json
sigil import bookmarks.json

# Interactive mode (fuzzy finder for navigation)
sigil interactive  # or just: sigil
```

### Output Format

**List output** (table format):
```
ID       FILE              LINE  TAGS           DESCRIPTION                    STATUS
bm_a3f5  src/parser.rs     156   parser,bug     Edge case with nested exprs    valid
bm_b7c2  lib/utils.py      89    refactor       Legacy code needs cleanup      stale
bm_d4e1  main.rs           12    entry          Main entry point               valid
```

**Show output** (detailed):
```
Bookmark: bm_a3f5
File: src/parser.rs:156
Tags: parser, bug
Description: Edge case with nested expressions
Created: 2026-02-15 10:30:00
Last accessed: 2026-02-20 14:22:00
Status: valid (checked 2026-02-26 09:15:00)

Context:
  155 | fn parse_expression(input: &str) -> Result<Expr> {
→ 156 |     let tokens = tokenize(input)?;
  157 |     build_ast(tokens)
```

---

## Validation Algorithm

### Context Matching

When validating a bookmark:

1. **Exact match**: Check if target line at stored line number matches context
   - If yes: Mark as `valid`, update `last_checked`
   - If no: Proceed to fuzzy search

2. **Nearby search**: Search ±10 lines for exact context match
   - If found: Update line number, mark as `valid`, log the change
   - If not found: Proceed to file-wide search

3. **File-wide search**: Search entire file for context match
   - If found: Update line number, mark as `moved`, prompt user
   - If not found: Mark as `stale`

4. **Stale handling**: When marked `stale`:
   - Store original context for reference
   - Don't auto-delete (user might want to review)
   - Show in `sigil list --stale`

### Auto-fix Mode

With `sigil validate --fix`:
- Automatically update line numbers for `valid` and `moved` bookmarks
- Leave `stale` bookmarks unchanged (require manual review)
- Print summary of changes

---

## Editor Integration (Phase 1: VS Code)

### Architecture

**Separation of concerns**:
- CLI tool handles all data management and validation
- Editor extension provides UI and keybindings
- Communication via CLI invocation (no daemon, no RPC initially)

### VS Code Extension Features

**Core functionality**:
- **Gutter icons**: Show bookmark indicators in editor gutter
- **Hover tooltips**: Display bookmark description on hover
- **Command palette**: Access all sigil commands
- **Sidebar panel**: List all bookmarks with filtering
- **Keybindings**: Quick bookmark creation and navigation

**Commands**:
- `Codemark: Add Bookmark Here` - Bookmark current line
- `Codemark: List Bookmarks` - Show sidebar panel
- `Codemark: Go to Bookmark` - Fuzzy search and jump
- `Codemark: Validate All` - Check bookmark status

**Implementation approach**:
- Extension reads `.sigil/bookmarks.json` on activation
- Watches file for external changes (CLI usage)
- Invokes `sigil` CLI for all operations
- Decorates editor based on bookmark data

---

## Technology Stack

### CLI Tool

**Language**: Rust
- Fast compilation to single binary
- Excellent CLI libraries (`clap`, `serde`)
- Strong type safety reduces bugs
- Cross-platform support

**Key dependencies**:
- `clap` - CLI argument parsing
- `serde` + `serde_json` - JSON serialization
- `fuzzy-matcher` - Fuzzy search for bookmarks
- `chrono` - Timestamp handling
- `git2` - Optional Git integration for repository detection

### VS Code Extension

**Language**: TypeScript
- Standard for VS Code extensions
- Good type safety
- Access to full VS Code API

**Key dependencies**:
- `@types/vscode` - VS Code API types
- Built-in file system watchers
- Built-in terminal integration for CLI invocation

---

## File Structure

```
sigil/
├── cli/
│   ├── src/
│   │   ├── main.rs           # CLI entry point
│   │   ├── commands/         # Command implementations
│   │   │   ├── add.rs
│   │   │   ├── list.rs
│   │   │   ├── goto.rs
│   │   │   ├── validate.rs
│   │   │   └── ...
│   │   ├── models/           # Data structures
│   │   │   ├── bookmark.rs
│   │   │   ├── storage.rs
│   │   │   └── validation.rs
│   │   └── utils/            # Helpers
│   │       ├── context.rs    # Context line extraction
│   │       ├── search.rs     # Fuzzy search
│   │       └── git.rs        # Git operations
│   ├── Cargo.toml
│   └── tests/
│
├── editors/
│   └── vscode/
│       ├── src/
│       │   ├── extension.ts  # Extension entry point
│       │   ├── commands.ts   # Command handlers
│       │   ├── decorations.ts # Gutter icons
│       │   └── provider.ts   # Bookmark provider
│       ├── package.json
│       └── tsconfig.json
│
└── docs/
    ├── README.md
    ├── CLI_REFERENCE.md
    └── EDITOR_INTEGRATION.md
```

---

## Implementation Phases

### Phase 1: Core CLI (Week 1-2)
- [ ] Data model and JSON storage
- [ ] Commands: add, list, show, delete
- [ ] Basic context extraction
- [ ] Simple validation (exact line match only)
- [ ] Repository detection (find `.sigil/` directory)

### Phase 2: Enhanced Validation (Week 2-3)
- [ ] Fuzzy context matching (nearby and file-wide search)
- [ ] Auto-fix mode
- [ ] Status tracking (valid, moved, stale)
- [ ] Validation summary reporting

### Phase 3: Search & Navigation (Week 3-4)
- [ ] Tag filtering
- [ ] Text search across descriptions
- [ ] `goto` command with editor integration
- [ ] Interactive mode with fuzzy finder
- [ ] Recently accessed sorting

### Phase 4: VS Code Extension (Week 4-6)
- [ ] Basic extension scaffolding
- [ ] Gutter icon decorations
- [ ] Command palette integration
- [ ] Sidebar bookmark list
- [ ] File watcher for external changes
- [ ] Keybindings

### Phase 5: Polish & Documentation (Week 6-7)
- [ ] Comprehensive error messages
- [ ] Configuration file support
- [ ] Export/import commands
- [ ] User documentation
- [ ] Example workflows
- [ ] Demo video

---

## Configuration

**Location**: `.sigil/config.json` (repository-specific) or `~/.sigil/config.json` (global)

```json
{
  "editor": {
    "command": "code",
    "args": ["--goto", "{file}:{line}"]
  },
  "validation": {
    "auto_validate_on_list": false,
    "context_lines": 1,
    "search_radius": 10
  },
  "display": {
    "date_format": "relative",
    "max_description_length": 50
  }
}
```

**Design decision**: Configuration is optional. Tool works with zero config, but power users can customize.

---

## Edge Cases & Limitations

### Known Limitations (Documented, Not Fixed in MVP)

1. **Binary files**: Cannot extract context from binary files (images, compiled code)
   - Mitigation: Detect and warn on bookmark creation

2. **Very long lines**: Context matching fails if lines are truncated
   - Mitigation: Store first N characters (e.g., 200) and match on that

3. **Generated files**: Bookmarks in generated code will break on regeneration
   - Mitigation: Warn if file path matches common patterns (e.g., `*.gen.go`)

4. **Merge conflicts**: Bookmarks file may have merge conflicts
   - Mitigation: Document manual resolution process

5. **Large files**: Validation of files >10k lines may be slow
   - Mitigation: Cache validation results, only re-validate on file change

### Explicitly Out of Scope for MVP

- Multi-repository bookmarks
- Shared/team bookmark synchronization
- LSP integration for semantic anchoring
- Bookmark history/versioning
- Integration with code review tools
- Bookmark collections/workspaces
- Import from other tools (IDE bookmarks, browser bookmarks)

---

## Success Metrics

### Technical Metrics
- All operations complete in <100ms for repos with <1000 bookmarks
- Validation correctly identifies 95%+ of moved bookmarks within ±10 lines
- Zero data loss (bookmarks never silently deleted or corrupted)

### Usage Metrics
- User creates 5+ bookmarks in first week (tool is useful)
- User accesses bookmarks 10+ times per week (tool is used regularly)
- User shares `.sigil/` directory in version control (tool is trusted)

### Feedback Metrics
- Users report which features they miss most (guides Phase 2 development)
- Users report false positive rates for staleness detection (tunes validation)
- Users request editor integrations (prioritizes editor support)

---

## Open Questions for Future Iteration

1. **Should bookmarks be personal or shared?**
   - MVP: Personal (in `.git/info/exclude` or global)
   - Future: Support both modes with clear semantics

2. **How should bookmark IDs be generated?**
   - MVP: Timestamp + random suffix (e.g., `bm_1709123456_a3f5`)
   - Future: Consider content-addressed IDs for stability

3. **Should we support bookmark hierarchies/groups?**
   - MVP: Flat
   - Future: Could add parent/child relationships or collections

4. **How should we handle renamed files?**
   - MVP: Bookmarks break, user updates manually
   - Future: Git integration to detect renames and update paths

5. **Should bookmarks support ranges (multiple lines)?**
   - MVP: Single line only
   - Future: Support line ranges for larger code blocks

6. **How should we integrate with Git workflows?**
   - MVP: None (bookmarks are independent of Git state)
   - Future: Could track bookmarks per branch, or relative to commits

7. **Should there be a daemon mode for better performance?**
   - MVP: No daemon, CLI invocation per command
   - Future: Optional daemon for instant editor updates

8. **How should we handle very large repositories (100k+ files)?**
   - MVP: Assume reasonably-sized repos (<10k files)
   - Future: Implement indexing and incremental validation

---

## Risk Assessment

### High Risk
**None** - MVP scope is intentionally conservative to minimize risk

### Medium Risk

1. **Context matching accuracy**
   - Risk: False positives (marking valid bookmarks as stale) or false negatives (missing moved bookmarks)
   - Mitigation: Start with exact matching, tune heuristics based on real usage data
   - Fallback: Users can manually review and update

2. **Cross-platform path handling**
   - Risk: Windows vs Unix path separators, case sensitivity
   - Mitigation: Use Rust's `std::path` which handles platform differences
   - Testing: Test on all three platforms (Linux, macOS, Windows)

3. **Editor integration reliability**
   - Risk: VS Code API changes, extension bugs, performance issues
   - Mitigation: Keep extension thin (delegate to CLI), version lock dependencies
   - Fallback: CLI works independently if extension fails

### Low Risk

1. **JSON parsing errors**
   - Risk: Corrupted bookmark file
   - Mitigation: Validate on read, atomic writes, backup before modifications
   - Recovery: User can manually edit JSON or restore from Git

2. **Performance with many bookmarks**
   - Risk: Slow operations with 1000+ bookmarks
   - Mitigation: Efficient data structures, lazy loading, caching
   - Monitoring: Benchmark with large bookmark files

3. **Concurrent access**
   - Risk: Two processes modifying bookmarks simultaneously
   - Mitigation: File locking, atomic writes
   - Acceptance: Rare edge case, manual resolution acceptable for MVP

---

## Testing Strategy

### Unit Tests

**CLI Core**:
- Bookmark creation, validation, serialization
- Context extraction from various file types
- Fuzzy matching algorithm
- Path normalization and resolution

**Coverage target**: 80%+ for core logic

### Integration Tests

**CLI Commands**:
- End-to-end command execution
- File system operations (create, read, update, delete)
- Error handling and edge cases
- Cross-platform path handling

**Test scenarios**:
- Create bookmark, validate it remains valid
- Modify file, validate bookmark updates correctly
- Delete file, validate bookmark marked as stale
- Multiple bookmarks in same file
- Bookmarks in nested directories

### Manual Testing

**Editor Integration**:
- Gutter icons display correctly
- Commands work from command palette
- Sidebar updates on external changes
- Keybindings function as expected
- Performance with large files

**User Workflows**:
- New user setup (zero config)
- Bookmark creation during code review
- Navigation during debugging
- Maintenance after major refactoring

### Performance Testing

**Benchmarks**:
- List 100 bookmarks: <10ms
- Validate 100 bookmarks: <500ms
- Add bookmark: <50ms
- Search bookmarks: <100ms

**Stress tests**:
- 1000 bookmarks in single repo
- Bookmarks in 10,000 line files
- Validation after 1000 line insertion

---

## Documentation Plan

### User Documentation

**README.md**:
- Quick start guide
- Installation instructions
- Basic usage examples
- Link to full documentation

**CLI_REFERENCE.md**:
- Complete command reference
- All flags and options
- Output format examples
- Configuration options

**WORKFLOWS.md**:
- Common use cases with examples
- Code review workflow
- Debugging workflow
- Learning/onboarding workflow
- Refactoring workflow

**EDITOR_INTEGRATION.md**:
- VS Code setup and usage
- Keybindings reference
- Troubleshooting common issues

### Developer Documentation

**ARCHITECTURE.md**:
- System design overview
- Data model explanation
- Validation algorithm details
- Extension points for future features

**CONTRIBUTING.md**:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

**ROADMAP.md**:
- MVP features (this spec)
- Planned future enhancements
- Community feature requests
- Known limitations and workarounds

---

## Deployment & Distribution

### CLI Tool

**Distribution channels**:
- **GitHub Releases**: Pre-built binaries for Linux, macOS, Windows
- **Cargo**: `cargo install sigil` for Rust users
- **Homebrew**: Formula for macOS users (after initial release)
- **Apt/Yum**: Packages for Linux distributions (future)

**Release process**:
1. Tag version in Git (e.g., `v0.1.0`)
2. CI builds binaries for all platforms
3. Create GitHub release with binaries and changelog
4. Publish to crates.io
5. Update documentation

### VS Code Extension

**Distribution**:
- **VS Code Marketplace**: Official extension registry
- **Open VSX**: For VSCodium and other compatible editors

**Release process**:
1. Version bump in `package.json`
2. Run tests and linting
3. Package extension: `vsce package`
4. Publish: `vsce publish`
5. Create Git tag matching version

### Versioning

**Semantic versioning** (SemVer):
- `0.1.0` - Initial MVP release
- `0.x.y` - Pre-1.0 releases (breaking changes allowed)
- `1.0.0` - Stable API, backward compatibility guarantees
- `1.x.0` - New features, backward compatible
- `1.x.y` - Bug fixes only

**Backward compatibility**:
- Bookmark file format version tracked in JSON
- CLI can read older formats, writes current format
- Migration path documented for breaking changes

---

## Launch Plan

### Pre-Launch (Week 6-7)

- [ ] Feature complete and tested
- [ ] Documentation written and reviewed
- [ ] Demo video recorded (3-5 minutes)
- [ ] Example repository with sample bookmarks
- [ ] Beta testing with 3-5 users
- [ ] Polish based on beta feedback

### Launch (Week 8)

**Announcement channels**:
- GitHub repository public release
- Reddit: r/programming, r/rust, r/vscode
- Hacker News: Show HN post
- Twitter/Mastodon: Developer communities
- Dev.to: Blog post with tutorial
- Personal blog/website

**Launch materials**:
- Clear README with GIF demos
- "Why I built this" blog post
- Comparison with existing tools
- Roadmap for future features
- Call for contributors

### Post-Launch (Week 9+)

**Community building**:
- Respond to issues and PRs promptly
- Weekly/biweekly release cadence
- Collect feature requests
- Prioritize based on user feedback
- Build contributor community

**Metrics to track**:
- GitHub stars and forks
- VS Code extension installs
- Issue reports and types
- Feature requests and patterns
- Community contributions

---

## Future Enhancements (Post-MVP)

### Phase 2: Enhanced Validation (Month 2-3)

- **Git integration**: Detect file renames and update bookmarks
- **Diff-based validation**: Use Git diffs to track code movement
- **Smart staleness**: Heuristics based on change magnitude
- **Bookmark history**: Track bookmark changes over time

### Phase 3: Semantic Features (Month 3-6)

- **LSP integration**: Anchor bookmarks to symbols (functions, classes)
- **Symbol tracking**: Follow code through refactorings
- **Language-aware validation**: Understand code structure
- **Multi-language support**: Start with popular languages (Rust, Python, TypeScript, Go)

### Phase 4: Collaboration (Month 6-9)

- **Shared bookmarks**: Team-wide bookmarks in VCS
- **Bookmark comments**: Discussion threads on bookmarks
- **Code review integration**: Link bookmarks to PRs/issues
- **Sync service**: Optional cloud sync for personal bookmarks

### Phase 5: Advanced Features (Month 9-12)

- **Bookmark collections**: Organize bookmarks into workspaces
- **Cross-repo bookmarks**: Reference code across repositories
- **AI-powered suggestions**: Suggest bookmarks for important code
- **Analytics**: Visualize codebase hotspots via bookmark density

### Phase 6: Ecosystem (Year 2+)

- **More editor integrations**: Vim, Emacs, JetBrains, Sublime
- **Browser extension**: Bookmark GitHub code in browser
- **IDE plugins**: Deep integration with IntelliJ, PyCharm, etc.
- **API/SDK**: Allow other tools to create/query bookmarks
- **Bookmark marketplace**: Share curated bookmark collections

---

## Conclusion

This MVP balances ambition with pragmatism. By accepting that bookmarks will sometimes break and focusing on making recovery easy, we can ship a useful tool quickly and learn from real usage.

The technical design is deliberately simple:
- **JSON storage** is VCS-friendly and human-readable
- **Context-based validation** is straightforward to implement and understand
- **CLI-first architecture** keeps the core logic editor-agnostic
- **Single-editor integration** proves the concept without overcommitting

Success looks like: **Developers use this tool daily for navigation, it saves them time, and they want more features.** That feedback loop will guide all future development.

The path from MVP to production-ready tool is clear, but we're not committing to it until we validate that the core concept resonates with users. If the MVP fails, we fail fast. If it succeeds, we have a solid foundation to build on.

**Estimated timeline**: 6-8 weeks from start to public launch for a solo developer working part-time, or 3-4 weeks full-time.

**Next steps**: 
1. Set up Rust project structure
2. Implement data model and JSON storage
3. Build core CLI commands (add, list, validate)
4. Test with real codebase usage
5. Iterate based on personal experience before adding editor integration

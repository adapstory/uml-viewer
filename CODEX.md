# Codex companion

The Codex launcher keeps the upstream viewer mailbox and starts Codex in a
project-specific tmux session. It refuses to replace a running companion.
It uses the existing Codex permissions and does not pass bypass flags.

Requirements: Java 21 or newer, Clojure CLI, tmux, and an authenticated
Codex CLI. Run these commands from the viewer repository to make a runtime
JAR, then run the launcher from the project being inspected:

```sh
sh scripts/build-viewer
cd /path/to/project
sh /path/to/uml-viewer/scripts/uml-codex view
```

Generate a diagram from a policy with:

```sh
sh /path/to/uml-viewer/scripts/uml-codex ir path/to/policy.edn
```

The JAR contains the viewer code, not Quil or a Java runtime. Clojure CLI
resolves Quil on first use. Without `target/viewer.jar`, the launcher loads
the pinned upstream viewer revision over HTTPS. `UML_VIEWER_JAR` may select
an existing packaged viewer. The first display can take time while Codex
inspects the project. Existing project instructions and permissions apply.

Closing the viewer ends its companion session. The launcher does not use
automatic respawn or replace an existing live session. The initial version
does not support `--restart`.

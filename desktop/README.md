# Codex Desktop integration

The MCP server compiles existing `.edn` diagrams with the viewer's own scene
compiler. It serves a local interactive view for Codex's browser panel. It
does not start another agent or change the diagram. The agent can edit or
generate EDN with the existing project tools, then refresh the view.

Requirements: Python 3.11+, `uv`, Clojure CLI, and Java 21+. In this directory:

```sh
uv sync --frozen
codex mcp add uml-viewer -- /absolute/path/to/uml-viewer/desktop/.venv/bin/uml-viewer-desktop
```

Set `JAVA_HOME` for the MCP server if the default Java is older than 21. The
agent calls `show_diagram` with an absolute EDN file path and opens the returned
URL with Codex's `open_in_codex` browser tool. Click a class or package, then
ask the agent about it; `get_selection` returns that choice. After editing the
EDN file, the agent calls `update_diagram`; the open view refreshes. Call
`close_diagram` when finished. A server restart ends its diagram sessions.

The page is served only on loopback, uses an unguessable session URL, and
accepts selections only from that local origin. Keep the URL private. This
browser view supports selection and refresh; hierarchical drilling, proposals,
and the complete desktop viewer controls are not yet implemented.

Run the MCP and HTTP integration test with:

```sh
uv run python -m unittest discover -s tests -v
```

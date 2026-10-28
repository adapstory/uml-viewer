(import '[java.net URL] '[clojure.lang DynamicClassLoader RT Var Compiler])

(def source-url
  "https://raw.githubusercontent.com/unclebob/uml-viewer/f65dafe93b3cb1b4e6bb02dbe41503ed05bd9ebf/src/")

(def loader (DynamicClassLoader. (RT/baseLoader)))
(.addURL loader (if-let [jar (System/getenv "UML_VIEWER_JAR")]
                  (.toURL (.toURI (java.io.File. jar)))
                  (URL. source-url)))

(defn resolve-var [symbol]
  (or (requiring-resolve symbol)
      (throw (ex-info "Viewer entry point unavailable" {:symbol symbol}))))

(defn run-viewer [args]
  (let [session-id (resolve-var 'uml-viewer.adapters.sketch/session-id)
        tmux! (resolve-var 'uml-viewer.adapters.sketch/tmux!)
        read-companion (resolve-var 'uml-viewer.domain.mailbox/read-companion)
        session (session-id (System/getProperty "user.dir"))
        previous (:session (read-companion (System/getProperty "user.dir")))
        args-var (resolve-var 'uml-viewer.adapters.sketch/new-session-args)
        open-var (resolve-var 'uml-viewer.adapters.sketch/open-in-terminal!)
        session-atom @(resolve-var 'uml-viewer.adapters.sketch/!session-name)
        window-atom @(resolve-var 'uml-viewer.adapters.sketch/!terminal-window-id)
        write-companion! (resolve-var 'uml-viewer.domain.mailbox/write-companion!)
        attach-command (resolve-var 'uml-viewer.adapters.sketch/attach-command)
        osascript (resolve-var 'uml-viewer.adapters.sketch/osascript)
        run-osascript (resolve-var 'uml-viewer.adapters.sketch/run-osascript)
        upstream-rules @(resolve-var 'uml-viewer.adapters.sketch/standing-rules)
        prompt (str "You are the Codex companion for UML viewer. Follow the project AGENTS.md and user permissions; do not create clones, worktrees, commits or pushes unless explicitly requested. "
                    "Use the current project as root. Your viewer is already running. "
                    "For IR generation use `uml-codex ir POLICY_PATH`; do not assume a clj alias exists. "
                    "The following describes the viewer mailbox and policy contract; ignore its instructions about launching Grok and its automatic commit, push, or worktree advice.\n\n"
                    upstream-rules)]
    (when (or (some #{"--restart"} args)
              (zero? (tmux! "has-session" "-t" session))
              (and previous (zero? (tmux! "has-session" "-t" previous))))
      (throw (ex-info "A viewer companion is already active or --restart was requested; refusing to replace it" {:session session :previous previous})))
    (alter-var-root args-var
      (constantly (fn
        ([cwd] ["new-session" "-d" "-s" (session-id cwd) "-c" cwd "codex" prompt])
        ([cwd name] ["new-session" "-d" "-s" name "-c" cwd "codex" prompt]))))
    (alter-var-root open-var
      (constantly
        (fn [cwd]
          (let [name (session-id cwd)]
            (when-not (zero? (apply tmux! (args-var cwd name)))
              (throw (ex-info "Could not start companion; no existing session was changed" {:session name})))
            (reset! session-atom name)
            (let [out (run-osascript (osascript (attach-command name) name))
                  win-id (re-find #"\d+" out)]
              (reset! window-atom win-id)
              (write-companion! cwd {:session name :window-id win-id})
              {:session name :window-id win-id})))))
    (apply (resolve-var 'uml-viewer.main.uml-viewer/-main) args)))

(with-bindings {Compiler/LOADER loader}
  (let [[command & args] *command-line-args*]
    (case command
      "ir" (apply (resolve-var 'uml-viewer.main.ir-generator/-main) args)
      "view" (run-viewer args)
      (throw (ex-info "Usage: uml-codex [view [edn-file] | ir policy.edn]" {:command command})))))

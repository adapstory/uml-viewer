(ns uml-viewer.main.desktop-json
  (:require [clojure.data.json :as json]
            [uml-viewer.application.document :as document]))

(defn -main [path]
  (let [{:keys [scene error]} (document/load-path path)]
    (when error
      (binding [*out* *err*] (println error))
      (System/exit 1))
    (println (json/write-str
               (-> scene
                   (select-keys [:title :size :packages :classes :edges])
                   (update :edges #(mapv (fn [edge] (select-keys edge [:from :to :kind :points :head])) %)))))))

import { getAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { resetWorkbenchState } from "@/services/workbench-state";

export function resetDemoWorkspace() {
  if (
    getAppPreferences().dataSourceMode !== "mock" ||
    getLocalSessionMeta()?.source === "import"
  )
    return false;
  for (const key of Array.from({ length: window.localStorage.length }, (_, i) =>
    window.localStorage.key(i),
  ).filter((key): key is string => key !== null)) {
    if (
      key === "rootlens.mock-backend-state" ||
      key.startsWith("rootlens.graph-draft.demo:")
    )
      window.localStorage.removeItem(key);
  }
  resetWorkbenchState();
  window.location.assign("/evidence");
  return true;
}

// ClawShell Local — Electron preload script (v3.0.0)
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("clawshell", {
  // App info
  getVersion: () => ipcRenderer.invoke("get-app-version"),

  getApiPort: () => ipcRenderer.invoke("get-api-port"),

  getUserDataPath: () => ipcRenderer.invoke("get-user-data-path"),

  // External
  openExternal: (url) => ipcRenderer.invoke("open-external", url),

  // Agent scanner
  scanAgents: () => ipcRenderer.invoke("scan-agents"),

  // Platform detection
  platform: process.platform,
  isElectron: true,
});

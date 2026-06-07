const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getBackendUrl: () => ipcRenderer.invoke("get-backend-url"),
  onBackendStatus: (callback) => {
    ipcRenderer.on("backend-status", (_event, status) => callback(status));
  },
  platform: process.platform,
});

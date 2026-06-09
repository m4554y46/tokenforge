const { app, BrowserWindow } = require("electron");
const path = require("path");

let mainWindow;

const BACKEND_URL = "http://127.0.0.1:8765";

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "TokenForge - Prompt Optimizer",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    backgroundColor: "#0a0e17",
    show: true,
  });

  mainWindow.loadFile(path.join(__dirname, "frontend", "index.html"));
  if (process.argv.includes("--dev") || !app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

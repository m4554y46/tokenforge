const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow;
let pythonProcess = null;

const BACKEND_PORT = 8765;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function findPython() {
  const candidates = ["python3", "python", "py"];
  for (const cmd of candidates) {
    try {
      const result = require("child_process").spawnSync(cmd, [
        "--version",
      ]);
      if (result.status === 0) {
        return cmd;
      }
    } catch (_) {}
  }
  return "python";
}

function killPort(port) {
  try {
    const { execSync } = require("child_process");
    const cmd = process.platform === "win32"
      ? `netstat -ano | findstr :${port}`
      : `lsof -ti:${port}`;
    const out = execSync(cmd, { timeout: 3000, encoding: "utf8" });
    const pids = out.match(/\d+/g) || [];
    pids.forEach((pid) => {
      try {
        process.kill(parseInt(pid));
      } catch (_) {}
    });
  } catch (_) {}
}

function startBackend() {
  // Backend is already running externally
  console.log("Backend managed externally on port", BACKEND_PORT);
  pythonProcess = null;
}

function stopBackend() {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

async function waitForBackend() {
  try {
    const http = require("http");
    await new Promise((resolve, reject) => {
      const req = http.get(`${BACKEND_URL}/api/health`, (res) => resolve(res));
      req.on("error", reject);
      req.setTimeout(2000, () => { req.destroy(); reject(new Error("timeout")); });
    });
    console.log("Backend is ready!");
    return true;
  } catch (e) {
    console.error("Backend not reachable:", e.message);
    return false;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "TokenForge - Prompt Optimizer",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
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
  startBackend();
  createWindow();

  const ready = await waitForBackend();
  if (!ready) {
    console.error("Backend failed to start in time");
  }

  if (mainWindow) {
    mainWindow.webContents.on("did-finish-load", () => {
      mainWindow.webContents.send("backend-status", ready ? "ready" : "error");
    });
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});

ipcMain.handle("get-backend-url", () => {
  return BACKEND_URL;
});

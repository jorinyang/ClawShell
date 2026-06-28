// ClawShell Local — Electron main process (v3.0.0)
const { app, BrowserWindow, shell, Menu, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow = null;
let nextServer = null;

const isDev = !app.isPackaged;
const NEXT_PORT = 3456;
const API_PORT = 8000;

// ── Next.js server (packaged) ────────────────────────────

function startNextServer() {
  if (isDev) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const serverPath = path.join(process.resourcesPath, "standalone", "server.js");
    const env = {
      ...process.env,
      PORT: String(NEXT_PORT),
      NODE_ENV: "production",
    };

    nextServer = spawn(process.execPath, [serverPath], {
      env,
      cwd: path.join(process.resourcesPath, "standalone"),
      stdio: ["ignore", "pipe", "pipe"],
    });

    let started = false;
    nextServer.stdout.on("data", (data) => {
      if (!started && data.toString().includes("ready")) {
        started = true;
        resolve();
      }
    });

    nextServer.stderr.on("data", (data) => {
      console.error("[next]", data.toString());
    });

    nextServer.on("error", reject);

    // Resolve after 10s even if "ready" not detected
    setTimeout(() => {
      if (!started) { started = true; resolve(); }
    }, 10000);
  });
}

// ── Window creation ──────────────────────────────────────

async function createWindow() {
  const url = isDev
    ? `http://localhost:${NEXT_PORT}`
    : `http://localhost:${NEXT_PORT}`;

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: "ClawShell Local",
    icon: path.join(__dirname, "..", "public", "icon.png"),
    backgroundColor: "#0a0a0b",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
    show: false,
    frame: true,
    titleBarStyle: "default",
  });

  // Window menu
  const menuTemplate = [
    {
      label: "ClawShell Local",
      submenu: [
        { label: "About ClawShell Local", role: "about" },
        { type: "separator" },
        { label: "Settings...", accelerator: "CmdOrCtrl+,", click: () => mainWindow.loadURL(`${url}/settings`) },
        { type: "separator" },
        { label: "Quit", accelerator: "CmdOrCtrl+Q", click: () => app.quit() },
      ],
    },
    {
      label: "View",
      submenu: [
        { label: "Reload", accelerator: "CmdOrCtrl+R", click: () => mainWindow.reload() },
        { label: "Toggle DevTools", accelerator: "F12", click: () => mainWindow.webContents.toggleDevTools() },
        { type: "separator" },
        { label: "Zoom In", accelerator: "CmdOrCtrl+=", role: "zoomIn" },
        { label: "Zoom Out", accelerator: "CmdOrCtrl+-", role: "zoomOut" },
        { label: "Reset Zoom", accelerator: "CmdOrCtrl+0", role: "resetZoom" },
      ],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "User Guide",
          click: () => shell.openExternal("https://github.com/jorinyang/ClawShell/blob/main/USER_GUIDE.md"),
        },
        {
          label: "Website",
          click: () => shell.openExternal("https://clawshell.club"),
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Handle links (open external in browser)
  mainWindow.webContents.on("will-navigate", (e, navUrl) => {
    const parsed = new URL(navUrl);
    if (parsed.hostname !== "localhost") {
      e.preventDefault();
      shell.openExternal(navUrl);
    }
  });

  await mainWindow.loadURL(url);
}

// ── IPC handlers ─────────────────────────────────────────

ipcMain.handle("get-api-port", () => API_PORT);

ipcMain.handle("get-app-version", () => app.getVersion());

ipcMain.handle("get-user-data-path", () => app.getPath("userData"));

ipcMain.handle("open-external", (_event, url) => {
  shell.openExternal(url);
});

// Agent scanner integration
ipcMain.handle("scan-agents", async () => {
  try {
    const script = path.join(__dirname, "..", "..", "local", "agent", "scanner.py");
    const proc = spawn("python3", ["-m", "local.agent.scanner", "--scan", "--json"], {
      cwd: path.join(__dirname, "..", ".."),
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    return new Promise((resolve) => {
      let stdout = "";
      proc.stdout.on("data", (d) => { stdout += d.toString(); });
      proc.on("close", () => {
        try { resolve(JSON.parse(stdout)); }
        catch { resolve({ agents: [], error: stdout }); }
      });
    });
  } catch (e) {
    return { agents: [], error: e.message };
  }
});

// ── App lifecycle ────────────────────────────────────────

app.whenReady().then(async () => {
  await startNextServer();
  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (nextServer) {
    nextServer.kill();
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (nextServer) {
    nextServer.kill();
  }
});

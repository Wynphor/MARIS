// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, Emitter};

/// 后端进程句柄（全局持有，退出时自动 kill）
struct BackendProcess(Mutex<Option<Child>>);

/// 启动 FastAPI 后端
#[tauri::command]
fn start_backend(app: AppHandle) -> Result<String, String> {
    let state = app.state::<BackendProcess>();
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    // 如果已经在运行，跳过
    if let Some(ref mut child) = *guard {
        if child.try_wait().ok().flatten().is_none() {
            return Ok("Backend already running".into());
        }
    }

    // 找到后端目录：优先检查 ../backend，其次当前目录下的 backend
    let backend_dir = find_backend_dir().ok_or("Cannot find backend/ directory")?;
    let python = find_python();

    // 启动 uvicorn
    let child = Command::new(&python)
        .args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
        .current_dir(&backend_dir)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start backend: {}", e))?;

    *guard = Some(child);

    // 发送事件通知前端
    let _ = app.emit("backend-status", "started");

    Ok(format!("Backend started from {:?}", backend_dir))
}

/// 停止后端
#[tauri::command]
fn stop_backend(app: AppHandle) -> Result<String, String> {
    let state = app.state::<BackendProcess>();
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;

    if let Some(ref mut child) = *guard {
        let _ = child.kill();
        child.wait().ok();
        *guard = None;
        let _ = app.emit("backend-status", "stopped");
        return Ok("Backend stopped".into());
    }

    Ok("Backend was not running".into())
}

/// 检查后端健康状态
#[tauri::command]
fn check_backend() -> bool {
    // 简单 TCP 连接检测
    std::net::TcpStream::connect("127.0.0.1:8000").is_ok()
}

/// 查找后端目录
fn find_backend_dir() -> Option<std::path::PathBuf> {
    // 相对于可执行文件位置
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();

    let candidates = [
        exe_dir.join("..").join("backend"),
        exe_dir.join("backend"),
        exe_dir.join("..").join("..").join("..").join("backend"), // 开发模式 target/release/../../../backend
        std::path::PathBuf::from("backend"),
    ];

    for dir in &candidates {
        let app_py = dir.join("app").join("main.py");
        if app_py.exists() {
            return Some(dir.canonicalize().unwrap_or(dir.clone()));
        }
    }

    // 当前工作目录
    let cwd = std::env::current_dir().ok()?;
    let cwd_backend = cwd.join("backend");
    if cwd_backend.join("app").join("main.py").exists() {
        return Some(cwd_backend);
    }

    None
}

/// 查找 Python 解释器
fn find_python() -> String {
    for name in &["python", "python3", "py"] {
        if Command::new(name).arg("--version").output().is_ok() {
            return name.to_string();
        }
    }
    "python".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            check_backend,
        ])
        .setup(|app| {
            // 应用启动时自动启动后端
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                // 等待 500ms 让窗口先显示
                std::thread::sleep(std::time::Duration::from_millis(500));

                // 检查后端是否已在运行
                if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
                    let _ = app_handle.emit("backend-status", "already_running");
                    return;
                }

                // 启动后端
                match start_backend(app_handle.clone()) {
                    Ok(msg) => {
                        let _ = app_handle.emit("backend-status", format!("started: {}", msg));
                        // 等待后端就绪（最多 10 秒）
                        for _ in 0..20 {
                            std::thread::sleep(std::time::Duration::from_millis(500));
                            if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
                                let _ = app_handle.emit("backend-status", "ready");
                                return;
                            }
                        }
                        let _ = app_handle.emit("backend-status", "timeout");
                    }
                    Err(e) => {
                        let _ = app_handle.emit("backend-status", format!("error: {}", e));
                    }
                }
            });
            Ok(())
        })
        .on_window_event(|_window, _event| {
            // Window events handled here if needed
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

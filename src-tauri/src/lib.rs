// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::process::Command;
use std::thread;
use std::time::Duration;

fn start_python_backend() {
    thread::spawn(|| {
        let venv_python = r"D:\Projects\cascade\cascade\backend\.venv\Scripts\python.exe";
        let backend_dir = r"D:\Projects\cascade\cascade\backend";

        let mut child = Command::new(venv_python)
            .args(&[
                "-m", "uvicorn",
                "main:app",
                "--host", "127.0.0.1",
                "--port", "5001",
                "--reload"
            ])
            .current_dir(backend_dir)
            .spawn()
            .expect("[Cascade] Failed to start Python backend");

        child.wait().expect("[Cascade] Backend process exited unexpectedly");
    });

    // Allow backend time to initialise before Tauri window loads
    thread::sleep(Duration::from_secs(3));
}

fn start_llama_server() {
    thread::spawn(|| {
        let llama_server = r"C:\llm\llama-server.exe";
        let mut child = Command::new(llama_server)
            .args(&[
                "--model", r"C:\llm\models\Qwen3.5-4B-Q4_K_M.gguf",
                "--n-gpu-layers", "28",
                "--ctx-size", "4096",
                "--port", "8080",
                "--host", "127.0.0.1"
            ])
            .spawn()
            .expect("[Cascade] Failed to start llama-server.exe");

        child.wait().expect("[Cascade] llama-server process exited unexpectedly");
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    start_llama_server();
    start_python_backend();

    // Allow servers time to initialise before Tauri window loads
    thread::sleep(Duration::from_secs(4));

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("[Cascade] Error running Tauri application");
}

# NL-Automation Host Agent

The host agent runs directly on your local machine (Windows, Linux, or macOS). It allows the containerized NL-Automation platform to safely inspect local metrics (such as Trash / Recycle Bin storage) and execute user-authorized host actions without exposing Docker to host root privileges.

---

## 💻 Installation

Install dependencies and install in editable mode:
```bash
cd host-agent
pip install -e .
```

---

## 🚀 Running the Agent

1. Generate an agent token in the Web UI (`/settings/host-agent` or via API Gateway):
   ```bash
   curl -X POST http://localhost:8080/api/v1/host-agents/tokens
   ```
2. Start the host agent on your computer:
   ```bash
   python -m host_agent run --token <your-token> --server http://localhost:8080
   ```

---

## 🛡️ Supported Operating Systems
* **Windows**: Uses Windows Shell API (`SHQueryRecycleBinW`, `SHEmptyRecycleBinW`).
* **Linux**: Freedesktop.org trash standard (`~/.local/share/Trash`).
* **macOS**: Apple Darwin trash folder (`~/.Trash`).

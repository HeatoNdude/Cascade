<h1 align="center">
  <br>
  🌊 Cascade
  <br>
</h1>

<h4 align="center">AI-Powered Code Intelligence and Blast Radius Simulation Engine</h4>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture-and-stack">Architecture</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="#usage">Usage</a>
</p>

## Overview

**Cascade** is a next-generation desktop application designed to help developers visualize, understand, and safely modify complex codebases. By parsing your entire repository into a dynamic dependency graph and indexing it with vector embeddings, Cascade allows you to semantically explore your codebase via **God View** and accurately simulate the cascading impacts of code changes (the **Blast Radius**) through intelligent traversal and AI synthesis.

---

## ⚡ Features

* **Interactive God View 🌌**  
  An interactive, zoomed semantic graph visualization of your repository's architecture. View how modules, functions, and classes interconnect, with automatic clustering and layout optimization.

* **AST-Powered Graph Engine 🌲**  
  Deeply parses the Python and TypeScript source code using `tree-sitter`, resolving structural edges (`contains`), dynamic dependencies (`calls`), and imports down to the function level.

* **Semantic Code Search 🧠**  
  Integration with FAISS and `sentence-transformers` automatically indexes codebase text and docstrings, allowing deep semantic search over your codebase rather than just regex keyword matching.

* **Simulation & Blast Radius Engine 💥**  
  Query a "What if?" scenario (e.g., *"what if we rename parse_file to parse_source_file?"*). Cascade traverses the dependency tree up to specific graph depths, cleanly categorizing affected components into 🔴 High, 🟡 Medium, and 🟢 Low Risks.

* **AI Synthesis 🤖**  
  Integration with local LLM (`llama.cpp` with GPU acceleration) synthesizes traversing reports into human-readable action items, highlighting exact downstream impacts and required fixes before you make a change.

---

## 🏗️ Architecture and Stack

Cascade is built with a highly decoupled client/server architecture:

### Frontend (Desktop Client)
* **Framework**: React / Next.js
* **Styling**: Tailwind CSS
* **Desktop Wrapper**: Tauri (Rust) for native lightweight OS integration
* **Graph Rendering**: Cytoscape / fcose (for God View interactive layouts)

### Backend (Graph & API Engine)
* **Framework**: FastAPI (Python / Uvicorn)
* **Graph Processing**: NetworkX
* **Parsing**: tree-sitter (for Python/TS AST generation)
* **Embeddings**: FAISS & sentence-transformers
* **LLM Backend**: llama-cpp-python (CUDA-enabled)

---

## 🚀 Getting Started

### Prerequisites
* Rust and Cargo (for Tauri)
* Node.js (v18+) and npm
* Python 3.11+
* (Optional) NVIDIA GPU + CUDA Toolkit for local LLM acceleration

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HeatoNdude/Cascade.git
   cd Cascade
   ```

2. **Set up the Backend:**
   ```bash
   cd backend
   python -m venv .venv
   .\.venv\Scripts\activate   # On Windows
   pip install -r requirements.txt
   ```

3. **Install Frontend Dependencies:**
   ```bash
   cd ..
   npm install
   ```

### Running the Application

Cascade requires both the backend API server and the Tauri frontend to be running simultaneously.

**Terminal 1: Start the Backend server**
```bash
cd backend
.\.venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 5001 --reload
```

**Terminal 2: Start the Frontend App**
```bash
# In the repository root
npm run tauri dev
```


---

## ⚠️ Hardware Limitations & Graceful Degradation

Running the local `llama.cpp` server for AST query resolution is highly hardware-dependent. 
On lower-end or older GPUs (e.g., **Nvidia GTX 1050**), LLM inference latency can be severely bottlenecked, sometimes exceeding 1-2 minutes per query.

To ensure a seamless developer experience, Cascade implements **Graceful Degradation Fallbacks**:
* **LLM Timeouts**: If the local model exceeds generation timeouts (60s for Explanations, 120s for Simulations), the query does not crash.
* **Deterministic Fallback**: Cascade intercepts the timeout or empty response and instantly synthesizes a structured Markdown table derived purely from the graph metadata (callers, callees, hop-distance, risk level).
* **Hybrid Routing**: Query intent classification is primarily handled by ultra-fast 0ms keyword matchers. The LLM zero-shot router (`IntentAgent`) is only invoked for highly ambiguous phrasing.

---
## 💡 Usage

### Loading a Repository
1. Open Cascade and navigate to the Repo Picker.
2. Select a targeted folder directory on your machine.
3. Cascade will begin the "Indexing" phase. This will build the initial Git Memory, parse the Abstract Syntax Trees, generate the vector embeddings in the `backend/cache/` directory, and construct the Graph Builder JSON structure.

### Exploring the Graph
* Jump into **God View** to see a bird's-eye map of module nodes.
* Scroll to zoom in and dynamically expose function and class-level nodes alongside their labels.
* Mouse hover over nodes to use the Node Inspector to see their underlying code, Git history, author, and docstrings.

### Running a Simulation
1. Open the Action / Query bar in God View.
2. Type an intent, such as: `what if we rename parse_file to parse_source_file`.
3. Hit enter and watch the SSE stream calculate the target nodes, trace upstream to pinpoint module callers, calculate hop distances, format the Blast Radius, and optionally query the local LLM to output a precise refactor protocol indicating what will break.

---

<p align="center">
  Built with ❤️ and AI.
</p>

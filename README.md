# 🔎 RepoLens AI

### AI-Powered GitHub Repository Investigator

RepoLens AI is a GenAI-powered application that allows developers to interact with GitHub repositories using natural language.

Instead of manually navigating through files and code, users can provide a GitHub repository URL and ask questions about its structure, implementation, and functionality.

The system combines **FastMCP, GitHub APIs, RAG, hybrid retrieval, LangGraph, and LLMs** to provide repository-aware answers.

---

## 🚀 Live Demo

🌐 **Frontend:**  
https://repolens-ai.streamlit.app

🔗 **Backend API:**  
https://repolens-fastapi.onrender.com

🔗 **MCP Server:**  
https://repolens-mcp-16hr.onrender.com

---

## ✨ Features

- 🔎 Analyze public GitHub repositories
- 📂 Explore repository file structure
- 📄 Read repository files
- 🧠 Ask natural-language questions about code
- 🔍 Semantic code search using RAG
- ⚡ Hybrid retrieval using dense + sparse search
- 🔀 Reciprocal Rank Fusion (RRF) for combining search results
- 🤖 LLM-powered repository investigation
- 💬 Stateful conversations with multiple chat threads
- ✏️ Rename chat sessions
- 🗑️ Delete chat sessions
- 🌐 Deployed frontend, backend, and MCP server

---

## 🏗️ Architecture

```text
                    User
                      │
                      ▼
              ┌───────────────┐
              │   Streamlit   │
              │    Frontend   │
              └───────┬───────┘
                      │ HTTP
                      ▼
              ┌───────────────┐
              │    FastAPI    │
              │     API       │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │   LangGraph   │
              │     Agent     │
              └───────┬───────┘
                      │
             ┌────────┴────────┐
             │                 │
             ▼                 ▼
      ┌─────────────┐   ┌──────────────┐
      │   FastMCP   │   │     RAG      │
      │    Client   │   │    Pipeline  │
      └──────┬──────┘   └──────┬───────┘
             │                 │
             ▼                 ▼
      ┌─────────────┐   ┌──────────────┐
      │ GitHub REST │   │   Pinecone   │
      │     API     │   │  + BM25      │
      └─────────────┘   └──────────────┘
                              │
                              ▼
                         ┌─────────┐
                         │  Groq   │
                         │   LLM   │
                         └─────────┘

<h1 align="center">Personal Memory Assistant</h1>

<p align="center">
  <strong>An AI-powered, offline-first desktop application that acts as an intelligent, semantic search engine for your local images and documents.</strong>
</p>

## ✨ Features

* **Semantic Image Search:** Find photos using natural language (e.g., "a sunset on the beach", "invoice from last month")—no exact file names required.
* **Semantic Document Search:** Search through the actual contents of PDFs, Word (\`.docx\`), and PowerPoint (\`.pptx\`) files based on meaning and context, not just keyword matching.
* **Real-time Background Monitoring:** Silently monitors your chosen folders (like Downloads or Documents) and automatically indexes new files as they arrive.
* **Offline & Private:** All processing, embedding generation, and vector storage happen locally on your machine. No data is ever uploaded to the cloud.
* **Modern Premium UI:** A sleek, glassmorphism-inspired PyQt5 interface with dark themes, neon glow effects, fluid animations, and system tray integration.

## 📸 Screenshots

*(Add your screenshots here!)*

> **Home Screen**
> <br/>
> `![Home Screen](link-to-screenshot.jpg)`

> **Image Search Results**
> <br/>
> `![Image Search](link-to-screenshot.jpg)`

> **Document Search Results**
> <br/>
> `![Document Search](link-to-screenshot.jpg)`

## 🛠️ Technologies Used

* **Language:** Python
* **GUI Framework:** PyQt5
* **Machine Learning / AI:** 
  * `PyTorch` & `Transformers` (Hugging Face)
  * **Image Search:** OpenAI `clip-vit-large-patch14`
  * **Document Search:** `all-MiniLM-L6-v2` (Sentence Transformers)
* **Vector Database:** ChromaDB
* **File System Monitoring:** Watchdog
* **Document Parsing:** PyMuPDF (`fitz`), `python-docx`, `python-pptx`

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Personal-Memory-Assistant.git
   cd Personal-Memory-Assistant
   ```

2. **Run the Application:**
   Run the following command to start the app:
   ```bash
   python desktop_app.py
   ```
   *(Note: The first time you run it, the app will download the necessary AI models, which may take a few minutes depending on your internet connection. After that, it works completely offline.)*

## 💡 Usage

* **Modes:** Click the hamburger menu (≡) in the top left to switch between "Images" and "Documents" search modes.
* **Searching:** Type a descriptive query (e.g., "dog playing in the park" or "tax documents 2023") and press Enter or the Search button.
* **Background Mode:** When you close the window, the app minimizes to the system tray and continues to monitor your folders for new files. You can right-click the tray icon to restore or quit.
* **Initial Scan:** Use the hamburger menu to run a full system scan and force index your specific directories manually if needed.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/YOUR_USERNAME/Personal-Memory-Assistant/issues).

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

# 🌌 ImageAI – Modern Streamlit App

[![Streamlit](https://img.shields.io/badge/Framework-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

_ImageAI_ is a **modern, user-friendly Streamlit application** for working with images.  
It features a clean UI, polished typography, and a dark theme powered by `style.css`.

---

## ✨ Features
- 🎨 **Modern UI**: Custom dark theme with cards, badges, and polished inputs  
- ⚡ **Streamlit-based**: Rapid, interactive experience in the browser  
- ☁️ **Config-ready**: Supports `service_account.json` for Google Cloud integrations (optional)  

---

## 📦 Prerequisites
- Python **3.9+** (recommended 3.10 or newer)  
- pip  
- (Optional) Virtual environment tool: `venv` or `conda`  

---

## 🚀 Quick Start

### Windows PowerShell
```powershell
# 1) Clone the repository
git clone <your-repo-url> ImageAI
cd ImageAI

# 2) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install dependencies
pip install -r requirements.txt

# 4) Run the app
streamlit run main.py
# or
streamlit run main_redesigned.py

➡️ Once running, Streamlit opens a local URL (usually http://localhost:8501).
⚙️ Configuration (Optional: Google Service Account)

If your app uses Google services:

    Place your credentials file in the project root as service_account.json

    Optionally set the environment variable so libraries can auto-detect credentials:

$env:GOOGLE_APPLICATION_CREDENTIALS = "${PWD}\service_account.json"

🎨 Styling

The app uses a dedicated stylesheet:

    style.css → global variables, cards, buttons, inputs, and badges

You can customize colors and spacing via the CSS variables (e.g., --primary-color, --bg) at the top of style.css.
📂 Project Structure

ImageAI/
├── main.py              # Primary Streamlit app entry
├── main_redesigned.py   # Alternate app entry
├── style.css            # Dark theme styling
├── requirements.txt     # Python dependencies
├── service_account.json # (Optional) Google credentials
└── deneme.py            # Additional scripts

🛠 Troubleshooting

    Port already in use
    streamlit run main.py --server.port 8502

    Dependency issues
    Upgrade pip:

python -m pip install --upgrade pip
pip install -r requirements.txt

Virtual env not activating
Run once:

    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

🤝 Contributing

    Fork the repo & create your branch:
    git checkout -b feature/your-feature

    Commit changes:
    git commit -m "Add your feature"

    Push the branch:
    git push origin feature/your-feature

    Open a Pull Request 🎉

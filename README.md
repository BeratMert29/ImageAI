## ImageAI – Modern Streamlit App

ImageAI is a modern, user-friendly Streamlit application for working with images. It features a clean UI, readable typography, and a dark theme powered by `style.css`.

### Features
- **Modern UI**: Custom dark theme with cards, badges, and polished inputs
- **Streamlit-based**: Rapid, interactive experience in the browser
- **Config-ready**: Supports a `service_account.json` for cloud integrations (optional)

### Prerequisites
- Python 3.9+ (recommended 3.10 or newer)
- pip
- (Optional) A virtual environment tool: `venv` or `conda`

### Quick Start (Windows PowerShell)
```powershell
# 1) Clone your repo (if you haven't already)
git clone <your-repo-url> ImageAI
cd ImageAI

# 2) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install dependencies
pip install -r requirements.txt

# 4) Run the app (choose the main file your project uses)
streamlit run main.py
# or
streamlit run main_redesigned.py
```

Once running, Streamlit will open a local URL (typically `http://localhost:8501`).

### Configuration (Optional: Google Service Account)
If your app uses Google services, place your credentials file at the project root:
- File: `service_account.json`

Optionally set the environment variable so libraries can auto-detect credentials:
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "${PWD}\service_account.json"
```

### Styling
The app uses a dedicated stylesheet:
- `style.css` – global variables, cards, buttons, inputs, and badges

You can tweak colors and spacing via the CSS variables at the top of `style.css` (e.g., `--primary-color`, `--bg`).

### Project Structure
```
ImageAI/
  main.py                 # Primary Streamlit app entry (or use main_redesigned.py)
  main_redesigned.py      # Alternate app entry
  style.css               # App styling (dark theme)
  requirements.txt        # Python dependencies
  service_account.json    # (Optional) Google credentials
  deneme.py               # Additional scripts
```

### Troubleshooting
- Port already in use: `streamlit run main.py --server.port 8502`
- Dependency issues: upgrade pip `python -m pip install --upgrade pip` then reinstall
- Virtual env not activating: In PowerShell, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try activation again

### Contributing
1. Create a feature branch: `git checkout -b feature/your-feature`
2. Commit your changes: `git commit -m "Add your feature"`
3. Push to the branch: `git push origin feature/your-feature`
4. Open a Pull Request

### License
This project is provided as-is. Add a license (e.g., MIT) if you intend to distribute.



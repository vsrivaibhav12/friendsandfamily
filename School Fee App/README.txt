:: create + activate venv
python -m venv .venv
.\.venv\Scripts\activate

:: install deps
pip install --upgrade pip
pip install -r requirements.txt

:: first-time init (creates db user owner/owner123)
python app.py --init

:: run (LAN-enabled)
python app.py --host 0.0.0.0 --port 5000
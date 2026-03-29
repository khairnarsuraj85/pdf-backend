# PDF Backend

Standalone Flask backend for PDF compression, splitting, merging, conversion, and AI-assisted helper endpoints.

## Stack

- Flask
- PyMuPDF
- Pillow
- OpenAI
- Google Gemini
- Gunicorn

## Structure

```text
pdf-backend/
|-- app.py
|-- gunicorn.conf.py
|-- render.yaml
|-- requirements.txt
|-- backend/
|   |-- routes/
|   |-- services/
|   |-- utils/
|   |-- config.py
|   `-- __init__.py
```

## Local run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Environment

Use `.env.example` as the base:

```env
FLASK_DEBUG=1
FLASK_USE_RELOADER=0
CORS_ORIGINS=http://localhost:5173
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
```

## Deploy on Render

- Blueprint file: `render.yaml`
- Python version: use the included `.python-version` file (`3.12`)
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn -c gunicorn.conf.py app:app`
- Health check path: `/health`

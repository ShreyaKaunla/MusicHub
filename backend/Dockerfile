FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Server code only. embeddings.py / evaluate.py / build_demo.py are offline tools.
COPY config.py main.py scan.py extras.py events.py identity.py userdata.py similarity.py taste.py ranker.py library.py ./

# The demo catalogue (Creative Commons songs) and its precomputed database
COPY demo_music ./demo_music
COPY demo_data/sql_db.db ./data/sql_db.db

ENV MUSIC_DIR=/app/demo_music \
    DATA_DIR=/app/data \
    ALLOW_FOLDER_PICK=0 \
    ALLOW_ANALYSIS=0 \
    SINGLE_USER=0

RUN useradd -m app && chown -R app /app
USER app

# Render/Fly/Railway provide $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

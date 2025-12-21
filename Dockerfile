FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV API_HOST=0.0.0.0 \
  API_PORT=10000 \
  BASE_URL="http://192.168.5.5:10000/bt/api" \
  DB_URL="mongodb://crawler:crawler_secure_password@192.168.5.5:27017/sehuatang" \
  DB_NAME="sehuatang" \
  SEARCH_TABLES="4k_video,anime_originate,asia_codeless_originate,asia_mosaic_originate,hd_chinese_subtitles,three_levels_photo,vegan_with_mosaic,magnent_links"

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-10000}"]

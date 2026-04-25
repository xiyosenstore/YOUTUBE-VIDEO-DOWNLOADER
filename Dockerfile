# Pake image Python yang enteng
FROM python:3.9-slim

# Install FFmpeg (wajib buat gabungin video/audio)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set folder kerja
WORKDIR /app

# Buat folder downloads dan kasih izin tulis
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# Copy semua file ke dalam image
COPY . .

# Install library
RUN pip install --no-cache-dir flask yt-dlp

# Port standar Hugging Face
EXPOSE 7860

# Jalankan aplikasi
CMD ["python", "app.py"]

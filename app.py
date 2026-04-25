from flask import Flask, request, jsonify, send_file, render_template_string
import yt_dlp
import os
import threading
import uuid
import shutil
import logging

app = Flask(__name__)

# Setup logging biar error keliatan di terminal
logging.basicConfig(level=logging.DEBUG)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

progress_store = {}

def get_html():
    path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html tidak ketemu!</h1>"

@app.route("/")
def index():
    return render_template_string(get_html())

@app.route("/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL kosong"}), 400
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "nocheckcertificate": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return jsonify({
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "channel": info.get("uploader", "Unknown"),
            "thumbnail": info.get("thumbnail", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download():
    data = request.json
    url = data.get("url", "").strip()
    fmt = data.get("format", "mp4").lower()
    quality = data.get("quality", "720")
    
    # ID Unik buat setiap proses download biar gak bentrok
    job_id = str(uuid.uuid4())
    progress_store[job_id] = {"status": "starting", "percent": 0, "filename": None, "error": None}

    def run():
        try:
            # Nama file pake job_id di depan biar browser anggep file baru terus
            out_template = os.path.join(DOWNLOAD_DIR, f"{job_id}-----%(title)s.%(ext)s")
            
            def progress_hook(d):
                if d["status"] == "downloading":
                    try:
                        p = d.get("_percent_str", "0%").replace("%", "").strip()
                        progress_store[job_id]["percent"] = float(p)
                    except: pass
                    progress_store[job_id]["status"] = "downloading"
                elif d["status"] == "finished":
                    progress_store[job_id]["status"] = "processing"

            ydl_opts = {
                "outtmpl": out_template,
                "progress_hooks": [progress_hook],
                "nocheckcertificate": True,
                "quiet": True
            }

            if fmt == "mp3":
                ydl_opts.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })
            elif fmt == "m4a":
                ydl_opts.update({
                    "format": "bestaudio[ext=m4a]/best",
                })
            else:
                # Video MP4/WebM
                ydl_opts.update({
                    "format": f"bestvideo[height<={quality}]+bestaudio/best[ext=m4a]/best[height<={quality}]",
                    "merge_output_format": fmt,
                })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Cek kalo file berubah ekstensi (khusus MP3)
                if fmt == "mp3":
                    actual_filename = os.path.splitext(filename)[0] + ".mp3"
                else:
                    actual_filename = filename

                # Pastiin file beneran ada sebelum kelar
                if os.path.exists(actual_filename):
                    progress_store[job_id]["filename"] = os.path.basename(actual_filename)
                    progress_store[job_id]["status"] = "done"
                else:
                    # Cari file yang mirip kalo pathnya meleset dikit
                    base_name = os.path.basename(os.path.splitext(filename)[0])
                    for f in os.listdir(DOWNLOAD_DIR):
                        if f.startswith(base_name):
                            progress_store[job_id]["filename"] = f
                            progress_store[job_id]["status"] = "done"
                            break

        except Exception as e:
            app.logger.error(f"Error: {str(e)}")
            progress_store[job_id]["status"] = "error"
            progress_store[job_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/progress/<job_id>")
def progress(job_id):
    return jsonify(progress_store.get(job_id, {"status": "not_found"}))

@app.route("/file/<job_id>")
def serve_file(job_id):
    info = progress_store.get(job_id)
    if not info or not info.get("filename"):
        return "File tidak ditemukan", 404
    
    file_path = os.path.join(DOWNLOAD_DIR, info["filename"])
    # Bersihin nama file pas di-save (buang job_id nya)
    display_name = info["filename"].split("-----")[-1]
    
    return send_file(file_path, as_attachment=True, download_name=display_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

import os
from flask import Flask, request, render_template_string, Response, stream_with_context
from playwright.sync_api import sync_playwright
import requests

app = Flask(__name__)

# Entire HTML Interface built straight into the Python code for a single-file deployment
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Interceptor Downloader</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background-color: #121212; 
            color: #ffffff; 
            text-align: center; 
            padding: 50px 20px; 
            margin: 0;
        }
        .container { 
            max-width: 600px; 
            margin: 0 auto; 
            background: #1e1e1e; 
            padding: 40px; 
            border-radius: 12px; 
            box-shadow: 0 8px 24px rgba(0,0,0,0.6); 
        }
        h1 { color: #ff0000; margin-bottom: 10px; font-size: 28px; }
        p { color: #aaa; margin-bottom: 30px; }
        input[type="text"] { 
            width: 90%; 
            padding: 14px; 
            border: 2px solid #333; 
            border-radius: 6px; 
            background: #252525; 
            color: #fff; 
            font-size: 16px; 
            margin-bottom: 20px;
            outline: none;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus { border-color: #ff0000; }
        button { 
            padding: 14px 35px; 
            background: #ff0000; 
            color: #fff; 
            border: none; 
            border-radius: 6px; 
            font-size: 16px; 
            cursor: pointer; 
            font-weight: bold; 
            text-transform: uppercase;
        }
        button:hover { background: #cc0000; }
        .info-box {
            margin-top: 25px;
            font-size: 13px;
            color: #888;
            background: #151515;
            padding: 15px;
            border-radius: 6px;
            text-align: left;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bypass Downloader</h1>
        <p>Intercepts raw YouTube data streams via automated browser automation</p>
        
        <form action="/download" method="GET">
            <input type="text" name="url" placeholder="Paste YouTube Video URL here..." required>
            <br>
            <button type="submit">Extract & Download</button>
        </form>

        <div class="info-box">
            <strong>How it works:</strong> This app launches a real Chromium web browser instance in the background, navigates directly to the target video URL, sniffs out the underlying server-generated playback stream, and channels the data directly back to your device.
        </div>
    </div>
</body>
</html>
"""

def get_raw_youtube_stream(video_url):
    # Detect environment context to manage headless state
    is_render = os.environ.get('RENDER') == 'true'
    is_headless = True if is_render else False
    
    print(f"[*] Starting browser interceptor (Headless={is_headless})...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=is_headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        stream_urls = []

        # Hook into network request flows to pull raw video playback streams
        def intercept_network(request):
            url = request.url
            if "googlevideo.com/videoplayback" in url:
                if url not in stream_urls:
                    stream_urls.append(url)

        page.on("request", intercept_network)
        
        try:
            page.goto(video_url, timeout=60000)
            page.wait_for_timeout(8000)  # Maintain active session to ensure traffic generation
        except Exception as e:
            print(f"[-] Navigation encounter error: {e}")
        finally:
            browser.close()
        
        return stream_urls[0] if stream_urls else None

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download')
def download():
    target_url = request.args.get('url')
    if not target_url:
        return "Error: Missing URL parameter.", 400
        
    raw_stream_url = get_raw_youtube_stream(target_url)
    if not raw_stream_url:
        return "Error: Failed to safely intercept the underlying stream. YouTube blocked the automation.", 500

    # Stream the file back using chunked distribution to avoid connection timeouts
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    stream_response = requests.get(raw_stream_url, headers=request_headers, stream=True)
    
    def data_generator():
        for chunk in stream_response.iter_content(chunk_size=16384):
            if chunk:
                yield chunk

    return Response(
        stream_with_context(data_generator()),
        mimetype="video/mp4",
        headers={"Content-Disposition": "attachment; filename=downloaded_video.mp4"}
    )

if __name__ == '__main__':
    # Dynamic port configuration to satisfy cloud service assignment parameters
    assigned_port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=assigned_port)

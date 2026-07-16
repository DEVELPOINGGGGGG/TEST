import os
import random
import requests
from flask import Flask, request, render_template_string, Response, stream_with_context
from playwright.sync_api import sync_playwright

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stream Interceptor Downloader</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #121212; color: #ffffff; text-align: center; padding: 50px 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #1e1e1e; padding: 40px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }
        h1 { color: #ff0000; }
        input[type="text"] { width: 90%; padding: 14px; border: 2px solid #333; border-radius: 6px; background: #252525; color: #fff; font-size: 16px; margin-bottom: 20px; }
        button { padding: 14px 35px; background: #ff0000; color: #fff; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
        button:hover { background: #cc0000; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bypass Downloader + Free Proxy Engine</h1>
        <p>Automatically scraping and applying free proxies to beat the data center ban.</p>
        <form action="/download" method="GET">
            <input type="text" name="url" placeholder="Paste YouTube Video URL here..." required>
            <br>
            <button type="submit">Extract & Download</button>
        </form>
    </div>
</body>
</html>
"""

def get_live_free_proxy():
    """Fetches a brand new list of free HTTP proxies on the fly"""
    print("[PROXY LOG] Fetching fresh free proxy pool...")
    try:
        # Pulls live anonymous proxies from a public API pool
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=anonymous"
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            proxies = response.text.strip().split("\r\n")
            if proxies:
                selected_proxy = random.choice(proxies)
                print(f"[PROXY LOG] Successfully picked free proxy: http://{selected_proxy}")
                return f"http://{selected_proxy}"
    except Exception as e:
        print(f"[PROXY ERROR] Failed to fetch free proxy api: {e}")
    return None

def get_raw_youtube_stream(video_url):
    is_render = os.environ.get('RENDER') == 'true'
    is_headless = True if is_render else False
    
    # Grab our free proxy server dynamically
    proxy_server = get_live_free_proxy()
    
    launch_args = {"headless": is_headless}
    
    # If a free proxy was fetched successfully, inject it directly into the browser settings
    if proxy_server:
        launch_args["proxy"] = {"server": proxy_server}
        print(f"[LOG] Directing browser traffic through proxy: {proxy_server}")
    else:
        print("[LOG] No proxy available, falling back to direct server IP.")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            stream_urls = []

            def intercept_network(request):
                url = request.url
                if "googlevideo.com/videoplayback" in url:
                    if url not in stream_urls:
                        stream_urls.append(url)

            page.on("request", intercept_network)
            
            print(f"[LOG] Navigating proxy browser to: {video_url}")
            page.goto(video_url, timeout=60000)
            page.wait_for_timeout(8000)
            
            browser_cookies = context.cookies()
            browser.close()
            
            target_stream = None
            for stream in stream_urls:
                if "mime=video" in stream:
                    target_stream = stream
                    break
            if not target_stream and stream_urls:
                target_stream = stream_urls[0]
                
            return target_stream, browser_cookies, proxy_server
            
        except Exception as e:
            print(f"[CRITICAL BROWSER ERROR] Proxy failed or timed out: {e}")
            return None, None, None

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/download')
def download():
    target_url = request.args.get('url')
    if not target_url:
        return "Error: Missing URL parameter.", 400
        
    raw_stream_url, browser_cookies, used_proxy = get_raw_youtube_stream(target_url)
    
    if not raw_stream_url:
        return "Error: The free proxy timed out or YouTube blocked it. Try refreshing to roll a new proxy!", 500

    request_cookies = {cookie['name']: cookie['value'] for cookie in browser_cookies}
    
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    
    # Route the final download request through the EXACT same proxy server used by the browser
    download_proxies = {"http": used_proxy, "https": used_proxy} if used_proxy else None
    
    try:
        stream_response = requests.get(
            raw_stream_url, 
            headers=request_headers, 
            cookies=request_cookies, 
            proxies=download_proxies, 
            stream=True, 
            timeout=15
        )
        
        if stream_response.status_code != 200:
            return f"Download failed. Proxy returned status code {stream_response.status_code}", 500

        def data_generator():
            for chunk in stream_response.iter_content(chunk_size=32768):
                if chunk:
                    yield chunk

        return Response(
            stream_with_context(data_generator()),
            mimetype="video/mp4",
            headers={"Content-Disposition": "attachment; filename=video.mp4"}
        )
    except Exception as e:
        return f"Download connection broke due to proxy instability: {e}", 500

if __name__ == '__main__':
    assigned_port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=assigned_port)

import urllib.request

proxy = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7890"})
opener = urllib.request.build_opener(proxy)
url = "https://huggingface.co/Systran/faster-whisper-base/resolve/main/model.bin"
req = urllib.request.Request(url, method="HEAD")
resp = opener.open(req, timeout=15)
print(f"Status: {resp.status}")
print(f"Content-Length: {resp.headers.get('Content-Length', '?')}")
print(f"Content-Type: {resp.headers.get('Content-Type', '?')}")
for h in resp.headers:
    if "content" in h.lower() or "location" in h.lower():
        print(f"  {h}: {resp.headers[h]}")

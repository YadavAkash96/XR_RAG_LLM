**activate env:**
```
cd E:\MS_AI\Sem-IV\event-gpt

.\event-gpt\Scripts\activate
```

**local query retrieval run:**
```
(event-gpt) PS E:\XRAI\XR_RAG_LLM\src> python .\query_adrant.py
```


**Host LLM to local api**:


```
pip install uvicorn

uvicorn <filename: app>:<initialized variable>app --reload --host 0.0.0.0 <iphost>

```

**if accessing user is on same Wi-Fi then api can be accessible using endpoint:**

```
e.g. IPv4 Address. . . . . . . . . . . : 192.168.0.232
```

**Example of communication:**

```
(event-gpt) PS E:\XRAI\XR_RAG_LLM\src> uvicorn app:app --reload --host 0.0.0.0
INFO:     Will watch for changes in these directories: ['E:\\XRAI\\XR_RAG_LLM\\src']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1932] using StatReload
INFO:     Started server process [12584]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:57659 - "GET /docs HTTP/1.1" 200 OK
INFO:     127.0.0.1:57659 - "GET /openapi.json HTTP/1.1" 200 OK
INFO:     127.0.0.1:57665 - "POST /ask_xr HTTP/1.1" 200 OK
```

**To test locally use Swagger UI**

```
http://127.0.0.1:8000/docs#/default/ask_xr_assistant_ask_xr_post
```

**To test from any other device: make sure connected to same Wi-Fi as hosted locally.**

```
http://<ipaddress-of-host-device:<port-number>8000>/docs
```

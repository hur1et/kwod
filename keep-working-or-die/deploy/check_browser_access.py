"""One benign HTTPS connectivity probe through the provisioned runtime IPC."""
import json
from kwod.browser_gateway import BrowserClient

def main():
    result=BrowserClient().open('https://example.org/')
    ok=result.get('ok') is True and result.get('http_status')==200 and bool(result.get('text'))
    print(json.dumps({'browser_https_probe':ok,'page_text_received':ok,
                     'model_calls':0,'worker_started':False,'birth':False}))
    if not ok: raise SystemExit('controlled_browser_probe_failed')

if __name__=='__main__': main()

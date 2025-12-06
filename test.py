import urllib.request
url = 'https://a164c1b38d8e.ngrok-free.app/pifagor/submit_card_result'
req = urllib.request.Request(url, data=b'{"result":{}}', headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    print(resp.status, resp.read())

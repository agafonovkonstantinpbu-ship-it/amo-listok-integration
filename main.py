from flask import Flask, request, jsonify
import requests
import os
import re

app = Flask(__name__)

LISTOK_DOMAIN = os.getenv("LISTOK_DOMAIN", "https://an10569.listokcrm.ru")
LISTOK_TOKEN = os.getenv("LISTOK_TOKEN")
LISTOK_OFFICE_ID = int(os.getenv("LISTOK_OFFICE_ID", 1))
LISTOK_SOURCE_ID = int(os.getenv("LISTOK_SOURCE_ID", 1))

@app.route('/')
def health():
    return "OK", 200

@app.route('/amo-to-listok', methods=['POST'])
def amo_to_listok():
    data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
    
    # Ищем телефон - любые 10-11 цифр подряд
    phone = ''
    for value in data.values():
        val = str(value)
        digits = re.sub(r'\D', '', val)  # Оставляем только цифры
        if len(digits) == 11 and digits[0] in '78':
            phone = digits
            break
        elif len(digits) == 10:
            phone = '7' + digits
            break
    
    # Ищем имя
    name = 'Клиент'
    for key, value in data.items():
        if key.endswith('[name]') and value:
            name = str(value)
            break
    
    if not phone:
        return jsonify({"error": "No phone found", "data": data}), 400
    
    # Отправляем в ListOK
    headers = {
        "Authorization": f"Bearer {LISTOK_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Проверяем существование
    check = requests.get(f"{LISTOK_DOMAIN}/api/external/v2/contacts?phone={phone}", headers=headers)
    if check.status_code == 200 and check.json().get('data'):
        return jsonify({"status": "exists"}), 200
    
    # Создаем
    resp = requests.post(
        f"{LISTOK_DOMAIN}/api/external/v2/contacts",
        headers=headers,
        json={
            "name": name,
            "phone": phone,
            "email": "",
            "gender": "female",
            "can_sms": True,
            "can_email": True,
            "added_office_id": LISTOK_OFFICE_ID,
            "source_id": LISTOK_SOURCE_ID
        }
    )
    
    return jsonify({"status": "ok", "code": resp.status_code}), 200 if resp.status_code in [200, 201] else 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

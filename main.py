from flask import Flask, request, jsonify
import requests
import os
import json
import re

app = Flask(__name__)

LISTOK_DOMAIN = os.getenv("LISTOK_DOMAIN", "https://an10569.listokcrm.ru")
LISTOK_TOKEN = os.getenv("LISTOK_TOKEN")
LISTOK_OFFICE_ID = int(os.getenv("LISTOK_OFFICE_ID", 1))
LISTOK_SOURCE_ID = int(os.getenv("LISTOK_SOURCE_ID", 1))

@app.route('/')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/amo-to-listok', methods=['POST'])
def amo_to_listok():
    try:
        # Получаем данные
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        print(f"📥 Получен вебхук. Ключи: {list(data.keys())}")
        
        name = 'Без имени'
        phone = ''
        email = ''

        # 1. Поиск Имени
        # Ищем в ключах те, что заканчиваются на [name]
        for key, value in data.items():
            if key.endswith('[name]'):
                name = str(value)
                print(f"✅ Имя найдено в ключе {key}: {name}")
                break
        # Если не нашли, пробуем стандартное поле
        if name == 'Без имени' and 'name' in 
            name = data['name']

        # 2. Поиск Телефона
        # Регулярка для поиска 10-11 цифр
        phone_pattern = re.compile(r'(?:\+7|8|7)?\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}')
        
        for key, value in data.items():
            val_str = str(value) # Превращаем всё в строку для поиска
            
            # Если ключ содержит phone/tel
            if 'phone' in key.lower() or 'tel' in key.lower():
                clean = ''.join(filter(str.isdigit, val_str))
                if 10 <= len(clean) <= 11:
                    phone = clean
                    print(f"✅ Телефон найден по ключу {key}: {phone}")
                    break
            
            # Если значение похоже на телефон (даже если ключ не содержит phone)
            if not phone:
                match = phone_pattern.search(val_str)
                if match:
                    clean = ''.join(filter(str.isdigit, match.group(0)))
                    if 10 <= len(clean) <= 11:
                        phone = clean
                        print(f"✅ Телефон найден перебором в значении: {phone}")
                        break

        # 3. Поиск Email
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        for key, value in data.items():
            val_str = str(value)
            if 'email' in key.lower():
                match = email_pattern.search(val_str)
                if match:
                    email = match.group(0)
                    print(f"✅ Email найден: {email}")
                    break
            if not email:
                match = email_pattern.search(val_str)
                if match:
                    email = match.group(0)
                    print(f"✅ Email найден перебором: {email}")
                    break

        if not phone and not email:
            print(f"❌ Не нашли телефон или email в данных!")
            return jsonify({"status": "error", "message": "No phone/email found"}), 400

        # Отправка в ListOK
        headers = {
            "Authorization": f"Bearer {LISTOK_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Проверка существования
        if phone:
            check_resp = requests.get(f"{LISTOK_DOMAIN}/api/external/v2/contacts?phone={phone}", headers=headers)
            if check_resp.status_code == 200:
                existing = check_resp.json().get('data', [])
                if existing:
                    return jsonify({"status": "exists", "id": existing[0].get('id')}), 200

        # Создание
        payload = {
            "name": name,
            "phone": phone,
            "email": email,
            "gender": "female",
            "can_sms": True,
            "can_email": True,
            "added_office_id": LISTOK_OFFICE_ID,
            "source_id": LISTOK_SOURCE_ID
        }
        
        print(f"📤 Создаем в ListOK: {payload}")
        
        resp = requests.post(f"{LISTOK_DOMAIN}/api/external/v2/contacts", headers=headers, json=payload)
        
        if resp.status_code in [200, 201]:
            return jsonify({"status": "ok", "listok_id": resp.json().get('contact_id')}), 200
        else:
            print(f"❌ Ошибка ListOK: {resp.text}")
            return jsonify({"status": "error", "details": resp.text}), 500

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/callback')
def callback():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

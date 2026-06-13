from flask import Flask, request, jsonify
import requests
import os
import re

app = Flask(__name__)

LISTOK_DOMAIN = os.getenv("LISTOK_DOMAIN", "https://an10569.listokcrm.ru")
LISTOK_TOKEN = os.getenv("LISTOK_TOKEN")
LISTOK_OFFICE_ID = int(os.getenv("LISTOK_OFFICE_ID", 1))
LISTOK_SOURCE_ID = int(os.getenv("LISTOK_SOURCE_ID", 1))

# ID и секрет интеграции для OAuth
INTEGRATION_ID = "a20368eb-ec3a-4d18-99d5-31af6171f296"
INTEGRATION_SECRET = "PTC0MIXPBChmlXMiOnkXSbeYuEEORbUlJ8f97jXL"

@app.route('/')
def health():
    return "OK", 200

@app.route('/amo-to-listok', methods=['POST'])
def amo_to_listok():
    try:
        data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        print(f"📥 Получено данных: {len(data)}")

        phone = ''
        phone_candidates = []
        
        # Шаг 1: Ищем в ключах, содержащих 'phone', 'tel', 'mobile'
        for key, value in data.items():
            key_lower = key.lower()
            if 'phone' in key_lower or 'tel' in key_lower or 'mobile' in key_lower:
                val = str(value)
                digits = re.sub(r'\D', '', val)
                if len(digits) >= 10 and not digits.startswith('1'):
                    if len(digits) == 11:
                        phone_candidates.append(digits)
                    elif len(digits) == 10 and digits[0] in '789':
                        phone_candidates.append('7' + digits)
        
        # Шаг 2: Если не нашли по ключам, ищем форматы телефонов
        if not phone_candidates:
            for value in data.values():
                val = str(value)
                matches = re.findall(r'(?:\+7|8)[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', val)
                for match in matches:
                    digits = re.sub(r'\D', '', match)
                    if len(digits) == 11:
                        phone_candidates.append(digits)
        
        # Шаг 3: Ищем просто 10-11 цифр, но НЕ timestamps
        if not phone_candidates:
            for value in data.values():
                val = str(value)
                digits = re.sub(r'\D', '', val)
                if len(digits) == 11 and digits[0] in '78':
                    phone_candidates.append(digits)
                elif len(digits) == 10 and digits[0] in '9834':
                    phone_candidates.append('7' + digits)
        
        # Берем первый найденный номер
        if phone_candidates:
            phone = phone_candidates[0]
            print(f"✅ Найдено телефонов: {len(phone_candidates)}, используем: {phone}")
        else:
            print("❌ Телефоны не найдены")

        # Имя
        name = 'Клиент'
        for key, value in data.items():
            if key.endswith('[name]') and value:
                name = str(value)
                break

        print(f"🔍 Итог: Имя='{name}', Телефон='{phone}'")
        
        if not phone:
            return jsonify({"error": "Phone not found"}), 400

        # Используем Bearer токен
        headers = {
            "Authorization": f"Bearer {LISTOK_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Проверяем существование
        try:
            check = requests.get(f"{LISTOK_DOMAIN}/api/external/v2/contacts?phone={phone}", headers=headers, timeout=5)
            print(f"🔍 Check ListOK status: {check.status_code}")
            
            if check.status_code == 200:
                try:
                    resp_data = check.json()
                    if resp_data.get('data'):
                        print(f"✅ Клиент уже существует")
                        return jsonify({"status": "exists"}), 200
                except:
                    print(f"⚠️ Ответ не JSON: {check.text[:100]}")
        except Exception as e:
            print(f"⚠️ Ошибка проверки: {e}")

        # Создаем
        print(f"📤 Создаем: {name}, {phone}")
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
            },
            timeout=10
        )
        
        print(f"📤 Ответ ListOK: {resp.status_code}")
        
        if resp.status_code in [200, 201]:
             return jsonify({"status": "ok"}), 200
        else:
             print(f"❌ Ошибка: {resp.text[:200]}")
             return jsonify({"status": "error", "details": resp.text}), 500

    except Exception as e:
        print(f"💥 Ошибка: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/callback')
def callback():
    """Обработка OAuth callback и получение access token"""
    code = request.args.get('code')
    if not code:
        return "❌ Код не получен. Проверь URL.", 400
    
    print(f"📥 Получен код: {code[:50]}...")
    
    # Данные для обмена кода на токен
    token_url = "https://an10569.listokcrm.ru/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": INTEGRATION_ID,
        "client_secret": INTEGRATION_SECRET,
        "redirect_uri": "https://scaling-telegram-6974x97v9vgv25vqw-5000.app.github.dev/callback",
        "code": code
    }
    
    try:
        resp = requests.post(token_url, json=payload)
        print(f"📤 Ответ от ListOK: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            
            print(f"✅✅✅ УСПЕХ! ACCESS TOKEN: {access_token} ✅✅✅")
            print(f"🔄 Refresh Token: {refresh_token}")
            
            return f"✅ Токен получен! Проверь логи на Render.<br><br>Access Token: {access_token}<br><br>Скопируй этот токен и вставь в переменную LISTOK_TOKEN на Render!"
        else:
            print(f"❌ Ошибка: {resp.text}")
            return f"Ошибка {resp.status_code}: {resp.text}"
            
    except Exception as e:
        print(f"❌ Исключение: {str(e)}")
        return f"Ошибка: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

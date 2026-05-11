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
    try:
        data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        print(f"📥 Получены данные. Полей: {len(data)}")

        phone = ''
        
        # 1. Сначала ищем значения, похожие на телефон по формату (+, -, скобки)
        for value in data.values():
            val = str(value)
            if any(c in val for c in ['+', '(', ')', '-']):
                digits = re.sub(r'\D', '', val)
                if len(digits) == 11:
                    phone = digits
                    print(f"✅ Найден форматированный номер: {phone}")
                    break
                elif len(digits) == 10 and digits[0] in '98':
                    phone = '7' + digits
                    print(f"✅ Найден форматированный номер (10 цифр): {phone}")
                    break
        
        # 2. Если не нашли, ищем просто 11 цифр, начинающихся на 7 или 8
        if not phone:
            for value in data.values():
                val = str(value)
                digits = re.sub(r'\D', '', val)
                if len(digits) == 11 and digits[0] in '78':
                    # Исключаем таймстампы (обычно начинаются на 1, но на всякий случай)
                    if not digits.startswith('1'): 
                        phone = digits
                        print(f"✅ Найден номер (11 цифр): {phone}")
                        break
        
        # 3. Если не нашли, ищем 10 цифр, начинающихся на 9 (мобильный без кода) или 8
        if not phone:
            for value in data.values():
                val = str(value)
                digits = re.sub(r'\D', '', val)
                if len(digits) == 10 and digits[0] in '9834':
                    # Исключаем таймстампы (начинаются на 1)
                    phone = '7' + digits
                    print(f"✅ Найден номер (10 цифр): {phone}")
                    break

        # Имя
        name = 'Клиент'
        for key, value in data.items():
            if key.endswith('[name]') and value:
                name = str(value)
                break

        print(f"🔍 Итог: Имя='{name}', Телефон='{phone}'")
        
        if not phone:
            print("❌ Телефон не найден!")
            return jsonify({"error": "Phone not found"}), 400

        headers = {
            "Authorization": f"Bearer {LISTOK_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Проверяем существование
        try:
            check = requests.get(f"{LISTOK_DOMAIN}/api/external/v2/contacts?phone={phone}", headers=headers)
            print(f"🔍 Check ListOK status: {check.status_code}")
            # Если ответ не JSON (например, HTML страница ошибки), выводим начало
            if 'application/json' not in check.headers.get('Content-Type', ''):
                 print(f"⚠️ Ответ ListOK не JSON: {check.text[:100]}")
            else:
                resp_data = check.json()
                if resp_data.get('data'):
                    print(f"✅ Клиент уже существует")
                    return jsonify({"status": "exists"}), 200
        except Exception as e:
            print(f"❌ Ошибка проверки: {e}")

        # Создаем
        print(f"📤 Создаем клиента: {name}, {phone}")
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
        
        print(f"📤 Ответ ListOK: {resp.status_code} - {resp.text[:200]}")
        
        if resp.status_code in [200, 201]:
             return jsonify({"status": "ok"}), 200
        else:
             return jsonify({"status": "error", "details": resp.text}), 500

    except Exception as e:
        print(f"💥 Ошибка: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

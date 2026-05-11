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
        
        print(f"📥 Получено данных: {len(data)}")

        phone = ''
        phone_candidates = []
        
        # Шаг 1: Ищем в ключах, содержащих 'phone', 'tel', 'mobile'
        for key, value in data.items():
            key_lower = key.lower()
            if 'phone' in key_lower or 'tel' in key_lower or 'mobile' in key_lower:
                val = str(value)
                digits = re.sub(r'\D', '', val)
                # Проверяем что это телефон, а не timestamp
                if len(digits) >= 10 and not digits.startswith('1'):
                    if len(digits) == 11:
                        phone_candidates.append(digits)
                    elif len(digits) == 10 and digits[0] in '789':
                        phone_candidates.append('7' + digits)
        
        # Шаг 2: Если не нашли по ключам, ищем форматы телефонов (с +, -, скобками)
        if not phone_candidates:
            for value in data.values():
                val = str(value)
                # Ищем паттерны типа +7 (999) 123-45-67 или 8-999-123-45-67
                matches = re.findall(r'(?:\+7|8)[\s\-\(\)]?\d{3}[\s\-\(\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', val)
                for match in matches:
                    digits = re.sub(r'\D', '', match)
                    if len(digits) == 11:
                        phone_candidates.append(digits)
        
        # Шаг 3: Если всё ещё не нашли, ищем просто 10-11 цифр, но НЕ timestamps
        if not phone_candidates:
            for value in data.values():
                val = str(value)
                digits = re.sub(r'\D', '', val)
                # Timestamps обычно начинаются с 1 и имеют 10 цифр (типа 1778509428)
                # Телефоны России начинаются с 7, 8 или 9
                if len(digits) == 11 and digits[0] in '78':
                    phone_candidates.append(digits)
                elif len(digits) == 10 and digits[0] in '9834':  # 9XX, 8XX, 3XX, 4XX
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

        # ВАРИАНТ 2: Токен с префиксом "Token"
        headers = {
            "Authorization": f"Token {LISTOK_TOKEN}",
            "Content-Type": "application/json"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

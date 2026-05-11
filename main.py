from flask import Flask, request, jsonify
import requests
import os
import json
import re

# Создание Flask приложения
app = Flask(__name__)

# ⚙️ НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
LISTOK_DOMAIN = os.getenv("LISTOK_DOMAIN", "https://an10569.listokcrm.ru")
LISTOK_TOKEN = os.getenv("LISTOK_TOKEN")
LISTOK_OFFICE_ID = int(os.getenv("LISTOK_OFFICE_ID", 1))
LISTOK_SOURCE_ID = int(os.getenv("LISTOK_SOURCE_ID", 1))

# Маршрут для проверки работоспособности
@app.route('/')
def health():
    return jsonify({
        "status": "ok",
        "message": "Интеграция AMO → ListOK работает!"
    }), 200

# Основной маршрут для получения вебхуков от AMO
@app.route('/amo-to-listok', methods=['POST'])
def amo_to_listok():
    try:
        # Получаем данные
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        print(f"📥 Получен вебхук от АМО")
        print(f"📥 Тип данных: {type(data)}")
        
        name = 'Без имени'
        phone = ''
        email = ''

        # 1. Попытка стандартного парсинга (если пришел JSON с контактом)
        if '_embedded' in data and 'contacts' in data.get('_embedded', {}):
            contact = data['_embedded']['contacts'][0]
            name = contact.get('name', 'Без имени')
            
            # Поиск телефона в custom_fields
            custom_fields = contact.get('custom_fields', [])
            for field in custom_fields:
                field_name = field.get('name', '').lower()
                if 'телефон' in field_name or 'phone' in field_name or 'tel' in field_name:
                    values = field.get('values', [])
                    if values:
                        phone = values[0].get('value', '')
                        phone = ''.join(filter(str.isdigit, phone))
                        print(f"✅ Телефон найден в custom_fields: {phone}")
                        break
            
            # Поиск email
            for field in custom_fields:
                field_name = field.get('name', '').lower()
                if 'email' in field_name or 'почта' in field_name:
                    values = field.get('values', [])
                    if values:
                        email = values[0].get('value', '')
                        print(f"✅ Email найден: {email}")
                        break
        else:
            # Если структура нестандартная, берем имя из сделки
            if 'leads[update][0][name]' in 
                name = data['leads[update][0][name]']
            elif 'name' in 
                name = data['name']

        # 2. Универсальный поиск телефона (Regex)
        # Ищем любую строку, похожую на телефон, во всех значениях
        phone_pattern = re.compile(r'(?:\+7|8|7)?\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}')
        
        if not phone:  # Если телефон еще не найден
            for key, value in data.items():
                # Если ключ содержит слово phone или tel, пробуем взять значение
                if 'phone' in key.lower() or 'tel' in key.lower():
                    clean_val = ''.join(filter(str.isdigit, str(value)))
                    if 10 <= len(clean_val) <= 11:
                        phone = clean_val
                        print(f"✅ Телефон найден по ключу {key}: {phone}")
                        break
                
                # Если значение похоже на телефон
                elif isinstance(value, str) and not phone:
                    match = phone_pattern.search(value)
                    if match:
                        found = match.group(0)
                        clean_val = ''.join(filter(str.isdigit, found))
                        if 10 <= len(clean_val) <= 11:
                            phone = clean_val
                            print(f"✅ Телефон найден перебором значений: {phone}")
                            break

        # 3. Универсальный поиск email
        if not email:
            email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
            for key, value in data.items():
                if 'email' in key.lower() or 'почта' in key.lower():
                    if isinstance(value, str) and email_pattern.search(value):
                        email = email_pattern.search(value).group(0)
                        print(f"✅ Email найден по ключу {key}: {email}")
                        break
                elif isinstance(value, str) and not email:
                    match = email_pattern.search(value)
                    if match:
                        email = match.group(0)
                        print(f"✅ Email найден перебором: {email}")
                        break

        if not phone and not email:
            print(f"❌ Телефон не найден! Данные: {data}")
            return jsonify({"status": "error", "message": "Нет телефона или email"}), 400

        # Заголовки для ListOK
        headers = {
            "Authorization": f"Bearer {LISTOK_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Проверка существования клиента
        if phone:
            check_response = requests.get(
                f"{LISTOK_DOMAIN}/api/external/v2/contacts?phone={phone}",
                headers=headers
            )
            if check_response.status_code == 200:
                existing = check_response.json().get('data', [])
                if existing:
                    print(f"⚠️ Клиент уже существует: {existing[0].get('id')}")
                    return jsonify({
                        "status": "exists", 
                        "listok_id": existing[0].get('id')
                    }), 200

        # Создание нового клиента
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
        
        print(f"📤 Отправляем в ListOK: {payload}")
        
        response = requests.post(
            f"{LISTOK_DOMAIN}/api/external/v2/contacts",
            headers=headers,
            json=payload
        )
        
        print(f"📤 Ответ от ListOK: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201]:
            contact_id = response.json().get('contact_id')
            return jsonify({
                "status": "ok", 
                "listok_id": contact_id,
                "message": "Клиент создан"
            }), 200
        else:
            return jsonify({
                "status": "error", 
                "details": response.text
            }), 500

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

# Маршрут для OAuth callback
@app.route('/callback')
def callback():
    return jsonify({"status": "ok", "message": "Callback received"}), 200

# Запуск приложения
if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

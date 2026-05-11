from flask import Flask, request, jsonify
import requests
import os
import json

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
        # Пробуем получить данные разными способами
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        # 🔥 ПОЛНОЕ ЛОГИРОВАНИЕ для отладки
        print(f"📥 Получен вебхук от AMO")
        print(f"📥 Тип данных: {type(data)}")
        print(f"📥 Ключи: {data.keys() if isinstance(data, dict) else 'N/A'}")
        
        # Выводим первые 1000 символов данных
        print(f"📥 Данные: {json.dumps(data, ensure_ascii=False)[:1000]}")
        
        # Извлекаем данные контакта
        if '_embedded' in 
            contact = data['_embedded'].get('contacts', [{}])[0]
        elif 'contacts' in data:
            contact = data['contacts'][0] if data['contacts'] else {}
        elif 'id' in data and 'name' in 
            # Возможно данные приходят сразу как контакт
            contact = data
        else:
            contact = data
        
        print(f"📥 Контакт: {json.dumps(contact, ensure_ascii=False)[:1000]}")
        
        name = contact.get('name', 'Без имени')
        
        # Извлечение телефона - пробуем разные варианты
        phone = ''
        custom_fields = contact.get('custom_fields', [])
        
        print(f"📥 Custom fields count: {len(custom_fields)}")
        
        for field in custom_fields:
            field_name = field.get('name', '').lower()
            field_id = field.get('id')
            values = field.get('values', [])
            
            print(f"🔍 Поле ID={field_id}, name='{field_name}', values={values}")
            
            if 'телефон' in field_name or 'phone' in field_name or 'tel' in field_name:
                if values:
                    phone = values[0].get('value', '')
                    print(f"✅ Найден телефон: {phone}")
                break
        
        # Извлечение email
        email = ''
        for field in custom_fields:
            field_name = field.get('name', '').lower()
            if 'email' in field_name or 'почта' in field_name:
                values = field.get('values', [])
                if values:
                    email = values[0].get('value', '')
                    print(f"✅ Найден email: {email}")
                break
        
        # Очистка телефона (оставляем только цифры)
        phone = ''.join(filter(str.isdigit, phone))
        
        if not phone and not email:
            print(f"❌ Нет телефона или email!")
            print(f"❌ Имя: {name}")
            print(f"❌ Все поля: {list(contact.keys())}")
            return jsonify({"status": "error", "message": "Нет телефона или email"}), 400
        
        # Заголовки для API ListOK
        headers = {
            "Authorization": f"Bearer {LISTOK_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Проверяем, существует ли клиент по телефону
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
        
        # Создаем нового клиента
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

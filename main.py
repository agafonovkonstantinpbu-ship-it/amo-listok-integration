@app.route('/amo-to-listok', methods=['POST'])
def amo_to_listok():
    try:
        # Пробуем получить данные разными способами
        if request.is_json:
            data = request.get_json()
        else:
            # Если не JSON, пробуем получить как form data
            data = request.form.to_dict() if request.form else request.get_json(silent=True) or {}
        
        print(f"📥 Получен вебхук от AMO: {type(data)}")
        
        # Извлекаем данные контакта (структура может отличаться)
        if '_embedded' in data:
            contact = data['_embedded'].get('contacts', [{}])[0]
        elif 'contacts' in data:
            contact = data['contacts'][0] if data['contacts'] else {}
        else:
            contact = data
        
        name = contact.get('name', 'Без имени')
        
        # Извлечение телефона
        phone = ''
        for field in contact.get('custom_fields', []):
            field_name = field.get('name', '').lower()
            if 'телефон' in field_name or 'phone' in field_name or 'tel' in field_name:
                phone = field.get('values', [{}])[0].get('value', '')
                break
        
        # Извлечение email
        email = ''
        for field in contact.get('custom_fields', []):
            field_name = field.get('name', '').lower()
            if 'email' in field_name or 'почта' in field_name:
                email = field.get('values', [{}])[0].get('value', '')
                break
        
        # Очистка телефона (оставляем только цифры)
        phone = ''.join(filter(str.isdigit, phone))
        
        if not phone and not email:
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

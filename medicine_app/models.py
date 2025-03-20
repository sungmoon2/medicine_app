# 데이터베이스 모델링 - 추후 개발 시 사용
class User:
    def __init__(self, id=None, username=None, name=None, age=None, ssn=None, phone=None, height=None, weight=None):
        self.id = id
        self.username = username
        self.name = name
        self.age = age
        self.ssn = ssn
        self.phone = phone
        self.height = height
        self.weight = weight

class Medicine:
    def __init__(self, id=None, name=None, ingredient=None, effect=None, usage_info=None, caution=None, company=None):
        self.id = id
        self.name = name
        self.ingredient = ingredient
        self.effect = effect
        self.usage_info = usage_info
        self.caution = caution
        self.company = company

class UserMedicine:
    def __init__(self, id=None, user_id=None, medicine_id=None, dosage=None, start_date=None, end_date=None, reminder=False, reminder_time=None, notes=None):
        self.id = id
        self.user_id = user_id
        self.medicine_id = medicine_id
        self.dosage = dosage
        self.start_date = start_date
        self.end_date = end_date
        self.reminder = reminder
        self.reminder_time = reminder_time
        self.notes = notes

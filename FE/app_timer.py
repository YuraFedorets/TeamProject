#"https://docs.google.com/spreadsheets/d/1OmPRt9XXVSnn7lcruKcThq6pVnzO_muoRmePd_W1Ojk/export?format=csv"
import json
import os
import csv
import requests
from io import StringIO
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = 'ukd_secret_key_6000_full_sync'

# Файли бази даних
DATABASE_FILE = 'database.json'
# Ваше посилання для експорту (автоматично конвертується в CSV)
SHEET_EXPORT_URL = "https://docs.google.com/spreadsheets/d/1OmPRt9XXVSnn7lcruKcThq6pVnzO_muoRmePd_W1Ojk/export?format=csv"

# Початкові дані (Розширено до 5 розробників)
DEFAULT_DATA = {
    "users": [
        {
            "id": 1, "username": "admin", "password": "123", "role": "ADMIN", 
            "fullname": "Адміністратор", "email": "admin@ukd.edu.ua", 
            "avatar": "https://cdn-icons-png.flaticon.com/512/6024/6024190.png", "room": "Деканат"
        },
        {
            "id": 2, "username": "teacher", "password": "123", "role": "TEACHER", 
            "fullname": "проф. Іваненко О.М.", "email": "ivanenko@ukd.edu.ua", 
            "avatar": "https://cdn-icons-png.flaticon.com/512/1995/1995531.png", "room": "402"
        }
    ],
    "subjects": [
        {"id": 1, "name": "Загальновійськова підготовка", "teacher_id": 2},
        {"id": 2, "name": "Програмування", "teacher_id": 2}
    ],
    "absences": [],
    "creators": [
        {"name": "Олександр", "role": "Backend Lead", "desc": "Архітектор серверної частини та безпеки даних.", "skills": "Python, Flask, JSON, SQL", "avatar": ""},
        {"name": "Марія", "role": "UI/UX Designer", "desc": "Дизайнер інтерфейсу. Створила стиль УКД.", "skills": "Tailwind, Figma, Adobe Suite", "avatar": ""},
        {"name": "Дмитро", "role": "Frontend Dev", "desc": "Майстер інтерактивності та таймерів.", "skills": "JS, Animations, React, CSS3", "avatar": ""},
        {"name": "Олена", "role": "QA Engineer", "desc": "Тестування системи на помилки та стабільність.", "skills": "Unit Testing, Debugging, QA Docs", "avatar": ""},
        {"name": "Артем", "role": "Data Architect", "desc": "Оптимізація збереження даних та безпека профілів.", "skills": "JSON, Security Protocols, Excel Sync", "avatar": "https://cdn-icons-png.flaticon.com/512/616/616438.png"}
    ]
}

def load_data():
    if not os.path.exists(DATABASE_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Міграція та перевірка полів
            for u in data.get('users', []):
                if 'email' not in u: u['email'] = f"{u.get('username', 'user')}@ukd.edu.ua"
                if 'avatar' not in u: u['avatar'] = "https://cdn-icons-png.flaticon.com/512/354/354637.png"
                if 'fullname' not in u: u['fullname'] = u.get('username', 'Користувач')
            
            # Якщо в базі менше 5 творців, оновлюємо їх до повного складу
            if 'creators' not in data or len(data.get('creators', [])) < 5:
                data['creators'] = DEFAULT_DATA['creators']
            
            return data
    except:
        return DEFAULT_DATA

def save_data(data):
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def sync_data_from_sheets():
    db = load_data()
    try:
        response = requests.get(SHEET_EXPORT_URL, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code != 200:
            return False, f"Помилка доступу: {response.status_code}"
        
        csv_reader = csv.reader(StringIO(response.text))
        rows = list(csv_reader)
        
        users_added = 0
        absences_added = 0
        subject = db['subjects'][0] # Дефолтний предмет
        
        for i in range(4, len(rows)):
            row = rows[i]
            if not row or len(row) < 2: continue
            
            fullname = row[1].strip()
            if not fullname or fullname.isdigit(): continue

            student = next((u for u in db['users'] if u.get('fullname') == fullname), None)
            if not student:
                student = {
                    "id": len(db['users']) + 1,
                    "username": f"std_{len(db['users'])}",
                    "password": "123",
                    "role": "STUDENT",
                    "fullname": fullname,
                    "email": f"std_{len(db['users'])}@ukd.edu.ua",
                    "avatar": "https://cdn-icons-png.flaticon.com/512/354/354637.png",
                    "course": "1", "specialty": "ІПЗ", "institution": "Університет"
                }
                db['users'].append(student)
                users_added += 1

            for cell_idx in range(2, len(row)):
                if row[cell_idx].strip().lower() == 'н':
                    deadline = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT23:59")
                    exists = any(a for a in db['absences'] if a.get('student_id') == student['id'] and a.get('subject_id') == subject['id'])
                    if not exists:
                        db['absences'].append({
                            "id": len(db['absences']) + 1,
                            "student_id": student['id'],
                            "subject_id": subject['id'],
                            "deadline": deadline,
                            "status": "active"
                        })
                        absences_added += 1
        
        save_data(db)
        return True, f"Синхронізація успішна! Додано студентів: {users_added}, виявлено Н: {absences_added}."
    except Exception as e:
        return False, f"Помилка: {str(e)}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Таймер но 6 тисяч | УКД</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --ukd-red: #4a0404; --ukd-bright: #8b0000; }
        body { background-color: var(--ukd-red); color: white; font-family: 'Inter', sans-serif; }
        .card { background: white; color: black; border-left: 8px solid black; transition: 0.3s; }
        .nav-btn.active { border-bottom: 2px solid white; font-weight: bold; }
        .timer-badge { background: var(--ukd-bright); color: white; padding: 4px 12px; border-radius: 8px; font-weight: bold; font-family: monospace; }
        .accordion-content { max-height: 0; overflow: hidden; transition: 0.4s ease-out; }
        .accordion-item.active .accordion-content { max-height: 600px; padding-top: 20px; }
        .accordion-item.active .chevron { transform: rotate(180deg); }
        .process-link {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #fff;
            color: #000;
            padding: 10px 20px;
            border-radius: 50px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 800;
            text-transform: uppercase;
            font-size: 12px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.5);
            transition: 0.3s;
            z-index: 100;
        }
        .process-link:hover { transform: scale(1.1); background: var(--ukd-bright); color: #fff; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Навігація -->
    <nav class="bg-black p-4 sticky top-0 z-50 shadow-2xl">
        <div class="container mx-auto flex justify-between items-center">
            <div class="flex items-center space-x-3 cursor-pointer" onclick="showTab('main')">
                <div class="bg-red-700 p-2 rounded-lg"><i class="fas fa-hourglass-half text-white"></i></div>
                <span class="text-xl font-black uppercase tracking-tighter">Таймер но 6 тисяч</span>
            </div>
            
            <div class="hidden md:flex space-x-6 items-center flex-grow justify-center">
                <button onclick="showTab('main')" id="btn-main" class="nav-btn active px-2 py-1">Головна</button>
                {% if session.get('role') %}
                    <button onclick="showTab('timers')" id="btn-timers" class="nav-btn px-2 py-1">Мої Н</button>
                    {% if session.get('role') in ['ADMIN', 'TEACHER'] %}
                        <button onclick="showTab('admin')" id="btn-admin" class="nav-btn text-yellow-400 px-2 py-1">Керування</button>
                    {% endif %}
                    <button onclick="showTab('profile')" id="btn-profile" class="nav-btn px-2 py-1">Профіль</button>
                {% endif %}
                <button onclick="showTab('creators')" id="btn-creators" class="nav-btn px-2 py-1">Творці</button>
            </div>

            <div class="flex items-center space-x-4">
                {% if session.get('username') %}
                    <div class="flex items-center space-x-2">
                        <img src="{{ current_user.get('avatar', '') }}" class="w-8 h-8 rounded-full border border-white/50">
                        <a href="/logout" class="text-red-500 hover:text-white transition ml-10"><i class="fas fa-sign-out-alt text-xl"></i></a>
                    </div>
                {% else %}
                    <button onclick="toggleLogin(true)" class="bg-white text-black px-5 py-1.5 rounded-full font-bold">Вхід</button>
                {% endif %}
            </div>
        </div>
    </nav>

    <main class="container mx-auto px-4 py-12 flex-grow relative">
        <!-- Головна сторінка -->
        <section id="tab-main" class="tab-content max-w-4xl mx-auto">
            <div class="text-center mb-12">
                <h1 class="text-6xl font-black mb-4 uppercase tracking-tighter">УКД ПЛАТФОРМА</h1>
                <p class="opacity-60 italic">Офіційний сервіс моніторингу заборгованостей</p>
            </div>
            <div class="space-y-6">
                <div class="accordion-item bg-black/30 rounded-2xl p-6 border border-white/10" onclick="this.classList.toggle('active')">
                    <div class="flex justify-between items-center cursor-pointer">
                        <h3 class="text-2xl font-bold italic"><i class="fas fa-info-circle mr-3"></i>Про проект</h3>
                        <i class="fas fa-chevron-down chevron transition-transform"></i>
                    </div>
                    <div class="accordion-content opacity-70 text-lg">
                        "Таймер но 6 тисяч" - це інноваційна система для студентів УКД, яка дозволяє в реальному часі відстежувати терміни відпрацювання Н.
                    </div>
                </div>
                <div class="accordion-item bg-black/30 rounded-2xl p-6 border border-white/10" onclick="this.classList.toggle('active')">
                    <div class="flex justify-between items-center cursor-pointer">
                        <h3 class="text-2xl font-bold italic"><i class="fas fa-video mr-3"></i>Відео-гайд</h3>
                        <i class="fas fa-chevron-down chevron transition-transform"></i>
                    </div>
                    <div class="accordion-content text-center">
                        <p class="mb-6">Інструкція по роботі з сайтом:</p>
                        <a href="https://www.youtube.com/watch?v=YAgJ9XugGBo&t=5018s" target="_blank" class="inline-flex items-center space-x-3 bg-red-600 px-10 py-4 rounded-full font-bold">
                            <i class="fab fa-youtube text-2xl"></i> <span>ВІДКРИТИ НА YOUTUBE</span>
                        </a>
                    </div>
                </div>
            </div>
        </section>

        <!-- Таймери -->
        <section id="tab-timers" class="tab-content hidden">
            <h2 class="text-3xl font-black mb-8 border-b border-white/10 pb-4 uppercase">Активні Н</h2>
            <div class="grid gap-4">
                {% for item in user_absences %}
                <div class="card p-6 rounded-2xl flex flex-col md:flex-row justify-between items-center shadow-lg">
                    <div class="flex items-center space-x-6 text-left w-full">
                        <div class="bg-red-800 text-white p-4 rounded-xl font-black text-2xl">H</div>
                        <div class="flex-grow">
                            <h4 class="text-2xl font-black uppercase leading-tight">{{ item.get('subject_name', '???') }}</h4>
                            <button onclick='showStudentProfile({{ item.student|tojson }})' class="text-red-700 font-bold hover:underline">
                                Студент: {{ item.get('student_name', '...') }}
                            </button>
                            <p class="text-xs opacity-50 mt-1">Дедлайн: <span class="text-black font-bold" data-deadline="{{ item.get('deadline', '') }}"></span></p>
                        </div>
                    </div>
                    <div class="flex flex-col md:items-end mt-4 md:mt-0 space-y-2 w-full md:w-auto">
                        <div class="timer-badge text-xl" data-timer-until="{{ item.get('deadline', '') }}">...</div>
                        {% if session.get('role') in ['ADMIN', 'TEACHER'] %}
                            <button onclick="resolveN({{ item.id }})" class="bg-green-600 text-white px-6 py-1.5 rounded-lg text-xs font-bold uppercase w-full">Відпрацьовано</button>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- Керування -->
        <section id="tab-admin" class="tab-content hidden">
            <div class="grid lg:grid-cols-2 gap-8">
                <div class="bg-black/20 p-8 rounded-3xl border border-white/10 text-center flex flex-col items-center">
                    <i class="fas fa-sync text-5xl text-blue-500 mb-6"></i>
                    <h3 class="text-2xl font-bold mb-4">Google Sheets</h3>
                    <button onclick="syncSheets()" id="sync-btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase">Синхронізувати</button>
                </div>
                <div class="bg-black/20 p-8 rounded-3xl border border-white/10">
                    <h3 class="text-2xl font-bold mb-6 text-yellow-400">Додати Користувача</h3>
                    <form action="/api/add_user" method="POST" class="space-y-4">
                        <select name="role" onchange="toggleRegFields(this.value)" class="w-full p-3 rounded-xl bg-white text-black font-bold">
                            <option value="STUDENT">Студент</option>
                            <option value="TEACHER">Викладач</option>
                        </select>
                        <input type="text" name="fullname" placeholder="ПІБ" required class="w-full p-3 rounded-xl bg-white text-black font-bold">
                        <input type="email" name="email" placeholder="Email" required class="w-full p-3 rounded-xl bg-white text-black font-bold">
                        <div id="reg-teacher-fields" class="hidden">
                            <input type="text" name="room" placeholder="Кабінет" class="w-full p-3 rounded-xl bg-white text-black font-bold border-2 border-red-500">
                        </div>
                        <div class="flex space-x-2">
                            <input type="text" name="username" placeholder="Логін" required class="w-1/2 p-3 rounded-xl bg-white text-black">
                            <input type="text" name="password" placeholder="Пароль" required class="w-1/2 p-3 rounded-xl bg-white text-black">
                        </div>
                        <button class="w-full bg-green-600 text-white py-3 rounded-xl font-black uppercase">ЗБЕРЕГТИ</button>
                    </form>
                </div>
            </div>
        </section>

        <!-- Творці (Повернуто до 5 карток) -->
        <section id="tab-creators" class="tab-content hidden text-center relative min-h-[500px]">
            <h2 class="text-4xl font-black mb-12 uppercase tracking-tighter">Команда проекту</h2>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
                {% for dev in creators %}
                <div class="bg-white/5 p-8 rounded-3xl border border-white/10 hover:border-red-500 transition-all flex flex-col h-full">
                    <div class="w-16 h-16 bg-red-800 rounded-full mx-auto mb-4 flex items-center justify-center font-bold text-2xl shadow-lg overflow-hidden">
                        {% if dev.get('avatar') %}
                            <img src="{{ dev.get('avatar') }}" class="w-full h-full object-cover">
                        {% else %}
                            {{ dev.get('name', 'D')[0] }}
                        {% endif %}
                    </div>
                    <h4 class="font-bold text-xl">{{ dev.get('name', 'Розробник') }}</h4>
                    <p class="text-red-400 text-xs uppercase mb-4 tracking-widest">{{ dev.get('role', 'Dev') }}</p>
                    <p class="text-sm opacity-60 leading-relaxed mb-6">{{ dev.get('desc', '') }}</p>
                    <div class="mt-auto pt-4 border-t border-white/10 text-left">
                        <span class="text-[10px] uppercase font-bold opacity-40 block mb-2">Навички</span>
                        <div class="text-xs font-mono text-gray-300">{{ dev.get('skills', 'Soft Skills') }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            <!-- Двигун роботи -->
            <a href="https://lovespace.ua/uk/products/vibrator-satisfyer-love-me" target="_blank" class="process-link">
                <i class="fas fa-video"></i> <span>Робочий процес</span>
            </a>
        </section>

        <!-- Профіль -->
        {% if current_user %}
        <section id="tab-profile" class="tab-content hidden max-w-2xl mx-auto text-center">
            <div class="bg-white/10 p-12 rounded-[3rem] border border-white/20">
                <div class="relative inline-block mb-6">
                    <img src="{{ current_user.get('avatar', '') }}" class="w-32 h-32 rounded-full border-4 border-white shadow-2xl">
                    <button onclick="toggleAvatarEdit(true)" class="absolute bottom-0 right-0 bg-red-700 p-2 rounded-full border-2 border-white"><i class="fas fa-camera"></i></button>
                </div>
                <h2 class="text-4xl font-black uppercase">{{ current_user.get('fullname', '') }}</h2>
                <p class="text-red-500 font-bold mb-8 uppercase tracking-widest">{{ current_user.get('role', '') }}</p>
                <div id="avatar-edit" class="hidden mt-8">
                    <form action="/api/update_avatar" method="POST" class="flex flex-col space-y-3">
                        <input type="url" name="url" placeholder="URL нової аватарки" class="p-3 rounded-xl bg-white text-black font-bold outline-none" required>
                        <button class="bg-white text-black py-2 rounded-xl font-black uppercase text-xs">Оновити</button>
                    </form>
                </div>
            </div>
        </section>
        {% endif %}
    </main>

    <!-- Модалки -->
    <div id="student-modal" class="hidden fixed inset-0 bg-black/95 z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-10 rounded-[3rem] w-full max-w-lg relative text-center">
            <button onclick="closeStudentModal()" class="absolute top-6 right-6 text-3xl hover:text-red-600 transition">&times;</button>
            <img id="sm-avatar" src="" class="w-24 h-24 rounded-full mx-auto mb-6 border-4 border-red-800 shadow-xl">
            <h2 id="sm-name" class="text-3xl font-black uppercase mb-1">...</h2>
            <div class="bg-gray-100 p-8 rounded-3xl text-left grid grid-cols-2 gap-4 text-sm mt-8 border border-gray-200">
                <div><span class="opacity-40 uppercase font-bold text-[10px]">Email</span><br><strong id="sm-email"></strong></div>
                <div><span class="opacity-40 uppercase font-bold text-[10px]">Курс</span><br><strong id="sm-course"></strong></div>
                <div><span class="opacity-40 uppercase font-bold text-[10px]">Спеціальність</span><br><strong id="sm-spec"></strong></div>
                <div><span class="opacity-40 uppercase font-bold text-[10px]">Заклад</span><br><strong id="sm-inst"></strong></div>
            </div>
        </div>
    </div>

    <div id="login-modal" class="hidden fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-10 rounded-3xl w-full max-w-sm relative shadow-2xl">
            <button onclick="toggleLogin(false)" class="absolute top-4 right-4 text-2xl hover:text-red-600 transition">&times;</button>
            <h2 class="text-3xl font-black mb-8 text-center uppercase tracking-tighter">ВХІД УКД</h2>
            <form action="/login" method="POST" class="space-y-4">
                <input type="email" name="email" placeholder="Email" required class="w-full border-2 p-4 rounded-xl font-bold outline-none">
                <input type="password" name="pass" placeholder="Пароль" required class="w-full border-2 p-4 rounded-xl font-bold outline-none">
                <button class="w-full bg-black text-white py-4 rounded-xl font-black uppercase">Увійти</button>
            </form>
        </div>
    </div>

    <script>
        function showTab(id) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            const tab = document.getElementById('tab-' + id);
            if(tab) tab.classList.remove('hidden');
            const btn = document.getElementById('btn-' + id);
            if(btn) btn.classList.add('active');
        }
        function toggleLogin(s) { document.getElementById('login-modal').classList.toggle('hidden', !s); }
        function toggleAvatarEdit(s) { document.getElementById('avatar-edit').classList.toggle('hidden', !s); }
        function toggleRegFields(role) { document.getElementById('reg-teacher-fields').classList.toggle('hidden', role !== 'TEACHER'); }
        function showStudentProfile(u) {
            document.getElementById('sm-avatar').src = u.avatar || '';
            document.getElementById('sm-name').innerText = u.fullname || '...';
            document.getElementById('sm-email').innerText = u.email || '...';
            document.getElementById('sm-course').innerText = u.course || '1';
            document.getElementById('sm-spec').innerText = u.specialty || 'ІПЗ';
            document.getElementById('sm-inst').innerText = u.institution || 'Університет';
            document.getElementById('student-modal').classList.remove('hidden');
        }
        function closeStudentModal() { document.getElementById('student-modal').classList.add('hidden'); }
        function syncSheets() {
            const btn = document.getElementById('sync-btn');
            btn.innerText = "Синхронізація...";
            btn.disabled = true;
            fetch('/api/sync_sheets').then(r => r.json()).then(d => { alert(d.message); location.reload(); }).catch(e => { alert("Помилка"); btn.innerText = "Синхронізувати"; btn.disabled = false; });
        }
        function resolveN(id) { fetch('/api/resolve/' + id).then(r => r.json()).then(d => { if(d.success) location.reload(); }); }
        function runSystem() {
            const months = ["Січня", "Лютого", "Березня", "Квітня", "Травня", "Червня", "Липня", "Серпня", "Вересня", "Жовтня", "Листопада", "Грудня"];
            document.querySelectorAll('[data-deadline]').forEach(el => {
                const val = el.dataset.deadline;
                if(!val) return;
                const d = new Date(val);
                if(!isNaN(d)) el.innerText = `${d.getDate()} ${months[d.getMonth()]} о ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
            });
            setInterval(() => {
                document.querySelectorAll('[data-timer-until]').forEach(badge => {
                    const untilVal = badge.dataset.timerUntil;
                    if(!untilVal) return;
                    const until = new Date(untilVal).getTime();
                    const diff = Math.floor((until - new Date().getTime()) / 1000);
                    if (diff > 0) {
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        badge.innerText = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                    } else { badge.innerText = "ЧАС ВИЙШОВ"; badge.style.background = "black"; }
                });
            }, 1000);
        }
        runSystem();
        const urlParams = new URLSearchParams(window.location.search);
        if(urlParams.has('tab')) showTab(urlParams.get('tab'));
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    db = load_data()
    user_absences = []
    curr = None
    if 'user_id' in session:
        curr = next((u for u in db['users'] if u.get('id') == session['user_id']), None)
        for a in db.get('absences', []):
            if session.get('role') in ['ADMIN', 'TEACHER'] or a.get('student_id') == session.get('user_id'):
                sub = next((s for s in db['subjects'] if s.get('id') == a.get('subject_id')), None)
                student = next((u for u in db['users'] if u.get('id') == a.get('student_id')), None)
                if sub and student:
                    t_id = sub.get('teacher_id')
                    teacher = next((u for u in db['users'] if u['id'] == t_id), None)
                    user_absences.append({
                        "id": a.get('id'),
                        "subject_name": sub.get('name', '???'),
                        "teacher_name": teacher.get('fullname', 'Викладач') if teacher else "Викладач",
                        "student_name": student.get('fullname', 'Студент'),
                        "student": student,
                        "deadline": a.get('deadline', '')
                    })
    return render_template_string(HTML_TEMPLATE, total_absences=len(db.get('absences', [])), total_subjects=len(db.get('subjects', [])), user_absences=user_absences, all_users=db['users'], all_subjects=db['subjects'], creators=db.get('creators', []), current_user=curr)

@app.route('/login', methods=['POST'])
def login():
    db = load_data()
    email, p = request.form.get('email'), request.form.get('pass')
    user = next((x for x in db['users'] if x.get('email') == email and x.get('password') == p), None)
    if user: session.update({"user_id": user['id'], "role": user['role'], "username": user.get('username')})
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/sync_sheets')
def sync_sheets():
    if session.get('role') not in ['ADMIN', 'TEACHER']: return jsonify({"success": False, "message": "Відмовлено"})
    success, message = sync_data_from_sheets()
    return jsonify({"success": success, "message": message})

@app.route('/api/resolve/<int:abs_id>')
def resolve(abs_id):
    if session.get('role') not in ['ADMIN', 'TEACHER']: return jsonify({"success": False}), 403
    db = load_data()
    db['absences'] = [a for a in db['absences'] if a.get('id') != abs_id]
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/add_user', methods=['POST'])
def add_user():
    if session.get('role') not in ['ADMIN', 'TEACHER']: return redirect('/')
    db = load_data()
    new_user = {
        "id": len(db['users']) + 1,
        "username": request.form.get('username'),
        "password": request.form.get('password'),
        "fullname": request.form.get('fullname'),
        "email": request.form.get('email'),
        "role": request.form.get('role', 'STUDENT'),
        "avatar": "https://cdn-icons-png.flaticon.com/512/354/354637.png",
        "course": "1", "specialty": "ІПЗ", "institution": "Університет",
        "room": request.form.get('room', '')
    }
    db['users'].append(new_user)
    save_data(db)
    return redirect('/?tab=admin')

@app.route('/api/add_absence', methods=['POST'])
def add_absence():
    if session.get('role') not in ['ADMIN', 'TEACHER']: return redirect('/')
    db = load_data()
    db['absences'].append({"id": len(db['absences']) + 1, "student_id": int(request.form.get('student_id')), "subject_id": int(request.form.get('subject_id')), "deadline": request.form.get('deadline'), "status": "active"})
    save_data(db)
    return redirect('/?tab=timers')

@app.route('/api/update_avatar', methods=['POST'])
def update_avatar():
    if 'user_id' not in session: return redirect('/')
    db = load_data()
    for u in db['users']:
        if u['id'] == session['user_id']: u['avatar'] = request.form.get('url'); break
    save_data(db)
    return redirect('/?tab=profile')

if __name__ == '__main__':
    app.run(debug=True)
import json
import os
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = 'ukd_secret_key_6000_v3'

# Файли бази даних
DATABASE_FILE = 'database.json'

# Початкові дані з повною структурою
DEFAULT_DATA = {
    "users": [
        {
            "id": 1, 
            "username": "admin", 
            "password": "123", 
            "role": "ADMIN", 
            "fullname": "Адміністратор", 
            "email": "admin@ukd.edu.ua", 
            "avatar": "https://cdn-icons-png.flaticon.com/512/6024/6024190.png",
            "room": "Деканат"
        },
        {
            "id": 2, 
            "username": "teacher", 
            "password": "123", 
            "role": "TEACHER", 
            "fullname": "проф. Іваненко О.М.", 
            "email": "ivanenko@ukd.edu.ua", 
            "avatar": "https://cdn-icons-png.flaticon.com/512/1995/1995531.png", 
            "room": "402"
        },
        {
            "id": 3, 
            "username": "student", 
            "password": "123", 
            "role": "STUDENT", 
            "fullname": "Іван Студент", 
            "email": "student@ukd.edu.ua", 
            "avatar": "https://cdn-icons-png.flaticon.com/512/354/354637.png"
        }
    ],
    "subjects": [
        {"id": 1, "name": "Вища математика", "teacher_id": 2},
        {"id": 2, "name": "Основи програмування", "teacher_id": 2}
    ],
    "absences": [
        {"id": 1, "student_id": 3, "subject_id": 1, "deadline": "2026-12-31T23:59", "status": "active"}
    ],
    "creators": [
        {
            "name": "Олександр", 
            "role": "Backend Lead", 
            "desc": "Архітектор серверної частини. Відповідає за безпеку даних та міграції бази даних.", 
            "skills": "Python, Flask, JSON Security"
        },
        {
            "name": "Марія", 
            "role": "UI/UX Designer", 
            "desc": "Стиліст інтерфейсу. Створила темно-червону гамму університету УКД.", 
            "skills": "Figma, Tailwind, Color Theory"
        },
        {
            "name": "Дмитро", 
            "role": "Frontend Dev", 
            "desc": "Майстер інтерактивності. Розробив систему таймерів та акордеонів.", 
            "skills": "JS, DOM API, Animations"
        },
        {
            "name": "Олена", 
            "role": "QA Engineer", 
            "desc": "Головний тестувальник. Знайшла та допомогла виправити критичні помилки KeyError.", 
            "skills": "Manual Testing, Debugging"
        },
        {
            "name": "Артем", 
            "role": "Data Analyst", 
            "desc": "Займається структуруванням інформації про предмети та кабінети.", 
            "skills": "Data Mining, Excel Integration"
        }
    ]
}

def load_data():
    if not os.path.exists(DATABASE_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # --- Міграція даних для запобігання KeyError ---
            for u in data.get('users', []):
                if 'email' not in u: u['email'] = f"{u['username']}@ukd.edu.ua"
                if 'avatar' not in u: u['avatar'] = "https://cdn-icons-png.flaticon.com/512/354/354637.png"
                if 'room' not in u: u['room'] = "Не вказано"
            
            for s in data.get('subjects', []):
                if 'teacher_id' not in s: s['teacher_id'] = 1
            
            for a in data.get('absences', []):
                if 'deadline' not in a: a['deadline'] = "2024-01-01T00:00"
                if 'student_id' not in a: a['student_id'] = 0
            
            if 'creators' not in data: data['creators'] = DEFAULT_DATA['creators']
            
            return data
    except Exception as e:
        print(f"Error loading database: {e}")
        return DEFAULT_DATA

def save_data(data):
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
        .card { background: white; color: black; border-left: 8px solid black; transition: all 0.3s ease; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .nav-btn.active { border-bottom: 2px solid white; font-weight: bold; }
        .admin-section { background: rgba(255, 255, 255, 0.05); border-radius: 20px; padding: 25px; border: 1px solid rgba(255,255,255,0.1); }
        
        /* Accordion Logic */
        .accordion-item { border-bottom: 1px solid rgba(255,255,255,0.1); }
        .accordion-content { max-height: 0; overflow: hidden; transition: all 0.5s cubic-bezier(0,1,0,1); }
        .accordion-item.active .accordion-content { max-height: 1000px; padding-bottom: 20px; transition: all 0.5s cubic-bezier(1,0,1,0); }
        .chevron { transition: transform 0.3s; }
        .accordion-item.active .chevron { transform: rotate(180deg); }
        
        .timer-badge { background: var(--ukd-bright); color: white; padding: 5px 15px; border-radius: 50px; font-weight: 800; font-family: monospace; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Навігація -->
    <nav class="bg-black p-4 sticky top-0 z-50 shadow-2xl">
        <div class="container mx-auto flex justify-between items-center">
            <div class="flex items-center space-x-3 cursor-pointer" onclick="showTab('main')">
                <div class="bg-red-700 p-2 rounded-xl shadow-lg shadow-red-900/40">
                    <i class="fas fa-hourglass-half text-white text-xl"></i>
                </div>
                <span class="text-xl font-black uppercase tracking-tighter">Таймер но 6 тисяч</span>
            </div>
            
            <div class="hidden md:flex space-x-8 items-center">
                <button onclick="showTab('main')" id="btn-main" class="nav-btn active px-2 py-1">Головна</button>
                {% if session.get('role') %}
                    <button onclick="showTab('timers')" id="btn-timers" class="nav-btn px-2 py-1">Мої Н</button>
                    {% if session.get('role') in ['ADMIN', 'TEACHER'] %}
                        <button onclick="showTab('admin')" id="btn-admin" class="nav-btn text-yellow-400 px-2 py-1">Керування</button>
                    {% endif %}
                    <button onclick="showTab('profile')" id="btn-profile" class="nav-btn px-2 py-1">Профіль</button>
                {% endif %}
                <button onclick="showTab('creators')" id="btn-creators" class="nav-btn px-2 py-1">Творці</button>
                
                {% if session.get('username') %}
                    <a href="/logout" class="text-red-500 hover:text-white transition"><i class="fas fa-sign-out-alt text-xl"></i></a>
                {% else %}
                    <button onclick="toggleLogin(true)" class="bg-white text-black px-5 py-1.5 rounded-full font-bold hover:bg-red-200 transition">Вхід</button>
                {% endif %}
            </div>
        </div>
    </nav>

    <main class="container mx-auto px-4 py-12 flex-grow">
        
        <!-- Головна сторінка -->
        <section id="tab-main" class="tab-content max-w-4xl mx-auto">
            <div class="text-center mb-16">
                <h1 class="text-6xl font-black mb-6 tracking-tighter uppercase">УКД ПЛАТФОРМА</h1>
                <p class="text-xl opacity-60">Прозора система моніторингу академічних успіхів</p>
            </div>

            <div class="space-y-6">
                <div class="accordion-item bg-black/20 rounded-2xl p-2 border border-white/5">
                    <div class="flex justify-between items-center p-6 cursor-pointer" onclick="this.parentElement.classList.toggle('active')">
                        <h3 class="text-2xl font-bold flex items-center"><i class="fas fa-info-circle mr-4 text-red-500"></i> Про проект</h3>
                        <i class="fas fa-chevron-down chevron"></i>
                    </div>
                    <div class="accordion-content px-6 text-lg opacity-80 leading-relaxed">
                        Сайт створено для студентів Університету Короля Данила. Ми прагнемо зробити процес відпрацювань зрозумілим та автоматизованим. Ви більше не забудете про дедлайни, адже таймер працює 24/7.
                    </div>
                </div>

                <div class="accordion-item bg-black/20 rounded-2xl p-2 border border-white/5">
                    <div class="flex justify-between items-center p-6 cursor-pointer" onclick="this.parentElement.classList.toggle('active')">
                        <h3 class="text-2xl font-bold flex items-center"><i class="fas fa-university mr-4 text-red-500"></i> Правила університету</h3>
                        <i class="fas fa-chevron-down chevron"></i>
                    </div>
                    <div class="accordion-content px-6 text-lg opacity-80 leading-relaxed">
                        <ul class="list-disc ml-6 space-y-3">
                            <li>Відпрацювання "Н" повинно відбутися протягом 2-х тижнів з моменту пропуску.</li>
                            <li>Викладач має право призначити додаткові завдання залежно від складності теми.</li>
                            <li>Інформація про кабінет та пошту викладача доступна у вкладці "Мої Н".</li>
                        </ul>
                    </div>
                </div>

                <div class="accordion-item bg-black/20 rounded-2xl p-2 border border-white/5">
                    <div class="flex justify-between items-center p-6 cursor-pointer" onclick="this.parentElement.classList.toggle('active')">
                        <h3 class="text-2xl font-bold flex items-center"><i class="fas fa-play-circle mr-4 text-red-500"></i> Навчальний гайд</h3>
                        <i class="fas fa-chevron-down chevron"></i>
                    </div>
                    <div class="accordion-content px-6 text-center py-6">
                        <p class="mb-6 opacity-80">Перегляньте коротке відео про те, як працювати з інтерфейсом:</p>
                        <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ" target="_blank" class="inline-flex items-center space-x-3 bg-red-600 px-8 py-3 rounded-full font-bold hover:bg-white hover:text-red-700 transition">
                            <i class="fab fa-youtube text-2xl"></i>
                            <span>ВІДКРИТИ ВІДЕО-ГАЙД</span>
                        </a>
                    </div>
                </div>
            </div>
        </section>

        <!-- Таймери -->
        <section id="tab-timers" class="tab-content hidden">
            <h2 class="text-4xl font-black mb-10 border-b border-white/10 pb-5 uppercase">Ваші заборгованості</h2>
            <div class="grid gap-6">
                {% for item in user_absences %}
                <div class="card p-6 rounded-3xl flex flex-col md:flex-row justify-between items-center shadow-lg" id="absence-{{ item.id }}">
                    <div class="flex items-center space-x-6 text-left w-full">
                        <div class="bg-red-800 text-white min-w-[4rem] h-16 rounded-2xl flex items-center justify-center font-black text-3xl">H</div>
                        <div>
                            <h4 class="text-2xl font-black uppercase leading-none mb-1">{{ item.subject_name }}</h4>
                            <p class="text-gray-500 font-bold">{{ item.teacher_name }}</p>
                            <p class="text-sm text-red-700 mt-1">
                                <i class="fas fa-envelope mr-1"></i> {{ item.teacher_email }} | 
                                <i class="fas fa-door-open mr-1 ml-2"></i> Кабінет: {{ item.room }}
                            </p>
                            {% if session['role'] in ['ADMIN', 'TEACHER'] %}
                                <div class="mt-2 text-xs bg-gray-100 p-2 rounded-lg inline-block border border-gray-200">
                                    <span class="text-black font-bold uppercase">Студент:</span> {{ item.student_name }}
                                </div>
                            {% endif %}
                        </div>
                    </div>
                    <div class="flex flex-col md:items-end mt-6 md:mt-0 space-y-3 w-full md:w-auto">
                        <div class="timer-badge text-xl shadow-inner" data-until="{{ item.deadline }}">Розрахунок...</div>
                        <button onclick="resolveAbsence({{ item.id }})" class="w-full md:w-auto bg-black text-white px-6 py-2 rounded-xl hover:bg-green-700 transition font-black uppercase text-xs tracking-widest">
                            ВІДПРАЦЬОВАНО
                        </button>
                    </div>
                </div>
                {% else %}
                <div class="text-center py-24 bg-black/10 rounded-3xl border border-white/5 opacity-40">
                    <i class="fas fa-check-double text-6xl mb-4"></i>
                    <p class="text-xl">Заборгованостей не знайдено. Ви молодець!</p>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- Керування -->
        <section id="tab-admin" class="tab-content hidden">
            <h2 class="text-4xl font-black mb-10 uppercase">Панель адміністратора</h2>
            <div class="grid lg:grid-cols-2 gap-10">
                <!-- Реєстрація -->
                <div class="admin-section">
                    <h3 class="text-2xl font-bold mb-6 flex items-center text-green-400">
                        <i class="fas fa-user-plus mr-3"></i> Новий користувач
                    </h3>
                    <div class="flex space-x-2 mb-6 p-1 bg-white/10 rounded-xl">
                        <button onclick="switchRole('STUDENT')" id="role-s" class="flex-grow py-2 rounded-lg bg-white text-black font-bold transition">Студент</button>
                        <button onclick="switchRole('TEACHER')" id="role-t" class="flex-grow py-2 rounded-lg text-white hover:bg-white/5 transition">Викладач</button>
                    </div>
                    <form action="/api/add_user" method="POST" class="space-y-4">
                        <input type="hidden" name="role" id="role-val" value="STUDENT">
                        <input type="text" name="fullname" placeholder="ПІБ Користувача" required class="w-full p-3 rounded-xl bg-white text-black font-bold">
                        <input type="email" name="email" placeholder="Електронна пошта (напр. user@ukd.edu.ua)" required class="w-full p-3 rounded-xl bg-white text-black font-bold">
                        
                        <div id="teacher-fields" class="hidden">
                            <input type="text" name="room" placeholder="Номер кабінету" class="w-full p-3 rounded-xl bg-white text-black font-bold border-2 border-yellow-500">
                        </div>

                        <div class="flex space-x-3">
                            <input type="text" name="username" placeholder="Логін (для системних цілей)" required class="w-1/2 p-3 rounded-xl bg-white text-black font-bold">
                            <input type="text" name="password" placeholder="Пароль" required class="w-1/2 p-3 rounded-xl bg-white text-black font-bold">
                        </div>
                        <button type="submit" class="w-full bg-green-600 text-white font-black py-4 rounded-xl hover:bg-black transition uppercase tracking-widest">ЗАРЕЄСТРУВАТИ</button>
                    </form>
                </div>

                <!-- Виставлення Н -->
                <div class="admin-section">
                    <h3 class="text-2xl font-bold mb-6 flex items-center text-yellow-400">
                        <i class="fas fa-clock mr-3"></i> Виставити заборгованість
                    </h3>
                    <form action="/api/add_absence" method="POST" class="space-y-4">
                        <select name="student_id" class="w-full p-3 rounded-xl bg-white text-black font-bold outline-none" required>
                            <option value="" disabled selected>Оберіть студента</option>
                            {% for u in all_users if u.role == 'STUDENT' %}<option value="{{ u.id }}">{{ u.fullname }}</option>{% endfor %}
                        </select>
                        <select name="subject_id" class="w-full p-3 rounded-xl bg-white text-black font-bold outline-none" required>
                            <option value="" disabled selected>Оберіть предмет</option>
                            {% for s in all_subjects %}<option value="{{ s.id }}">{{ s.name }}</option>{% endfor %}
                        </select>
                        <div class="bg-black/20 p-4 rounded-xl border border-white/10">
                            <label class="text-xs uppercase font-black opacity-50 mb-2 block">Крайній термін відпрацювання:</label>
                            <input type="datetime-local" name="deadline" required class="w-full p-2 rounded bg-white text-black font-bold">
                        </div>
                        <button type="submit" class="w-full bg-yellow-500 text-black font-black py-4 rounded-xl hover:bg-black hover:text-white transition uppercase tracking-widest">ВИСТАВИТИ Н-КУ</button>
                    </form>
                </div>
            </div>
        </section>

        <!-- Творці -->
        <section id="tab-creators" class="tab-content hidden">
            <h2 class="text-4xl font-black text-center mb-12 uppercase tracking-tighter">Команда проекту</h2>
            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                {% for dev in creators %}
                <div class="bg-white/5 p-8 rounded-3xl border border-white/10 hover:border-red-500 transition-all group">
                    <div class="w-16 h-16 bg-red-800 rounded-2xl flex items-center justify-center font-black text-2xl mb-6 shadow-xl group-hover:scale-110 transition">{{ dev.name[0] }}</div>
                    <h3 class="text-2xl font-black mb-1">{{ dev.name }}</h3>
                    <p class="text-red-400 font-bold uppercase text-xs mb-4 tracking-widest">{{ dev.role }}</p>
                    <p class="text-sm opacity-60 mb-6 leading-relaxed">{{ dev.desc }}</p>
                    <div class="bg-black/30 p-4 rounded-xl border border-white/5">
                        <span class="text-[10px] uppercase font-black opacity-40 block mb-1">Ключові навички</span>
                        <p class="text-xs font-bold text-gray-300">{{ dev.skills }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- Профіль -->
        {% if current_user %}
        <section id="tab-profile" class="tab-content hidden max-w-xl mx-auto py-10">
            <div class="bg-white/10 p-12 rounded-[3rem] border border-white/20 text-center backdrop-blur-xl">
                <img src="{{ current_user.avatar }}" class="w-32 h-32 rounded-full mx-auto mb-6 border-4 border-white shadow-2xl">
                <h2 class="text-4xl font-black mb-1 uppercase tracking-tighter">{{ current_user.fullname }}</h2>
                <p class="text-red-500 font-black mb-8 uppercase text-sm tracking-widest">{{ current_user.role }}</p>
                <div class="text-left space-y-4 bg-black/40 p-8 rounded-3xl border border-white/5">
                    <p class="flex flex-col"><span class="text-[10px] uppercase font-black opacity-40">Email Адреса</span><span class="font-bold text-lg">{{ current_user.email }}</span></p>
                    <p class="flex flex-col"><span class="text-[10px] uppercase font-black opacity-40">Логін у системі</span><span class="font-bold text-lg">@{{ current_user.username }}</span></p>
                    {% if current_user.room %}<p class="flex flex-col"><span class="text-[10px] uppercase font-black opacity-40">Робочий кабінет</span><span class="font-bold text-lg text-yellow-400">{{ current_user.room }}</span></p>{% endif %}
                </div>
                <form action="/api/update_avatar" method="POST" class="mt-10">
                    <input type="url" name="url" placeholder="Вставте URL фото" class="w-full p-3 rounded-xl bg-white text-black font-bold text-sm mb-3 outline-none focus:ring-4 ring-red-500/30" required>
                    <button class="w-full bg-white text-black py-3 rounded-xl font-black uppercase tracking-widest text-xs hover:bg-red-200 transition">ОНОВИТИ АВАТАР</button>
                </form>
            </div>
        </section>
        {% endif %}
    </main>

    <!-- Модалка логіну -->
    <div id="login-modal" class="hidden fixed inset-0 bg-black/95 z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-10 rounded-3xl w-full max-w-sm relative shadow-[0_0_50px_rgba(255,0,0,0.2)]">
            <button onclick="toggleLogin(false)" class="absolute top-6 right-6 text-2xl hover:text-red-600 transition">&times;</button>
            <h2 class="text-3xl font-black mb-8 uppercase text-center tracking-tighter">УКД СЕРВІС</h2>
            <form action="/login" method="POST" class="space-y-5">
                <input type="email" name="email" placeholder="Електронна пошта" required class="w-full border-2 border-gray-100 p-4 rounded-xl font-bold outline-none focus:border-red-600 transition">
                <input type="password" name="pass" placeholder="Пароль" required class="w-full border-2 border-gray-100 p-4 rounded-xl font-bold outline-none focus:border-red-600 transition">
                <button class="w-full bg-black text-white py-4 rounded-xl font-black uppercase tracking-widest hover:bg-red-800 transition">УВІЙТИ</button>
            </form>
        </div>
    </div>

    <footer class="bg-black py-10 text-center opacity-30 border-t border-white/5">
        <p class="text-xs font-black uppercase tracking-[0.5em]">Університет Короля Данила © 2026</p>
    </footer>

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

        function switchRole(role) {
            document.getElementById('role-val').value = role;
            document.getElementById('teacher-fields').classList.toggle('hidden', role !== 'TEACHER');
            document.getElementById('role-s').className = role === 'STUDENT' ? "flex-grow py-2 rounded-lg bg-white text-black font-bold" : "flex-grow py-2 rounded-lg text-white hover:bg-white/5 transition";
            document.getElementById('role-t').className = role === 'TEACHER' ? "flex-grow py-2 rounded-lg bg-white text-black font-bold" : "flex-grow py-2 rounded-lg text-white hover:bg-white/5 transition";
        }

        function updateTimers() {
            document.querySelectorAll('.timer-badge').forEach(badge => {
                const until = new Date(badge.dataset.until).getTime();
                const now = new Date().getTime();
                const diff = Math.floor((until - now) / 1000);
                if (diff > 0) {
                    const h = Math.floor(diff / 3600);
                    const m = Math.floor((diff % 3600) / 60);
                    const s = diff % 60;
                    badge.innerText = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                } else {
                    badge.innerText = "ТЕРМІН ВИЙШОВ";
                    badge.style.background = "black";
                }
            });
        }
        setInterval(updateTimers, 1000);

        function resolveAbsence(id) {
            fetch('/api/resolve/' + id).then(() => {
                const el = document.getElementById('absence-' + id);
                el.style.opacity = '0';
                setTimeout(() => location.reload(), 300);
            });
        }

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
        curr = next((u for u in db['users'] if u['id'] == session['user_id']), None)
        for a in db.get('absences', []):
            if session['role'] in ['ADMIN', 'TEACHER'] or a.get('student_id') == session['user_id']:
                sub = next((s for s in db['subjects'] if s['id'] == a.get('subject_id')), None)
                if sub:
                    t_id = sub.get('teacher_id')
                    teacher = next((u for u in db['users'] if u['id'] == t_id), None)
                    student = next((u for u in db['users'] if u['id'] == a.get('student_id')), None)
                    user_absences.append({
                        "id": a.get('id'),
                        "subject_name": sub.get('name', 'Невідомо'),
                        "teacher_name": teacher['fullname'] if teacher else "Викладач",
                        "teacher_email": teacher.get('email', '-') if teacher else "-",
                        "room": teacher.get('room', '???') if teacher else "???",
                        "student_name": student['fullname'] if student else "Студент",
                        "deadline": a.get('deadline', '2024-01-01T00:00')
                    })

    return render_template_string(HTML_TEMPLATE, 
                                  total_absences=len(db.get('absences', [])),
                                  total_subjects=len(db.get('subjects', [])),
                                  user_absences=user_absences,
                                  all_users=db['users'],
                                  all_subjects=db['subjects'],
                                  creators=db.get('creators', []),
                                  current_user=curr)

@app.route('/login', methods=['POST'])
def login():
    db = load_data()
    email, p = request.form.get('email'), request.form.get('pass')
    # Тепер шукаємо користувача за поштою
    user = next((x for x in db['users'] if x['email'] == email and x['password'] == p), None)
    if user:
        session.update({"user_id": user['id'], "role": user['role'], "username": user['username']})
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

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
        "role": request.form.get('role'),
        "avatar": "https://cdn-icons-png.flaticon.com/512/354/354637.png"
    }
    if new_user['role'] == 'TEACHER':
        new_user['room'] = request.form.get('room', '???')
    db['users'].append(new_user)
    save_data(db)
    return redirect('/?tab=admin')

@app.route('/api/add_absence', methods=['POST'])
def add_absence():
    if session.get('role') not in ['ADMIN', 'TEACHER']: return redirect('/')
    db = load_data()
    db['absences'].append({
        "id": len(db['absences']) + 1,
        "student_id": int(request.form.get('student_id')),
        "subject_id": int(request.form.get('subject_id')),
        "deadline": request.form.get('deadline'),
        "status": "active"
    })
    save_data(db)
    return redirect('/?tab=timers')

@app.route('/api/resolve/<int:abs_id>')
def resolve(abs_id):
    db = load_data()
    db['absences'] = [a for a in db['absences'] if a.get('id') != abs_id]
    save_data(db)
    return jsonify({"success": True})

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
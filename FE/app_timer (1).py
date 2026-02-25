import sqlite3
import os
from flask import Flask, render_template_string, request, session, redirect, g, flash
from datetime import datetime

# Налаштування додатка
app = Flask(__name__)
app.secret_key = 'ukd_recruitment_secret_key_v5'
DATABASE = 'ukd_database.db'

# --- РОБОТА З БАЗОЮ ДАНИХ (SQLite) ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 1. Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL DEFAULT 'STUDENT',
                status TEXT DEFAULT 'active'
            )
        ''')

        # 2. Students
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                patronymic TEXT,
                course TEXT,
                specialty TEXT,
                skills TEXT,
                links TEXT,
                contact_info TEXT,
                rating INTEGER DEFAULT 0,
                avatar TEXT DEFAULT 'https://cdn-icons-png.flaticon.com/512/354/354637.png',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Міграції для студентів (якщо БД вже існує)
        for col in ['patronymic', 'course', 'contact_info']:
            try: cursor.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError: pass
            
        try: cursor.execute("ALTER TABLE students ADD COLUMN rating INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass

        # 3. Companies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                company_name TEXT,
                description TEXT,
                avatar TEXT DEFAULT 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png',
                position TEXT,
                contact_info TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Міграції для компаній
        for col in ['avatar', 'position', 'contact_info']:
            try: cursor.execute(f"ALTER TABLE companies ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError: pass
            
        try: cursor.execute("ALTER TABLE companies ALTER COLUMN avatar SET DEFAULT 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png'")
        except sqlite3.OperationalError: pass

        # 4. Admins
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                admin_level INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 5. Invitations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                company_id INTEGER,
                user_id INTEGER, 
                message TEXT,
                status TEXT DEFAULT 'pending',
                flagged BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id),
                FOREIGN KEY (company_id) REFERENCES companies (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        try: cursor.execute("ALTER TABLE invitations ADD COLUMN flagged BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        except sqlite3.OperationalError: pass
            
        db.commit()
        
        # Admin Default
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                           ('admin', '123', 'admin@ukd.edu.ua', 'ADMIN'))
            admin_user_id = cursor.lastrowid
            cursor.execute("INSERT INTO admins (user_id, admin_level) VALUES (?, ?)", (admin_user_id, 10))
            db.commit()

# --- HTML ШАБЛОН ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>УКД Recruitment</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --ukd-red: #4a0404; --ukd-bright: #8b0000; }
        body {
    background-image: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), 
                      url('https://ukd.edu.ua/sites/default/files/styles/16/public/2024-10/DSC_3783.jpg?h=295b0d92&itok=mx-I0n3V');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    background-repeat: no-repeat;
}
  .card { background: white; color: black; border-left: 8px solid black; transition: 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
.nav-btn {
    position: relative;
    color: rgba(255, 255, 255, 0.7) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    padding: 8px 16px !important;
    border-radius: 12px;
    overflow: hidden;
}

/* Ефект при наведенні */
.nav-btn:hover {
    color: #fff !important;
    background: rgba(255, 255, 255, 0.1);
    transform: translateY(-2px); /* Кнопка трохи підстрибує */
}

/* Динамічна лінія під кнопкою */
.nav-btn::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 50%;
    width: 0;
    height: 2px;
    background: #ff4d4d; /* Твій фірмовий червоний */
    transition: all 0.3s ease;
    transform: translateX(-50%);
}

.nav-btn:hover::after {
    width: 70%; /* Лінія розширюється при наведенні */
}

/* Стиль для активної кнопки */
.nav-btn.active {
    color: #fff !important;
    background: rgba(255, 77, 77, 0.15); /* Легкий червоний відблиск */
    font-weight: 700 !important;
}

.nav-btn.active::after {
    width: 80%;
    background: #ff4d4d;
}
        input, select, textarea { border: 2px solid #ddd; transition: 0.3s; color: black; }
        input:focus, select:focus, textarea:focus { border-color: var(--ukd-bright); outline: none; }
        .modal-bg { background: rgba(0,0,0,0.9); }
        .landing-hero { background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url('https://yt3.googleusercontent.com/ytc/AIdro_k624OQvH_3vjA4H8U1fQvX5Q5x5x5x5x5x5x5x5=s900-c-k-c0x00ffffff-no-rj'); background-size: cover; background-position: center; }
        .table-wrapper { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Навігація -->
 <nav class="p-4 sticky top-0 z-50 shadow-2xl" style="background-color: #AC0632 !important; border-bottom: 2px solid rgba(255,255,255,0.1);">
    <div class="container mx-auto flex items-center justify-between">
        
        <div class="flex items-center space-x-3 cursor-pointer shrink-0" onclick="window.location.href='/'">
            <div class="bg-white p-2 rounded-lg flex items-center justify-center" style="width: 38px; height: 38px;">
                <i class="fas fa-graduation-cap" style="color: #AC0632;"></i>
            </div>
            <span class="text-xl font-black uppercase tracking-tighter text-white">УКД TALENT</span>
        </div>

        <div class="flex items-center ml-auto">
            {% if session.get('user_id') %}
                <div class="hidden md:flex items-center space-x-1">
                    <a href="/?tab=home" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'home' else '' }}">
                        <i class="fas fa-home mr-2"></i> Головна
                    </a>
                    <a href="/?tab=ranking" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'ranking' else '' }}">
                        <i class="fas fa-list-ol mr-2"></i> Рейтинг
                    </a>
                    
                    {% if session.get('role') == 'ADMIN' %}
                        <a href="/?tab=invitations" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'invitations' else '' }}">
                            <i class="fas fa-shield-alt mr-2"></i> Адмін Панель
                        </a>
                        <a href="/?tab=users" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'users' else '' }}">
                            <i class="fas fa-users mr-2"></i> Користувачі
                        </a>
                    {% endif %}

                    {% if session.get('role') == 'COMPANY' %}
                         <a href="/?tab=invitations" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'invitations' else '' }}">
                            <i class="fas fa-paper-plane mr-2"></i> Мої Запити
                        </a>
                    {% endif %}
                    
                    {% if session.get('role') == 'STUDENT' %}
                         <a href="/?tab=invitations" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'invitations' else '' }}">
                            <i class="fas fa-inbox mr-2"></i> Мої Запрошення 
                            {% if pending_count > 0 %}
                            <span class="bg-white text-[#AC0632] text-[10px] px-1.5 py-0.5 rounded-full ml-1 font-black animate-pulse">{{ pending_count }}</span>
                            {% endif %}
                        </a>
                    {% endif %}

                    <a href="/?tab=profile" class="px-3 py-2 text-white font-bold rounded-xl transition-all hover:bg-white/20 flex items-center {{ 'bg-white/20' if active_tab == 'profile' else '' }}">
                        <i class="fas fa-user-circle mr-2"></i> Мій Профіль
                    </a>
                </div>

                <div class="flex items-center space-x-3 ml-4 pl-4 border-l border-white/20">
                    <div class="text-right hidden sm:block">
                        <div class="text-[10px] text-white/70 uppercase font-black">{{ session.get('role') }}</div>
                        <div class="text-sm text-white font-bold leading-none">{{ session.get('username') }}</div>
                    </div>
                    <a href="/logout" class="bg-white/10 hover:bg-white/30 p-2 rounded-full text-white transition">
                        <i class="fas fa-sign-out-alt"></i>
                    </a>
                </div>

            {% else %}
                <div class="flex items-center space-x-2">
                     <button onclick="toggleModal('login-modal')" class="bg-white text-[#AC0632] px-5 py-1.5 rounded-xl font-bold hover:bg-gray-100 transition-all">Вхід</button>
                     <button onclick="toggleModal('register-modal')" class="border-2 border-white text-white px-5 py-1.5 rounded-xl font-bold hover:bg-white hover:text-[#AC0632] transition-all">Реєстрація</button>
                </div>
            {% endif %}
        </div>
    </div>
</nav>
        <!-- Мобільне меню -->
        {% if session.get('user_id') %}
        <div class="md:hidden flex justify-around mt-4 border-t border-white/10 pt-2 overflow-x-auto gap-4">
            <a href="/?tab=home" class="text-sm whitespace-nowrap"><i class="fas fa-home"></i> Головна</a>
            <a href="/?tab=ranking" class="text-sm whitespace-nowrap"><i class="fas fa-list"></i> Рейтинг</a>
            <a href="/?tab=invitations" class="text-sm whitespace-nowrap"><i class="fas fa-inbox"></i> Inbox</a>
            {% if session.get('role') == 'ADMIN' %}<a href="/?tab=users" class="text-sm text-purple-400 whitespace-nowrap"><i class="fas fa-users"></i> Юзери</a>{% endif %}
            <a href="/?tab=profile" class="text-sm whitespace-nowrap"><i class="fas fa-user"></i> Профіль</a>
        </div>
        {% endif %}
    </nav>

    <main class="flex-grow relative">
        
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            <div class="container mx-auto px-4 mt-6">
                <div class="bg-green-600 text-white p-4 rounded-xl text-center font-bold shadow-lg animate-bounce">
                {{ messages[0] }}
                </div>
            </div>
          {% endif %}
        {% endwith %}

        <!-- ЛЕНДІНГ ПЕЙДЖ -->
        {% if not session.get('user_id') %}
        <div class="landing-hero min-h-[80vh] flex items-center justify-center text-center px-4">
            <div class="max-w-4xl">
                <h1 class="text-5xl md:text-7xl font-black uppercase mb-6 drop-shadow-lg">
                    Знайди Своє <span class="text-red-600">Майбутнє</span>
                </h1>
                <p class="text-xl md:text-2xl mb-8 font-light text-gray-200">
                    Платформа працевлаштування для студентів Університету Короля Данила.
                </p>
                <div class="flex flex-col md:flex-row justify-center gap-4">
                    <button onclick="toggleModal('register-modal')" class="bg-red-700 text-white px-8 py-4 rounded-full text-xl font-black uppercase hover:bg-red-800 transition shadow-xl transform hover:scale-105">
                        <i class="fas fa-rocket mr-2"></i> Стати Студентом
                    </button>
                    <button onclick="toggleModal('register-modal')" class="bg-white text-black px-8 py-4 rounded-full text-xl font-black uppercase hover:bg-gray-200 transition shadow-xl transform hover:scale-105">
                        <i class="fas fa-building mr-2"></i> Я Роботодавець
                    </button>
                </div>
            </div>
        </div>
        {% else %}
        
        <!-- ВНУТРІШНЯ ЧАСТИНА САЙТУ -->
        <div class="container mx-auto px-4 py-8">

            <!-- Вкладка: ГОЛОВНА (Home) -->
            {% if active_tab == 'home' %}
          <section class="max-w-6xl mx-auto text-center py-8">
                <h1 class="text-4xl md:text-6xl font-black uppercase mb-6 drop-shadow-lg tracking-tighter">
                    Ласкаво просимо до <span class="text-red-600">УКД Talent</span>
                </h1>
                <p class="text-lg md:text-xl mb-12 font-light text-gray-200 max-w-3xl mx-auto">
                    Платформа, що об'єднує найкращих студентів та провідних роботодавців для побудови успішного майбутнього.
                </p>

    </section>
                <div class="grid md:grid-cols-2 gap-8 text-left mb-16">
                    <div class="bg-white text-black p-8 rounded-3xl shadow-2xl border-l-8 border-red-700 transition hover:-translate-y-2">
                        <div class="text-red-700 text-4xl mb-4"><i class="fas fa-university"></i></div>
                        <h2 class="text-2xl font-black uppercase mb-4">Університет Короля Данила (УКД)</h2>
                        <p class="text-gray-700 font-medium leading-relaxed">
                            Університет Короля Данила — це сучасний заклад вищої освіти, який фокусується на практичних навичках, інноваціях та успішному працевлаштуванні випускників. Ми створюємо умови для розвитку талантів та тісно співпрацюємо з провідними компаніями, щоб наші студенти отримували реальний професійний досвід ще під час навчання.
                        </p>
                    </div>
                    
                    <div class="bg-white text-black p-8 rounded-3xl shadow-2xl border-l-8 border-black transition hover:-translate-y-2">
                        <div class="text-black text-4xl mb-4"><i class="fas fa-project-diagram"></i></div>
                        <h2 class="text-2xl font-black uppercase mb-4">Про Проєкт</h2>
                        <p class="text-gray-700 font-medium leading-relaxed">
                            <b>УКД Recruitment Platform</b> — це інноваційне рішення для спрощення процесу пошуку першої роботи для студентів та молодих спеціалістів. 
                            Студенти можуть створювати професійні портфоліо та вказувати свої навички, а компанії отримують зручний інструмент для пошуку кандидатів за спеціальностями, рейтингом та можуть надсилати їм прямі запрошення на роботу.
                        </p>
                    </div>
                </div>

                <div class="mt-8 border-t border-white/20 pt-12 pb-6">
                    <p class="text-gray-400 font-bold uppercase mb-6">Відкритий вихідний код проєкту на GitHub:</p>
                    <a href="https://github.com/YuraFedorets/TeamProject/tree/V3" target="_blank" class="inline-flex items-center gap-3 bg-gray-800 hover:bg-black text-white px-8 py-4 rounded-full font-black uppercase transition shadow-xl border border-gray-600 hover:border-gray-400 transform hover:scale-105">
                        <i class="fab fa-github text-3xl"></i> 
                        TeamProject / V3
                    </a>
                </div>
            </section>
            {% endif %}

            <!-- Вкладка: РЕЙТИНГ (Ranking) -->
            {% if active_tab == 'ranking' %}
            <section class="max-w-7xl mx-auto">
                <h2 class="text-4xl font-black mb-8 uppercase tracking-tighter border-b-4 border-white pb-2">
                    Рейтинг Студентів
                </h2>
                
                <!-- ПАНЕЛЬ ПОШУКУ ТА ФІЛЬТРІВ -->
                <form method="GET" action="/" class="bg-black/40 backdrop-blur-xl text-white p-6 rounded-[30px] border border-white/10 shadow-2xl mb-8 flex flex-wrap gap-4 items-end">
    <input type="hidden" name="tab" value="ranking">
    
    <div class="flex-grow min-w-[200px]">
        <label class="block text-xs font-black uppercase text-gray-400 mb-2 ml-1 tracking-widest">Пошук (Ім'я, Навички)</label>
        <div class="relative">
            <i class="fas fa-search absolute left-4 top-4 text-gray-500"></i>
            <input type="text" name="search" value="{{ current_filters.search }}" 
                   class="w-full pl-12 pr-4 py-3.5 rounded-2xl bg-white/5 border border-white/10 focus:border-red-500/50 focus:bg-white/10 transition-all outline-none text-white placeholder-gray-500" 
                   placeholder="Наприклад: Python, Дизайн...">
        </div>
    </div>
    
    <div class="w-full md:w-auto">
        <label class="block text-xs font-black uppercase text-gray-400 mb-2 ml-1 tracking-widest">Курс</label>
        <select name="course" class="w-full p-3.5 rounded-2xl bg-white/5 border border-white/10 focus:border-red-500/50 focus:bg-white/10 transition-all outline-none text-white appearance-none cursor-pointer">
            <option value="" class="bg-gray-900">Всі курси</option>
            {% for c in unique_courses %}
            <option value="{{ c }}" {% if current_filters.course == c|string %}selected{% endif %} class="bg-gray-900">{{ c }} курс</option>
            {% endfor %}
        </select>
    </div>

    <div class="w-full md:w-auto">
        <label class="block text-xs font-black uppercase text-gray-400 mb-2 ml-1 tracking-widest">Спеціальність</label>
        <select name="specialty" class="w-full p-3.5 rounded-2xl bg-white/5 border border-white/10 focus:border-red-500/50 focus:bg-white/10 transition-all outline-none text-white appearance-none cursor-pointer">
            <option value="" class="bg-gray-900">Всі спеціальності</option>
            {% for s in unique_specialties %}
            <option value="{{ s }}" {% if current_filters.specialty == s %}selected{% endif %} class="bg-gray-900">{{ s }}</option>
            {% endfor %}
        </select>
    </div>

    <div class="w-full md:w-auto">
        <label class="block text-xs font-black uppercase text-gray-400 mb-2 ml-1 tracking-widest">Сортування</label>
        <select name="sort" class="w-full p-3.5 rounded-2xl bg-white/5 border border-white/10 focus:border-red-500/50 focus:bg-white/10 transition-all outline-none text-white appearance-none cursor-pointer">
            <option value="desc" {% if current_filters.sort == 'desc' %}selected{% endif %} class="bg-gray-900">Рейтинг: Топ</option>
            <option value="asc" {% if current_filters.sort == 'asc' %}selected{% endif %} class="bg-gray-900">Рейтинг: Зростання</option>
        </select>
    </div>

    <div class="w-full md:w-auto flex gap-3">
        <button type="submit" class="bg-red-600 hover:bg-red-500 text-white px-8 py-3.5 rounded-2xl font-black uppercase tracking-widest shadow-lg shadow-red-900/20 transition-all active:scale-95 flex items-center gap-2">
            <i class="fas fa-filter"></i> Знайти
        </button>
        <a href="/?tab=ranking" class="bg-white/10 hover:bg-white/20 text-white px-5 py-3.5 rounded-2xl transition-all active:scale-95 flex items-center justify-center shadow-lg" title="Скинути">
            <i class="fas fa-sync-alt"></i>
        </a>
    </div>
</form>

                <!-- СПИСОК СТУДЕНТІВ -->
                {% if students %}
                <div class="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {% for std in students %}
                    <div class="card rounded-2xl p-6 relative group overflow-hidden flex flex-col h-full">
                        <!-- Зірочка рейтингу -->
                        <div class="absolute top-4 right-4 bg-yellow-400 text-black px-2 py-1 rounded-lg font-black text-sm shadow-md" title="Рейтинг студента">
                            <i class="fas fa-star text-xs"></i> {{ std.rating or 0 }}
                        </div>

                        <div class="flex items-center space-x-4 mb-4">
                            <img src="{{ std.avatar }}" class="w-16 h-16 rounded-full border-2 border-black object-cover bg-gray-200">
                            <div class="pr-8"> <!-- Відступ для зірочки -->
                                <h3 class="text-lg font-black uppercase leading-tight">{{ std.last_name }} {{ std.first_name }}</h3>
                                <p class="text-xs text-gray-500 font-bold mt-1">{{ std.course or '?' }} курс, {{ std.specialty or 'Спеціальність не вказана' }}</p>
                            </div>
                        </div>
                        
                        <div class="mb-4 flex-grow overflow-hidden">
                            <p class="text-[10px] font-bold uppercase text-gray-400 mb-1">Навички:</p>
                            <div class="flex flex-wrap gap-1 max-h-16 overflow-y-auto">
                                {% for skill in (std.skills or '').split(',') %}
                                    {% if skill.strip() %}
                                    <span class="bg-gray-200 text-black px-2 py-0.5 rounded text-[10px] font-bold">{{ skill.strip() }}</span>
                                    {% endif %}
                                {% endfor %}
                                {% if not std.skills %}<span class="text-gray-400 text-xs italic">Немає даних</span>{% endif %}
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-2 mt-auto pt-4 border-t border-gray-100">
                            <button onclick="openStudentProfile({{ std.user_id }})" class="bg-black text-white py-2 rounded-lg font-bold text-xs uppercase hover:bg-gray-800 transition">
                                <i class="fas fa-eye mr-1"></i> Профіль
                            </button>
                            
                            {% if session.get('role') in ['COMPANY', 'ADMIN'] %}
                            <button onclick="openInviteModal({{ std.id }}, '{{ std.first_name }}')" class="bg-red-700 text-white py-2 rounded-lg font-bold text-xs uppercase hover:bg-red-800 transition">
                                <i class="fas fa-handshake mr-1"></i> Найняти
                            </button>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                    <div class="text-center opacity-50 text-xl py-20 bg-black/20 rounded-2xl border border-white/10">
                        <i class="fas fa-search mb-4 text-4xl"></i><br>
                        Студентів за такими критеріями не знайдено.
                    </div>
                {% endif %}
            </section>
            {% endif %}

            <!-- Вкладка: СКРИНЬКА (Invitations) -->
           {% if active_tab == 'invitations' %}
<section class="max-w-6xl mx-auto px-4">
    
    <h2 class="text-3xl font-black mb-8 uppercase flex items-center gap-3 text-white">
        {% if session.get('role') == 'ADMIN' %} 
            <i class="fas fa-shield-alt text-white"></i> Панель Керування Заявками
        {% elif session.get('role') == 'STUDENT' %} 
            <i class="fas fa-inbox text-white"></i> Мої Запрошення
        {% else %} 
            <i class="fas fa-paper-plane text-white"></i> Надіслані Пропозиції 
        {% endif %}
    </h2>

    {% if session.get('role') == 'ADMIN' %}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white p-6 rounded-3xl shadow-xl border-l-8 border-[#AC0632]">
            <div class="text-gray-500 text-xs font-bold uppercase">Усього заявок</div>
            <div class="text-3xl font-black text-black">{{ invitations|length }}</div>
        </div>
        <div class="bg-white p-6 rounded-3xl shadow-xl border-l-8 border-green-500">
            <div class="text-gray-500 text-xs font-bold uppercase">Прийнято</div>
            <div class="text-3xl font-black text-black">
                {{ invitations|selectattr('status', 'equalto', 'accepted')|list|length }}
            </div>
        </div>
        <div class="bg-white p-6 rounded-3xl shadow-xl border-l-8 border-yellow-500">
            <div class="text-gray-500 text-xs font-bold uppercase">Очікують</div>
            <div class="text-3xl font-black text-black">
                {{ invitations|selectattr('status', 'equalto', 'pending')|list|length }}
            </div>
        </div>
        <div class="bg-white p-6 rounded-3xl shadow-xl border-l-8 border-red-600 animate-pulse">
            <div class="text-gray-500 text-xs font-bold uppercase">Потребують уваги</div>
            <div class="text-3xl font-black text-red-600">
                {{ invitations|selectattr('flagged', 'equalto', true)|list|length }}
            </div>
        </div>
    </div>
    {% endif %}

    <div class="bg-white text-black rounded-3xl shadow-2xl overflow-hidden border border-white/10">
        <div class="overflow-x-auto">
            <table class="w-full text-left min-w-max">
                <thead class="bg-gray-50 border-b border-gray-200">
                    <tr>
                        {% if session.get('role') != 'COMPANY' %}<th class="p-5 font-black uppercase text-xs text-gray-400">Від Кого</th>{% endif %}
                        {% if session.get('role') != 'STUDENT' %}<th class="p-5 font-black uppercase text-xs text-gray-400">Кому (Студент)</th>{% endif %}
                        <th class="p-5 font-black uppercase text-xs text-gray-400">Повідомлення</th>
                        <th class="p-5 font-black uppercase text-xs text-gray-400">Статус</th>
                        <th class="p-5 font-black uppercase text-xs text-gray-400 text-center">Дії</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for inv in invitations %}
                    <tr class="hover:bg-gray-50/80 transition-all {% if session.get('role') == 'ADMIN' and inv.flagged %}bg-red-50/50{% endif %}">
                        {% if session.get('role') != 'COMPANY' %}
                        <td class="p-5">
                            <div class="flex items-center space-x-3">
                                <img src="{{ inv.company_avatar or 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png' }}" class="w-10 h-10 rounded-xl object-cover shadow-sm">
                                <div>
                                    <span class="font-bold text-black block leading-tight">{{ inv.company_name or 'Невідома Компанія' }}</span>
                                    <span class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{{ inv.created_at }}</span>
                                </div>
                            </div>
                        </td>
                        {% endif %}
                        
                        {% if session.get('role') != 'STUDENT' %}
                        <td class="p-5">
                            <span class="font-bold text-gray-800">{{ inv.last_name }} {{ inv.first_name }}</span>
                        </td>
                        {% endif %}
                        
                        <td class="p-5">
                            <div class="text-sm text-gray-600 italic max-w-xs truncate" title="{{ inv.message }}">"{{ inv.message }}"</div>
                        </td>
                        
                        <td class="p-5">
                            {% if inv.status == 'pending' %}
                                <span class="bg-yellow-100 text-yellow-700 px-3 py-1 rounded-lg text-[10px] font-black uppercase">Очікує</span>
                            {% elif inv.status == 'accepted' %}
                                <span class="bg-green-100 text-green-700 px-3 py-1 rounded-lg text-[10px] font-black uppercase">Прийнято</span>
                            {% elif inv.status == 'rejected' %}
                                <span class="bg-red-100 text-red-700 px-3 py-1 rounded-lg text-[10px] font-black uppercase">Відхилено</span>
                            {% endif %}
                        </td>

                        <td class="p-5">
                            <div class="flex gap-2 justify-center">
                                {% if session.get('role') == 'STUDENT' and inv.status == 'pending' %}
                                    <form action="/respond_invite" method="POST" class="m-0">
                                        <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                        <input type="hidden" name="action" value="accept">
                                        <button class="bg-[#AC0632] text-white px-4 py-1.5 rounded-lg hover:bg-black transition-all text-xs font-bold uppercase">Так</button>
                                    </form>
                                    <form action="/respond_invite" method="POST" class="m-0">
                                        <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                        <input type="hidden" name="action" value="reject">
                                        <button class="border-2 border-gray-200 text-gray-500 px-4 py-1.5 rounded-lg hover:bg-gray-100 transition-all text-xs font-bold uppercase">Ні</button>
                                    </form>
                                {% endif %}
                                
                                {% if session.get('role') == 'ADMIN' %}
                                    <form action="/delete_invite" method="POST" class="m-0" onsubmit="return confirm('Видалити назавжди?');">
                                        <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                        <button class="w-9 h-9 flex items-center justify-center bg-gray-100 text-gray-400 hover:bg-[#AC0632] hover:text-white rounded-xl transition-all">
                                            <i class="fas fa-trash-alt text-sm"></i>
                                        </button>
                                    </form>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</section>
{% endif %}

            <!-- Вкладка: КОРИСТУВАЧІ (Admin Only) -->
                      {% if active_tab == 'users' and session.get('role') == 'ADMIN' %}
            <section class="w-full max-w-[95%] mx-auto">
                <h2 class="text-3xl font-black mb-8 uppercase flex items-center gap-3">
                    <i class="fas fa-users text-purple-400"></i> Управління Користувачами
                </h2>
                <div class="bg-white text-black rounded-3xl shadow-2xl overflow-hidden">
                    <div class="table-wrapper">
                        <table class="w-full text-left text-sm min-w-max">
                            <thead class="bg-gray-100 border-b-2 border-black">
                                <tr>
                                    <th class="p-4 font-black uppercase whitespace-nowrap">ID</th>
                                    <th class="p-4 font-black uppercase whitespace-nowrap">Email</th>
                                    <th class="p-4 font-black uppercase whitespace-nowrap">Посада / Роль</th>
                                    <th class="p-4 font-black uppercase min-w-[150px]">Company Name</th>
                                    <th class="p-4 font-black uppercase min-w-[200px]">ПІБ (Прізвище, Ім'я, По-батькові)</th>
                                    <th class="p-4 font-black uppercase min-w-[150px]">Курс і Спеціальність</th>
                                    <th class="p-4 font-black uppercase min-w-[250px]">Контактна інформація</th>
                                    <th class="p-4 font-black uppercase whitespace-nowrap">Статус</th>
                                    <th class="p-4 font-black uppercase whitespace-nowrap">Дії</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200">
                                {% for u in all_users %}
                                <tr class="hover:bg-gray-50 transition {% if u.status == 'blocked' %}bg-red-50 opacity-75{% endif %}">
                                    <td class="p-4 font-bold whitespace-nowrap">{{ u.id }}</td>
                                    <td class="p-4 font-medium text-blue-700 whitespace-nowrap">{{ u.email or '-' }}</td>
                                    
                                    <td class="p-4 whitespace-nowrap">
                                        {% if u.role == 'COMPANY' %}
                                            <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-bold">{{ u.position or 'Представник' }}</span>
                                        {% elif u.role == 'ADMIN' %}
                                            <span class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs font-bold">Адміністратор</span>
                                        {% else %}
                                            <span class="text-gray-400 text-xs">-</span>
                                        {% endif %}
                                    </td>
                                    
                                    <td class="p-4 font-bold break-words whitespace-normal">
                                        {% if u.role == 'COMPANY' %}{{ u.company_name or '-' }}{% else %}<span class="text-gray-400 text-xs">-</span>{% endif %}
                                    </td>
                                <td class="p-4 break-words whitespace-normal">
                                    {% if u.role == 'STUDENT' %}
                                        <b>{{ u.last_name }}</b> {{ u.first_name }} {{ u.patronymic }}
                                    {% else %}<span class="text-gray-400 text-xs">-</span>{% endif %}
                                </td>
                                
                                <td class="p-4 break-words whitespace-normal">
                                    {% if u.role == 'STUDENT' %}
                                        {% if u.course or u.specialty %}
                                            <div class="font-bold whitespace-nowrap">{{ u.course or '?' }} курс</div>
                                            <div class="text-xs text-red-600">{{ u.specialty or '-' }}</div>
                                        {% else %}-{% endif %}
                                    {% else %}<span class="text-gray-400 text-xs">-</span>{% endif %}
                                </td>
                                
                                <td class="p-4 text-xs min-w-[250px] whitespace-normal break-words">
                                    {{ u.contact_info or '-' }}
                                </td>
                                
                                <td class="p-4 whitespace-nowrap">
                                    {% if u.status == 'blocked' %}
                                        <span class="bg-red-200 text-red-800 px-2 py-1 rounded text-xs font-black uppercase">Заблоковано</span>
                                    {% else %}
                                        <span class="bg-green-200 text-green-800 px-2 py-1 rounded text-xs font-black uppercase">Активний</span>
                                    {% endif %}
                                </td>
                                
                                <td class="p-4">
                                    <div class="flex gap-2 items-center min-w-[200px]">
                                        {% if u.id != session.get('user_id') %}
                                            <form action="/admin/toggle_block" method="POST" class="inline-block m-0">
                                                <input type="hidden" name="user_id" value="{{ u.id }}">
                                                {% if u.status == 'blocked' %}
                                                    <button class="bg-green-600 text-white px-3 py-2 rounded hover:bg-green-700 text-xs font-bold uppercase whitespace-nowrap" title="Розблокувати"><i class="fas fa-unlock mr-1"></i> Розблок.</button>
                                                {% else %}
                                                    <button class="bg-orange-500 text-white px-3 py-2 rounded hover:bg-orange-600 text-xs font-bold uppercase whitespace-nowrap" title="Заблокувати" onclick="return confirm('Заблокувати користувача?');"><i class="fas fa-ban mr-1"></i> Блок.</button>
                                                {% endif %}
                                            </form>
                                            <form action="/admin/delete_user" method="POST" class="inline-block m-0" onsubmit="return confirm('ОБЕРЕЖНО! Видалити користувача та всі його дані назавжди?');">
                                                <input type="hidden" name="user_id" value="{{ u.id }}">
                                                <button class="bg-red-700 text-white px-3 py-2 rounded hover:bg-black text-xs font-bold uppercase whitespace-nowrap" title="Видалити"><i class="fas fa-trash mr-1"></i> Видалити</button>
                                            </form>
                                        {% else %}
                                            <span class="text-gray-400 text-xs font-bold whitespace-nowrap">Це ви</span>
                                        {% endif %}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </section>
            {% endif %}

            <!-- Вкладка: ПРОФІЛЬ (Profile) -->
            {% if active_tab == 'profile' %}
            <section class="max-w-4xl mx-auto">
                <div class="bg-white text-black rounded-[2rem] p-8 md:p-12 shadow-2xl relative">
                    
                    {% if session.get('role') == 'ADMIN' %}
                    <div class="absolute top-4 right-4 bg-yellow-300 px-3 py-1 rounded-lg text-xs font-bold uppercase">Admin Mode</div>
                    {% endif %}

                    <h2 class="text-3xl font-black mb-6 uppercase border-b pb-4 flex items-center justify-between">
                        Редагування Профілю
                        <span class="text-sm bg-black text-white px-3 py-1 rounded-full font-normal">{{ user_info.role }}</span>
                    </h2>

                    <form action="/update_profile" method="POST" class="space-y-6">
                        <!-- Загальні поля -->
                        <div class="grid md:grid-cols-2 gap-6 bg-gray-50 p-4 rounded-xl border">
                            <div>
                                <label class="label-text">Логін</label>
                                <input type="text" value="{{ user_info.username }}" disabled class="w-full p-3 rounded-xl bg-gray-200 cursor-not-allowed font-mono">
                            </div>
                            <div>
                                <label class="label-text">Email</label>
                                <input type="email" name="email" value="{{ user_info.email }}" class="w-full p-3 rounded-xl bg-white font-bold border focus:border-red-500">
                            </div>
                        </div>

                        {% if user_info.role == 'STUDENT' %}
                        
                        <!-- ПАНЕЛЬ АДМІНІСТРАТОРА (Редагування рейтингу) -->
                        {% if session.get('role') == 'ADMIN' %}
                        <div class="bg-yellow-50 p-4 rounded-xl border border-yellow-400 mb-6 shadow-inner">
                            <label class="label-text text-yellow-800"><i class="fas fa-star text-yellow-500"></i> Рейтинг Студента (Тільки для Адміністратора)</label>
                            <input type="number" name="rating" value="{{ profile_data.rating or 0 }}" class="w-full p-3 rounded-xl border-2 border-yellow-300 bg-white font-black text-xl" placeholder="Введіть бали рейтингу...">
                        </div>
                        {% endif %}

                        <div class="space-y-4">
                            <!-- ПІБ -->
                            <div class="grid md:grid-cols-3 gap-4">
                                <div>
                                    <label class="label-text">Прізвище</label>
                                    <input type="text" name="last_name" value="{{ profile_data.last_name or '' }}" class="w-full p-3 rounded-xl border">
                                </div>
                                <div>
                                    <label class="label-text">Ім'я</label>
                                    <input type="text" name="first_name" value="{{ profile_data.first_name or '' }}" class="w-full p-3 rounded-xl border">
                                </div>
                                <div>
                                    <label class="label-text">По батькові</label>
                                    <input type="text" name="patronymic" value="{{ profile_data.patronymic or '' }}" class="w-full p-3 rounded-xl border">
                                </div>
                            </div>
                            
                            <!-- Навчання -->
                            <div class="grid md:grid-cols-2 gap-4">
                                <div>
                                    <label class="label-text">Курс</label>
                                    <input type="number" name="course" value="{{ profile_data.course or '' }}" class="w-full p-3 rounded-xl border" placeholder="1-6">
                                </div>
                                <div>
                                    <label class="label-text">Спеціальність</label>
                                    <input type="text" name="specialty" value="{{ profile_data.specialty or '' }}" class="w-full p-3 rounded-xl border" placeholder="Наприклад: Інженерія ПЗ">
                                </div>
                            </div>

                            <div class="grid md:grid-cols-[auto_1fr] gap-4 items-start pt-2">
                                <img src="{{ profile_data.avatar }}" class="w-20 h-20 rounded-full border bg-gray-100 object-cover">
                                <div>
                                    <label class="label-text">Посилання на фото (Аватар)</label>
                                    <input type="text" name="avatar" value="{{ profile_data.avatar or '' }}" class="w-full p-3 rounded-xl border" placeholder="https://...">
                                </div>
                            </div>
                            
                            <label class="label-text">Навички (через кому)</label>
                            <textarea name="skills" class="w-full p-3 rounded-xl border h-20" placeholder="Python, SQL, Figma...">{{ profile_data.skills or '' }}</textarea>
                            
                            <hr class="my-4">
                            <h3 class="font-black text-red-700 uppercase mb-2">Контакти та Зв'язок</h3>

                            <div>
                                <label class="label-text">Контактна інформація (Телефон, Telegram тощо)</label>
                                <input type="text" name="contact_info" value="{{ profile_data.contact_info or '' }}" class="w-full p-3 rounded-xl border" placeholder="+380... або @username">
                            </div>
                            
                            <div>
                                <label class="label-text">Link (GitHub, LinkedIn, Портфоліо)</label>
                                <input type="text" name="links" value="{{ profile_data.links or '' }}" class="w-full p-3 rounded-xl border" placeholder="https://github.com/...">
                                <p class="text-xs text-gray-500 mt-1">Додайте посилання через кому, вони перетворяться на зручні іконки.</p>
                            </div>
                        </div>
                        
                        {% elif user_info.role == 'COMPANY' %}
                        <div class="space-y-4">
                            <div>
                                <label class="label-text text-blue-800">Назва Компанії</label>
                                <input type="text" name="company_name" value="{{ profile_data.company_name or '' }}" class="w-full p-3 rounded-xl border-2 border-blue-100 font-bold text-lg" placeholder="Назва вашої фірми">
                            </div>

                            <div>
                                <label class="label-text text-blue-800">Ваша Посада (Company Role)</label>
                                <input type="text" name="position" value="{{ profile_data.position or '' }}" class="w-full p-3 rounded-xl border-2 border-blue-100 font-bold" placeholder="HR, Менеджер, Рекрутер, CEO...">
                            </div>

                            <div class="grid md:grid-cols-[auto_1fr] gap-4 items-start bg-blue-50 p-4 rounded-xl">
                                <img src="{{ profile_data.avatar }}" class="w-24 h-24 rounded-lg border bg-white object-contain">
                                <div class="w-full">
                                    <label class="label-text text-blue-800">Логотип Компанії (URL)</label>
                                    <input type="text" name="avatar" value="{{ profile_data.avatar or '' }}" class="w-full p-3 rounded-xl border" placeholder="Вставте посилання на картинку логотипу...">
                                </div>
                            </div>
                            
                            <div>
                                <label class="label-text text-blue-800">Контактна інформація</label>
                                <input type="text" name="contact_info" value="{{ profile_data.contact_info or '' }}" class="w-full p-3 rounded-xl border-2 border-blue-100" placeholder="Телефон, адреса офісу, або Telegram рекрутера...">
                            </div>

                            <div>
                                <label class="label-text text-blue-800">Опис Компанії / Вакансії</label>
                                <textarea name="description" class="w-full p-3 rounded-xl border h-32" placeholder="Опишіть, чим займається ваша компанія і кого ви шукаєте...">{{ profile_data.description or '' }}</textarea>
                            </div>
                        </div>
                        {% endif %}

                        <button type="submit" class="w-full bg-black text-white py-4 rounded-xl font-black uppercase tracking-widest hover:bg-red-700 transition transform hover:-translate-y-1 shadow-xl">
                            Зберегти Профіль
                        </button>
                    </form>

                    {% if session.get('role') == 'ADMIN' %}
                    <div class="mt-12 pt-8 border-t-2 border-dashed border-gray-300">
                        <h3 class="font-bold mb-4">Адмін: Редагувати іншого користувача</h3>
                        <form action="/admin/select_user" method="POST" class="flex gap-2">
                            <input type="number" name="target_user_id" placeholder="ID" class="p-3 rounded-xl border-2 border-black w-24 text-center">
                            <button class="bg-yellow-400 text-black px-6 rounded-xl font-bold uppercase hover:bg-yellow-500">Вибрати</button>
                        </form>
                    </div>
                    {% endif %}
                </div>
            </section>
            {% endif %}

        </div>
        {% endif %}

    </main>

    <!-- МОДАЛКИ (Login/Register/View) -->
    <div id="login-modal" class="hidden fixed inset-0 modal-bg z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-8 rounded-3xl w-full max-w-sm relative shadow-2xl">
            <button onclick="toggleModal('login-modal')" class="absolute top-4 right-4 text-2xl font-bold hover:text-red-600">&times;</button>
            <h2 class="text-3xl font-black mb-6 text-center uppercase">Вхід</h2>
            <form action="/login" method="POST" class="space-y-4">
                <input type="text" name="username" placeholder="Логін" required class="w-full p-3 rounded-xl font-bold bg-gray-100 border focus:border-black">
                <input type="password" name="password" placeholder="Пароль" required class="w-full p-3 rounded-xl font-bold bg-gray-100 border focus:border-black">
                <button class="w-full bg-black text-white py-3 rounded-xl font-black uppercase hover:bg-red-700 transition">Увійти</button>
            </form>
        </div>
    </div>

    <div id="register-modal" class="hidden fixed inset-0 modal-bg z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-8 rounded-3xl w-full max-w-md relative shadow-2xl max-h-[90vh] overflow-y-auto">
            <button onclick="toggleModal('register-modal')" class="absolute top-4 right-4 text-2xl font-bold hover:text-red-600">&times;</button>
            <h2 class="text-3xl font-black mb-6 text-center uppercase">Реєстрація</h2>
            <form action="/register" method="POST" class="space-y-4">
                <label class="block font-bold mb-1 ml-1 text-gray-500 text-xs uppercase">Оберіть Роль</label>
                <select name="role" class="w-full p-3 rounded-xl font-bold bg-gray-100 mb-4 border-2 border-black cursor-pointer hover:bg-gray-200 transition">
                    <option value="STUDENT">👨‍🎓 Студент (Шукаю роботу)</option>
                    <option value="COMPANY">🏢 Компанія (Шукаю людей)</option>
                </select>
                <input type="text" name="username" placeholder="Логін" required class="w-full p-3 rounded-xl font-bold bg-gray-100 border">
                <input type="email" name="email" placeholder="Email" required class="w-full p-3 rounded-xl font-bold bg-gray-100 border">
                <input type="password" name="password" placeholder="Пароль" required class="w-full p-3 rounded-xl font-bold bg-gray-100 border">
                <button class="w-full bg-red-700 text-white py-3 rounded-xl font-black uppercase hover:bg-black transition">Створити акаунт</button>
            </form>
        </div>
    </div>

    <!-- Запрошення -->
    <div id="invite-modal" class="hidden fixed inset-0 modal-bg z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-8 rounded-3xl w-full max-w-md relative shadow-2xl">
            <button onclick="toggleModal('invite-modal')" class="absolute top-4 right-4 text-2xl font-bold">&times;</button>
            <h2 class="text-2xl font-black mb-2 uppercase text-red-700">Найняти Студента</h2>
            <p id="invite-student-name" class="text-xl font-bold mb-6">...</p>
            <form action="/send_invite" method="POST" class="space-y-4">
                <input type="hidden" name="student_id" id="invite-student-id">
                <textarea name="message" placeholder="Напишіть коротке повідомлення: яку вакансію пропонуєте, умови, контакти..." required class="w-full p-4 rounded-xl bg-gray-100 h-32 border focus:border-black"></textarea>
                <button class="w-full bg-green-600 text-white py-3 rounded-xl font-black uppercase hover:bg-green-700 transition">Надіслати Запрошення</button>
            </form>
        </div>
    </div>

    <!-- Перегляд студента -->
    <div id="student-view-modal" class="hidden fixed inset-0 modal-bg z-[100] flex items-center justify-center p-4">
        <div class="bg-white text-black p-0 rounded-3xl w-full max-w-lg relative shadow-2xl overflow-hidden">
            <div class="h-28 bg-gradient-to-r from-red-900 to-black w-full relative">
                <button onclick="toggleModal('student-view-modal')" class="absolute top-4 right-4 text-white text-2xl font-bold hover:scale-110 transition">&times;</button>
            </div>
            <div class="px-8 pb-8 text-center -mt-14">
                <img id="sv-avatar" src="" class="w-28 h-28 rounded-full border-4 border-white shadow-lg mx-auto bg-gray-200 object-cover">
                <h2 id="sv-name" class="text-3xl font-black uppercase mt-4 tracking-tight"></h2>
                <p id="sv-spec" class="text-red-600 font-bold mb-6 text-lg"></p>
                
                <div class="text-left bg-gray-50 p-6 rounded-2xl space-y-4 text-sm border">
                    <div>
                        <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Навички</span>
                        <p id="sv-skills" class="font-medium bg-white p-2 rounded border"></p>
                    </div>
                    
                    <div>
                        <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Контактна інформація</span>
                        <p id="sv-contact-info" class="font-bold text-gray-800 bg-white p-2 rounded border truncate"></p>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Link (Мережі)</span>
                            <p id="sv-links" class="text-blue-600 flex gap-3 flex-wrap mt-1"></p>
                        </div>
                        <div>
                            <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Email</span>
                            <p id="sv-email" class="text-gray-800 font-bold truncate mt-1"></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleModal(id) {
            document.getElementById(id).classList.toggle('hidden');
        }
        
        function openInviteModal(id, name) {
            document.getElementById('invite-student-id').value = id;
            document.getElementById('invite-student-name').innerText = name;
            toggleModal('invite-modal');
        }

        function openStudentProfile(userId) {
            fetch('/api/student/' + userId)
                .then(r => r.json())
                .then(data => {
                    if(data.error) return alert(data.error);
                    document.getElementById('sv-avatar').src = data.avatar || '';
                    
                    let fullName = [data.last_name, data.first_name, data.patronymic].filter(Boolean).join(' ');
                    document.getElementById('sv-name').innerText = fullName || 'Студент';
                    
                    let specText = [];
                    if(data.course) specText.push(data.course + ' курс');
                    if(data.specialty) specText.push(data.specialty);
                    document.getElementById('sv-spec').innerText = specText.join(', ') || 'Студент';
                    
                    document.getElementById('sv-skills').innerText = data.skills || '-';
                    document.getElementById('sv-contact-info').innerText = data.contact_info || '-';
                    
                    // Обробка посилань у клікабельні іконки
                    let linksHtml = '';
                    if (data.links && data.links.trim() !== '') {
                        let urls = data.links.split(',').map(l => l.trim());
                        urls.forEach(url => {
                            if (!url) return;
                            let href = url.startsWith('http') ? url : 'https://' + url;
                            let iconClass = 'fas fa-link';
                            if (url.toLowerCase().includes('github')) iconClass = 'fab fa-github';
                            if (url.toLowerCase().includes('linkedin')) iconClass = 'fab fa-linkedin';
                            linksHtml += `<a href="${href}" target="_blank" class="text-2xl hover:text-red-600 transition" title="${url}"><i class="${iconClass}"></i></a>`;
                        });
                    } else {
                        linksHtml = '-';
                    }
                    document.getElementById('sv-links').innerHTML = linksHtml;
                    
                    document.getElementById('sv-email').innerText = data.email || '';
                    toggleModal('student-view-modal');
                });
        }
    </script>
    <style>
        .label-text { display: block; font-weight: bold; font-size: 0.75rem; text-transform: uppercase; color: #6b7280; margin-bottom: 0.25rem; }
    </style>
</body>
</html>
"""

# --- МАРШРУТИЗАЦІЯ ---

@app.route('/')
def index():
    init_db() 
    active_tab = request.args.get('tab', 'home') # Змінено вкладку за замовчуванням на 'home'
    db = get_db()
    
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE, active_tab='landing')

    # Отримання параметрів фільтрації для Ranking
    search_query = request.args.get('search', '').strip()
    course_filter = request.args.get('course', '').strip()
    specialty_filter = request.args.get('specialty', '').strip()
    sort_order = request.args.get('sort', 'desc') # за замовчуванням рейтинг по спаданню (топ найкращих)

    # Зберігаємо поточні фільтри для підстановки в HTML шаблоні
    current_filters = {
        'search': search_query,
        'course': course_filter,
        'specialty': specialty_filter,
        'sort': sort_order
    }

    # Підготовка списків для dropdown-меню (витягуємо унікальні курси та спеціальності)
    unique_courses = []
    unique_specialties = []
    
    if active_tab == 'ranking':
        c_cur = db.execute("SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != '' ORDER BY course")
        unique_courses = [r['course'] for r in c_cur.fetchall()]
        
        s_cur = db.execute("SELECT DISTINCT specialty FROM students WHERE specialty IS NOT NULL AND specialty != '' ORDER BY specialty")
        unique_specialties = [r['specialty'] for r in s_cur.fetchall()]

    # Формування запиту з фільтрами (Ranking)
    students = []
    if active_tab == 'ranking':
        base_query = "SELECT s.*, u.email FROM students s JOIN users u ON s.user_id = u.id WHERE u.status != 'blocked'"
        params = []
        
        if search_query:
            base_query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.skills LIKE ? OR s.specialty LIKE ?)"
            like_search = f"%{search_query}%"
            params.extend([like_search, like_search, like_search, like_search])
            
        if course_filter:
            base_query += " AND s.course = ?"
            params.append(course_filter)
            
        if specialty_filter:
            base_query += " AND s.specialty = ?"
            params.append(specialty_filter)
            
        if sort_order == 'asc':
            base_query += " ORDER BY s.rating ASC"
        else:
            base_query += " ORDER BY s.rating DESC"

        cur = db.execute(base_query, params)
        students = [dict(row) for row in cur.fetchall()]

    # Users Table for Admin
    all_users = []
    if active_tab == 'users' and session.get('role') == 'ADMIN':
        query = """
            SELECT u.id, u.username, u.email, u.role, u.status,
                   s.first_name, s.last_name, s.patronymic, s.course, s.specialty, s.skills, s.links,
                   c.company_name, c.description, c.position,
                   COALESCE(s.contact_info, c.contact_info) as contact_info
            FROM users u
            LEFT JOIN students s ON u.id = s.user_id
            LEFT JOIN companies c ON u.id = c.user_id
            ORDER BY u.id DESC
        """
        all_users = [dict(row) for row in db.execute(query).fetchall()]

    # Profile Data
    user_info = {}
    profile_data = {}
    if 'user_id' in session:
        target_id = session.get('edit_target_id', session['user_id'])
        cur = db.execute("SELECT * FROM users WHERE id = ?", (target_id,))
        user_info = dict(cur.fetchone() or {})
        
        if user_info.get('role') == 'STUDENT':
            cur = db.execute("SELECT * FROM students WHERE user_id = ?", (target_id,))
            profile_data = dict(cur.fetchone() or {})
        elif user_info.get('role') == 'COMPANY':
            cur = db.execute("SELECT * FROM companies WHERE user_id = ?", (target_id,))
            profile_data = dict(cur.fetchone() or {})

    # Invitations
    invitations = []
    pending_count = 0
    
    if session.get('role') == 'STUDENT':
        count_res = db.execute("SELECT COUNT(*) as c FROM invitations i JOIN students s ON i.student_id = s.id WHERE s.user_id = ? AND i.status='pending'", (session['user_id'],)).fetchone()
        pending_count = count_res['c']

    if active_tab == 'invitations':
        if session.get('role') == 'ADMIN':
            query = """
                SELECT i.*, s.first_name, s.last_name, 
                       c.company_name, c.avatar as company_avatar
                FROM invitations i
                LEFT JOIN students s ON i.student_id = s.id
                LEFT JOIN companies c ON i.company_id = c.id
                ORDER BY i.created_at DESC
            """
            invitations = [dict(row) for row in db.execute(query).fetchall()]
            
        elif session.get('role') == 'COMPANY':
            query = """
                SELECT i.*, s.first_name, s.last_name
                FROM invitations i
                JOIN students s ON i.student_id = s.id
                WHERE i.user_id = ?
                ORDER BY i.created_at DESC
            """
            invitations = [dict(row) for row in db.execute(query, (session['user_id'],)).fetchall()]
            
        elif session.get('role') == 'STUDENT':
            query = """
                SELECT i.*, c.company_name, c.avatar as company_avatar
                FROM invitations i
                JOIN students s ON i.student_id = s.id
                LEFT JOIN companies c ON i.company_id = c.id
                WHERE s.user_id = ?
                ORDER BY i.created_at DESC
            """
            invitations = [dict(row) for row in db.execute(query, (session['user_id'],)).fetchall()]

    return render_template_string(HTML_TEMPLATE, 
                                  active_tab=active_tab, 
                                  students=students, 
                                  all_users=all_users,
                                  user_info=user_info, 
                                  profile_data=profile_data,
                                  invitations=invitations,
                                  pending_count=pending_count,
                                  current_filters=current_filters,
                                  unique_courses=unique_courses,
                                  unique_specialties=unique_specialties)

# --- АВТОРИЗАЦІЯ ---

@app.route('/register', methods=['POST'])
def register():
    role = request.form.get('role')
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)", 
                    (username, password, email, role))
        user_id = cur.lastrowid
        
        if role == 'STUDENT':
            cur.execute("INSERT INTO students (user_id, first_name, last_name) VALUES (?, ?, ?)", (user_id, username, 'Student'))
        elif role == 'COMPANY':
            cur.execute("INSERT INTO companies (user_id, company_name) VALUES (?, ?)", (user_id, username))
            
        db.commit()
        session['user_id'] = user_id
        session['role'] = role
        session['username'] = username
        flash("Вітаємо! Ваш акаунт створено.")
    except sqlite3.IntegrityError:
        flash("Помилка: Такий логін вже зайнятий.")
        
    return redirect('/')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    
    if user:
        if dict(user).get('status') == 'blocked':
            flash("Ваш акаунт було заблоковано адміністратором.")
            return redirect('/')
            
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['username'] = user['username']
        session.pop('edit_target_id', None)
    else:
        flash("Невірні дані для входу")
        
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- ЛОГІКА ---

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session: return redirect('/')
    
    target_id = session.get('edit_target_id', session['user_id'])
    
    if target_id != session['user_id'] and session['role'] != 'ADMIN':
        return "Access Denied", 403

    db = get_db()
    role = db.execute("SELECT role FROM users WHERE id = ?", (target_id,)).fetchone()['role']
    
    db.execute("UPDATE users SET email = ? WHERE id = ?", (request.form.get('email'), target_id))
    
    if role == 'STUDENT':
        # Якщо ми під адміном, отримуємо переданий рейтинг (якщо ні - лишаємо старий)
        rating_val = request.form.get('rating')
        if session.get('role') == 'ADMIN' and rating_val is not None:
            db.execute("UPDATE students SET rating=? WHERE user_id=?", (int(rating_val), target_id))

        db.execute("""
            UPDATE students SET first_name=?, last_name=?, patronymic=?, course=?, specialty=?, skills=?, links=?, contact_info=?, avatar=?
            WHERE user_id=?
        """, (
            request.form.get('first_name'),
            request.form.get('last_name'),
            request.form.get('patronymic'),
            request.form.get('course'),
            request.form.get('specialty'),
            request.form.get('skills'),
            request.form.get('links'),
            request.form.get('contact_info'),
            request.form.get('avatar'),
            target_id
        ))
    elif role == 'COMPANY':
        db.execute("""
            UPDATE companies SET company_name=?, description=?, avatar=?, position=?, contact_info=?
            WHERE user_id=?
        """, (
            request.form.get('company_name'),
            request.form.get('description'),
            request.form.get('avatar'),
            request.form.get('position'),
            request.form.get('contact_info'),
            target_id
        ))
    
    db.commit()
    flash("Профіль успішно оновлено!")
    return redirect('/?tab=profile')

@app.route('/admin/select_user', methods=['POST'])
def admin_select_user():
    if session.get('role') != 'ADMIN': return redirect('/')
    try:
        tid = int(request.form.get('target_user_id'))
        session['edit_target_id'] = tid
        flash(f"Режим редагування користувача ID: {tid}")
    except:
        flash("Невірний ID")
    return redirect('/?tab=profile')

@app.route('/send_invite', methods=['POST'])
def send_invite():
    if 'user_id' not in session: return redirect('/')
    
    db = get_db()
    student_record_id = request.form.get('student_id') 
    message = request.form.get('message')
    
    comp_row = db.execute("SELECT id FROM companies WHERE user_id = ?", (session['user_id'],)).fetchone()
    comp_id = comp_row['id'] if comp_row else None
    
    db.execute("""
        INSERT INTO invitations (student_id, company_id, user_id, message, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (student_record_id, comp_id, session['user_id'], message))
    
    db.commit()
    flash("Запрошення надіслано!")
    return redirect('/?tab=ranking')

@app.route('/respond_invite', methods=['POST'])
def respond_invite():
    if session.get('role') != 'STUDENT': return redirect('/')
    
    invite_id = request.form.get('invite_id')
    action = request.form.get('action') 
    
    new_status = 'accepted' if action == 'accept' else 'rejected'
    
    db = get_db()
    db.execute("UPDATE invitations SET status = ? WHERE id = ?", (new_status, invite_id))
    db.commit()
    
    msg = "Ви прийняли пропозицію!" if new_status == 'accepted' else "Ви відхилили пропозицію."
    flash(msg)
    return redirect('/?tab=invitations')

@app.route('/delete_invite', methods=['POST'])
def delete_invite():
    if session.get('role') != 'ADMIN': return redirect('/')
    invite_id = request.form.get('invite_id')
    db = get_db()
    db.execute("DELETE FROM invitations WHERE id = ?", (invite_id,))
    db.commit()
    flash("Заявку успішно видалено.")
    return redirect('/?tab=invitations')

@app.route('/flag_invite', methods=['POST'])
def flag_invite():
    if session.get('role') != 'COMPANY': return redirect('/')
    invite_id = request.form.get('invite_id')
    db = get_db()
    db.execute("UPDATE invitations SET flagged = 1 WHERE id = ?", (invite_id,))
    db.commit()
    flash("Ви позначили цю заявку. Адміністратор отримає сповіщення!")
    return redirect('/?tab=invitations')

@app.route('/admin/toggle_block', methods=['POST'])
def admin_toggle_block():
    if session.get('role') != 'ADMIN': return redirect('/')
    user_id = request.form.get('user_id')
    db = get_db()
    db.execute("UPDATE users SET status = CASE WHEN status = 'blocked' THEN 'active' ELSE 'blocked' END WHERE id = ?", (user_id,))
    db.commit()
    flash("Статус користувача змінено.")
    return redirect('/?tab=users')

@app.route('/admin/delete_user', methods=['POST'])
def admin_delete_user():
    if session.get('role') != 'ADMIN': return redirect('/')
    user_id = request.form.get('user_id')
    db = get_db()
    
    db.execute("""
        DELETE FROM invitations 
        WHERE user_id = ? 
           OR student_id IN (SELECT id FROM students WHERE user_id = ?) 
           OR company_id IN (SELECT id FROM companies WHERE user_id = ?)
    """, (user_id, user_id, user_id))
    
    db.execute("DELETE FROM students WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM companies WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    
    flash("Користувача та всі його дані успішно видалено назавжди.")
    return redirect('/?tab=users')

@app.route('/api/student/<int:user_id>')
def get_student_api(user_id):
    db = get_db()
    std = db.execute("""
        SELECT s.*, u.email 
        FROM students s JOIN users u ON s.user_id = u.id 
        WHERE u.id = ?
    """, (user_id,)).fetchone()
    
    if std:
        return dict(std)
    return {"error": "Student not found"}, 404

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, port=5000)
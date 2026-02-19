import sqlite3
import os
from flask import Flask, render_template_string, request, session, redirect, g, flash
from datetime import datetime

# Налаштування додатка
app = Flask(__name__)
app.secret_key = 'ukd_recruitment_secret_key_v3'
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
                role TEXT NOT NULL DEFAULT 'STUDENT'
            )
        ''')

        # 2. Students
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                specialty TEXT,
                skills TEXT,
                links TEXT,
                avatar TEXT DEFAULT 'https://cdn-icons-png.flaticon.com/512/354/354637.png',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # 3. Companies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                company_name TEXT,
                description TEXT,
                avatar TEXT DEFAULT 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Міграція для існуючих баз даних (додаємо колонку avatar якщо її немає)
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN avatar TEXT DEFAULT 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png'")
        except sqlite3.OperationalError:
            pass # Колонка вже існує

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
        
        # Міграція для таблиці запрошень (позначка для адміна)
        try:
            cursor.execute("ALTER TABLE invitations ADD COLUMN flagged BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Колонка вже існує
            
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
        body { background-color: var(--ukd-red); color: white; font-family: 'Inter', sans-serif; }
        .card { background: white; color: black; border-left: 8px solid black; transition: 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .nav-btn.active { border-bottom: 2px solid white; font-weight: bold; color: white; }
        .nav-btn { color: #ccc; transition: 0.3s; }
        .nav-btn:hover { color: white; }
        input, select, textarea { border: 2px solid #ddd; transition: 0.3s; }
        input:focus, select:focus, textarea:focus { border-color: var(--ukd-bright); outline: none; }
        .modal-bg { background: rgba(0,0,0,0.9); }
        .landing-hero { background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)), url('https://yt3.googleusercontent.com/ytc/AIdro_k624OQvH_3vjA4H8U1fQvX5Q5x5x5x5x5x5x5x5=s900-c-k-c0x00ffffff-no-rj'); background-size: cover; background-position: center; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Навігація -->
    <nav class="bg-black p-4 sticky top-0 z-50 shadow-2xl border-b border-white/10">
        <div class="container mx-auto flex flex-wrap justify-between items-center">
            <div class="flex items-center space-x-3 cursor-pointer" onclick="window.location.href='/'">
                <div class="bg-red-700 p-2 rounded-lg"><i class="fas fa-graduation-cap text-white"></i></div>
                <span class="text-xl font-black uppercase tracking-tighter">УКД <span class="text-red-600">Talent</span></span>
            </div>
            
            {% if session.get('user_id') %}
            <div class="hidden md:flex space-x-6 items-center flex-grow justify-center">
                <a href="/?tab=ranking" class="nav-btn px-2 py-1 {{ 'active' if active_tab == 'ranking' else '' }}">
                    <i class="fas fa-list-ol mr-1"></i> Рейтинг
                </a>
                
                {% if session.get('role') == 'ADMIN' %}
                    <a href="/?tab=invitations" class="nav-btn px-2 py-1 {{ 'active' if active_tab == 'invitations' else '' }} text-yellow-400">
                        <i class="fas fa-shield-alt mr-1"></i> Адмін Панель
                    </a>
                {% endif %}

                {% if session.get('role') == 'COMPANY' %}
                     <a href="/?tab=invitations" class="nav-btn px-2 py-1 {{ 'active' if active_tab == 'invitations' else '' }}">
                        <i class="fas fa-paper-plane mr-1"></i> Мої Запити
                    </a>
                {% endif %}
                
                {% if session.get('role') == 'STUDENT' %}
                     <a href="/?tab=invitations" class="nav-btn px-2 py-1 {{ 'active' if active_tab == 'invitations' else '' }}">
                        <i class="fas fa-inbox mr-1"></i> Мої Запрошення 
                        {% if pending_count > 0 %}
                        <span class="bg-red-600 text-white text-xs px-2 py-0.5 rounded-full ml-1 animate-pulse">{{ pending_count }}</span>
                        {% endif %}
                    </a>
                {% endif %}

                <a href="/?tab=profile" class="nav-btn px-2 py-1 {{ 'active' if active_tab == 'profile' else '' }}">
                    <i class="fas fa-user-circle mr-1"></i> Мій Профіль
                </a>
            </div>

            <div class="flex items-center space-x-4">
                <div class="text-right hidden sm:block">
                    <div class="text-xs text-gray-400 uppercase font-bold">{{ session.get('role') }}</div>
                    <div class="font-bold">{{ session.get('username') }}</div>
                </div>
                <a href="/logout" class="bg-white/10 hover:bg-red-600 p-2 rounded-full transition"><i class="fas fa-sign-out-alt"></i></a>
            </div>
            {% else %}
            <div>
                 <button onclick="toggleModal('login-modal')" class="bg-white text-black px-5 py-1.5 rounded-full font-bold hover:bg-gray-200">Вхід</button>
                 <button onclick="toggleModal('register-modal')" class="border border-white text-white px-5 py-1.5 rounded-full font-bold hover:bg-white hover:text-black ml-2">Реєстрація</button>
            </div>
            {% endif %}
        </div>
        
        <!-- Мобільне меню -->
        {% if session.get('user_id') %}
        <div class="md:hidden flex justify-around mt-4 border-t border-white/10 pt-2">
            <a href="/?tab=ranking" class="text-sm"><i class="fas fa-list"></i> Рейтинг</a>
            <a href="/?tab=invitations" class="text-sm"><i class="fas fa-inbox"></i> Inbox</a>
            <a href="/?tab=profile" class="text-sm"><i class="fas fa-user"></i> Профіль</a>
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

        <!-- ЛЕНДІНГ ПЕЙДЖ (Для незалогінених) -->
        {% if not session.get('user_id') %}
        <div class="landing-hero min-h-[80vh] flex items-center justify-center text-center px-4">
            <div class="max-w-4xl">
                <h1 class="text-5xl md:text-7xl font-black uppercase mb-6 drop-shadow-lg">
                    Знайди Своє <span class="text-red-600">Майбутнє</span>
                </h1>
                <p class="text-xl md:text-2xl mb-8 font-light text-gray-200">
                    Платформа працевлаштування для студентів Університету Короля Данила.
                    <br>Компанії знаходять таланти, студенти знаходять можливості.
                </p>
                <div class="flex flex-col md:flex-row justify-center gap-4">
                    <button onclick="toggleModal('register-modal')" class="bg-red-700 text-white px-8 py-4 rounded-full text-xl font-black uppercase hover:bg-red-800 transition shadow-xl transform hover:scale-105">
                        <i class="fas fa-rocket mr-2"></i> Стати Студентом
                    </button>
                    <button onclick="toggleModal('register-modal')" class="bg-white text-black px-8 py-4 rounded-full text-xl font-black uppercase hover:bg-gray-200 transition shadow-xl transform hover:scale-105">
                        <i class="fas fa-building mr-2"></i> Я Роботодавець
                    </button>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mt-16 text-left">
                    <div class="bg-black/50 p-6 rounded-2xl backdrop-blur-sm border border-white/10">
                        <i class="fas fa-user-graduate text-4xl text-red-500 mb-4"></i>
                        <h3 class="text-xl font-bold uppercase mb-2">Для Студентів</h3>
                        <p class="text-gray-300">Створіть портфоліо, додайте навички та отримуйте пропозиції роботи прямо на сайті.</p>
                    </div>
                    <div class="bg-black/50 p-6 rounded-2xl backdrop-blur-sm border border-white/10">
                        <i class="fas fa-briefcase text-4xl text-blue-500 mb-4"></i>
                        <h3 class="text-xl font-bold uppercase mb-2">Для Компаній</h3>
                        <p class="text-gray-300">Переглядайте рейтинг найкращих студентів, фільтруйте за навичками та надсилайте запрошення.</p>
                    </div>
                    <div class="bg-black/50 p-6 rounded-2xl backdrop-blur-sm border border-white/10">
                        <i class="fas fa-check-circle text-4xl text-green-500 mb-4"></i>
                        <h3 class="text-xl font-bold uppercase mb-2">Простота</h3>
                        <p class="text-gray-300">Без зайвих резюме. Тільки реальні навички, рейтинг та прямий зв'язок.</p>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        
        <!-- ВНУТРІШНЯ ЧАСТИНА САЙТУ -->
        <div class="container mx-auto px-4 py-8">

            <!-- Вкладка: РЕЙТИНГ (Ranking) -->
            {% if active_tab == 'ranking' %}
            <section class="max-w-6xl mx-auto">
                <h2 class="text-4xl font-black mb-8 uppercase tracking-tighter border-b-4 border-white pb-2">
                    Активні Студенти
                </h2>
                
                {% if students %}
                <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {% for std in students %}
                    <div class="card rounded-2xl p-6 relative group overflow-hidden">
                        <div class="flex items-center space-x-4 mb-4">
                            <img src="{{ std.avatar }}" class="w-16 h-16 rounded-full border-2 border-black object-cover bg-gray-200">
                            <div>
                                <h3 class="text-xl font-black uppercase">{{ std.first_name }} {{ std.last_name }}</h3>
                                <p class="text-sm text-gray-500 font-bold">{{ std.specialty }}</p>
                            </div>
                        </div>
                        
                        <div class="mb-4 h-16 overflow-hidden">
                            <p class="text-xs font-bold uppercase text-gray-400 mb-1">Навички:</p>
                            <div class="flex flex-wrap gap-1">
                                {% for skill in (std.skills or '').split(',') %}
                                    {% if skill.strip() %}
                                    <span class="bg-gray-200 text-black px-2 py-0.5 rounded text-xs font-bold">{{ skill.strip() }}</span>
                                    {% endif %}
                                {% endfor %}
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-2 mt-4">
                            <button onclick="openStudentProfile({{ std.user_id }})" class="bg-black text-white py-2 rounded-lg font-bold text-sm uppercase hover:bg-gray-800 transition">
                                <i class="fas fa-eye mr-1"></i> Профіль
                            </button>
                            
                            {% if session.get('role') in ['COMPANY', 'ADMIN'] %}
                            <button onclick="openInviteModal({{ std.id }}, '{{ std.first_name }}')" class="bg-red-700 text-white py-2 rounded-lg font-bold text-sm uppercase hover:bg-red-800 transition">
                                <i class="fas fa-handshake mr-1"></i> Найняти
                            </button>
                            {% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                    <div class="text-center opacity-50 text-xl py-20">Поки що немає зареєстрованих студентів.</div>
                {% endif %}
            </section>
            {% endif %}

            <!-- Вкладка: СКРИНЬКА (Invitations) -->
            {% if active_tab == 'invitations' %}
            <section class="max-w-5xl mx-auto">
                <h2 class="text-3xl font-black mb-8 uppercase flex items-center gap-3">
                    {% if session.get('role') == 'ADMIN' %} <i class="fas fa-shield-alt text-yellow-400"></i> Панель Керування Заявками
                    {% elif session.get('role') == 'STUDENT' %} <i class="fas fa-inbox text-white"></i> Мої Запрошення на Роботу
                    {% else %} <i class="fas fa-paper-plane text-blue-400"></i> Надіслані Пропозиції {% endif %}
                </h2>
                
                <div class="bg-white text-black rounded-3xl overflow-hidden shadow-2xl">
                    <table class="w-full text-left">
                        <thead class="bg-gray-100 border-b-2 border-black">
                            <tr>
                                {% if session.get('role') != 'COMPANY' %}<th class="p-4 font-black uppercase">Від Кого (Компанія)</th>{% endif %}
                                {% if session.get('role') != 'STUDENT' %}<th class="p-4 font-black uppercase">Кому (Студент)</th>{% endif %}
                                <th class="p-4 font-black uppercase">Повідомлення</th>
                                <th class="p-4 font-black uppercase">Статус</th>
                                <th class="p-4 font-black uppercase">Дії</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            {% for inv in invitations %}
                            <tr class="hover:bg-gray-50 transition {% if session.get('role') == 'ADMIN' and inv.flagged %}bg-red-50 border-l-4 border-red-600{% endif %}">
                                {% if session.get('role') != 'COMPANY' %}
                                <td class="p-4">
                                    <div class="flex items-center space-x-3">
                                        <img src="{{ inv.company_avatar or 'https://cdn-icons-png.flaticon.com/512/3061/3061341.png' }}" class="w-10 h-10 rounded-full border border-gray-300">
                                        <div>
                                            <span class="font-bold text-blue-800 block">{{ inv.company_name or 'Невідома Компанія' }}</span>
                                            <span class="text-xs text-gray-500">{{ inv.created_at }}</span>
                                        </div>
                                    </div>
                                </td>
                                {% endif %}
                                
                                {% if session.get('role') != 'STUDENT' %}
                                <td class="p-4 font-bold">{{ inv.first_name }} {{ inv.last_name }}</td>
                                {% endif %}
                                
                                <td class="p-4 text-sm text-gray-600 italic max-w-xs">"{{ inv.message }}"</td>
                                
                                <td class="p-4">
                                    {% if inv.status == 'pending' %}
                                        <span class="bg-yellow-100 text-yellow-800 px-3 py-1 rounded-full text-xs font-black uppercase animate-pulse">Очікує</span>
                                    {% elif inv.status == 'accepted' %}
                                        <span class="bg-green-100 text-green-800 px-3 py-1 rounded-full text-xs font-black uppercase"><i class="fas fa-check mr-1"></i> Прийнято</span>
                                    {% elif inv.status == 'rejected' %}
                                        <span class="bg-red-100 text-red-800 px-3 py-1 rounded-full text-xs font-black uppercase"><i class="fas fa-times mr-1"></i> Відхилено</span>
                                    {% endif %}
                                    
                                    {% if session.get('role') == 'ADMIN' and inv.flagged %}
                                        <div class="mt-2 text-red-600 text-xs font-black uppercase animate-bounce"><i class="fas fa-flag"></i> Увага адміна!</div>
                                    {% endif %}
                                </td>

                                <td class="p-4 flex gap-2 flex-wrap">
                                    {% if session.get('role') == 'STUDENT' and inv.status == 'pending' %}
                                        <form action="/respond_invite" method="POST" class="inline">
                                            <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                            <input type="hidden" name="action" value="accept">
                                            <button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 text-xs font-bold uppercase">Так</button>
                                        </form>
                                        <form action="/respond_invite" method="POST" class="inline">
                                            <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                            <input type="hidden" name="action" value="reject">
                                            <button class="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 text-xs font-bold uppercase">Ні</button>
                                        </form>
                                    {% elif session.get('role') == 'STUDENT' %}
                                        <span class="text-gray-400 text-xs uppercase font-bold">Закрито</span>
                                    {% endif %}
                                    
                                    {% if session.get('role') == 'ADMIN' %}
                                        <form action="/delete_invite" method="POST" class="inline" onsubmit="return confirm('Видалити цю заявку назавжди?');">
                                            <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                            <button class="bg-black text-white px-3 py-1 rounded hover:bg-red-700 text-xs font-bold uppercase" title="Видалити"><i class="fas fa-trash"></i></button>
                                        </form>
                                    {% endif %}
                                    
                                    {% if session.get('role') == 'COMPANY' %}
                                        {% if not inv.flagged %}
                                            <form action="/flag_invite" method="POST" class="inline">
                                                <input type="hidden" name="invite_id" value="{{ inv.id }}">
                                                <button class="bg-yellow-400 text-black px-3 py-1 rounded hover:bg-yellow-500 text-xs font-bold uppercase whitespace-nowrap" title="Покликати адміна для вирішення питань"><i class="fas fa-flag"></i> Покликати Адміна</button>
                                            </form>
                                        {% else %}
                                            <span class="text-red-600 text-xs font-bold uppercase"><i class="fas fa-flag"></i> Адмін сповіщений</span>
                                        {% endif %}
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                            {% if not invitations %}
                            <tr><td colspan="5" class="p-8 text-center text-gray-400">У вас поки немає повідомлень.</td></tr>
                            {% endif %}
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
                                <label class="block font-bold text-xs uppercase mb-2 text-gray-500">Логін</label>
                                <input type="text" value="{{ user_info.username }}" disabled class="w-full p-3 rounded-xl bg-gray-200 cursor-not-allowed font-mono">
                            </div>
                            <div>
                                <label class="block font-bold text-xs uppercase mb-2 text-gray-500">Email</label>
                                <input type="email" name="email" value="{{ user_info.email }}" class="w-full p-3 rounded-xl bg-white font-bold border focus:border-red-500">
                            </div>
                        </div>

                        {% if user_info.role == 'STUDENT' %}
                        <div class="space-y-4">
                            <div class="grid md:grid-cols-2 gap-4">
                                <div>
                                    <label class="label-text">Ім'я</label>
                                    <input type="text" name="first_name" value="{{ profile_data.first_name or '' }}" class="w-full p-3 rounded-xl border">
                                </div>
                                <div>
                                    <label class="label-text">Прізвище</label>
                                    <input type="text" name="last_name" value="{{ profile_data.last_name or '' }}" class="w-full p-3 rounded-xl border">
                                </div>
                            </div>
                            
                            <label class="label-text">Спеціальність</label>
                            <input type="text" name="specialty" value="{{ profile_data.specialty or '' }}" class="w-full p-3 rounded-xl border" placeholder="Наприклад: Інженерія ПЗ">
                            
                            <div class="grid md:grid-cols-[auto_1fr] gap-4 items-start">
                                <img src="{{ profile_data.avatar }}" class="w-20 h-20 rounded-full border bg-gray-100 object-cover">
                                <div>
                                    <label class="label-text">Посилання на фото (Аватар)</label>
                                    <input type="text" name="avatar" value="{{ profile_data.avatar or '' }}" class="w-full p-3 rounded-xl border" placeholder="https://...">
                                </div>
                            </div>
                            
                            <label class="label-text">Навички (через кому)</label>
                            <textarea name="skills" class="w-full p-3 rounded-xl border h-20" placeholder="Python, SQL, Figma...">{{ profile_data.skills or '' }}</textarea>
                            
                            <label class="label-text">Посилання (GitHub, LinkedIn)</label>
                            <input type="text" name="links" value="{{ profile_data.links or '' }}" class="w-full p-3 rounded-xl border">
                        </div>
                        
                        {% elif user_info.role == 'COMPANY' %}
                        <div class="space-y-4">
                            <div>
                                <label class="label-text text-blue-800">Назва Компанії</label>
                                <input type="text" name="company_name" value="{{ profile_data.company_name or '' }}" class="w-full p-3 rounded-xl border-2 border-blue-100 font-bold text-lg" placeholder="Назва вашої фірми">
                            </div>

                            <div class="grid md:grid-cols-[auto_1fr] gap-4 items-start bg-blue-50 p-4 rounded-xl">
                                <img src="{{ profile_data.avatar }}" class="w-24 h-24 rounded-lg border bg-white object-contain">
                                <div class="w-full">
                                    <label class="label-text text-blue-800">Логотип Компанії (URL)</label>
                                    <input type="text" name="avatar" value="{{ profile_data.avatar or '' }}" class="w-full p-3 rounded-xl border" placeholder="Вставте посилання на картинку логотипу...">
                                    <p class="text-xs text-gray-500 mt-1">Рекомендуємо квадратне зображення</p>
                                </div>
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
        {% endif %} <!-- Кінець перевірки session -->

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
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Контакти</span>
                            <p id="sv-links" class="text-blue-600 underline truncate"></p>
                        </div>
                        <div>
                            <span class="block text-xs font-bold uppercase text-gray-400 mb-1">Email</span>
                            <p id="sv-email" class="text-gray-800 font-bold truncate"></p>
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
                    document.getElementById('sv-name').innerText = (data.first_name || '') + ' ' + (data.last_name || '');
                    document.getElementById('sv-spec').innerText = data.specialty || 'Студент';
                    document.getElementById('sv-skills').innerText = data.skills || '-';
                    document.getElementById('sv-links').innerText = data.links || '-';
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
    active_tab = request.args.get('tab', 'ranking')
    db = get_db()
    
    # Якщо не залогінений - показуємо тільки Лендінг (логіка в HTML шаблоні)
    if 'user_id' not in session:
        return render_template_string(HTML_TEMPLATE, active_tab='landing')

    # Дані для студентів (Ranking)
    students = []
    if active_tab == 'ranking':
        cur = db.execute("SELECT s.*, u.email FROM students s JOIN users u ON s.user_id = u.id")
        students = [dict(row) for row in cur.fetchall()]

    # Дані профілю
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

    # Дані Invitations (Скринька)
    invitations = []
    pending_count = 0
    
    # Лічильник нових повідомлень для меню
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
            # Студент бачить запрошення, адресовані йому
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
                                  user_info=user_info, 
                                  profile_data=profile_data,
                                  invitations=invitations,
                                  pending_count=pending_count)

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
        db.execute("""
            UPDATE students SET first_name=?, last_name=?, specialty=?, skills=?, links=?, avatar=?
            WHERE user_id=?
        """, (
            request.form.get('first_name'),
            request.form.get('last_name'),
            request.form.get('specialty'),
            request.form.get('skills'),
            request.form.get('links'),
            request.form.get('avatar'),
            target_id
        ))
    elif role == 'COMPANY':
        db.execute("""
            UPDATE companies SET company_name=?, description=?, avatar=?
            WHERE user_id=?
        """, (
            request.form.get('company_name'),
            request.form.get('description'),
            request.form.get('avatar'), # Оновлення аватарки компанії
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
    
    # Адмін теж може слати, але company_id буде None (або можна створити фейкову компанію для адміна)
    
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
    action = request.form.get('action') # 'accept' or 'reject'
    
    new_status = 'accepted' if action == 'accept' else 'rejected'
    
    db = get_db()
    # Перевірка чи цей інвайт належить цьому студенту
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

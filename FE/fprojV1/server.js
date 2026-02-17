const express = require('express');
const session = require('express-session');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const DATABASE_FILE = 'database.json';

// Налаштування
app.set('view engine', 'ejs');
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(session({
    secret: 'ukd_secret_key_6000_v3',
    resave: false,
    saveUninitialized: true
}));

// --- Робота з базою даних ---
const loadData = () => {
    try {
        if (!fs.existsSync(DATABASE_FILE)) {
            return { users: [], subjects: [], absences: [], creators: [] }; // Повертаємо пусту структуру, якщо файлу немає
        }
        const rawData = fs.readFileSync(DATABASE_FILE);
        const data = JSON.parse(rawData);
        
        // "Міграція" даних (як у Python версії)
        if (data.users) {
            data.users.forEach(u => {
                if (!u.email) u.email = `${u.username}@ukd.edu.ua`;
                if (!u.avatar) u.avatar = "https://cdn-icons-png.flaticon.com/512/354/354637.png";
                if (!u.room) u.room = "Не вказано";
            });
        }
        return data;
    } catch (err) {
        console.error("Помилка зчитування БД:", err);
        return { users: [], subjects: [], absences: [], creators: [] };
    }
};

const saveData = (data) => {
    fs.writeFileSync(DATABASE_FILE, JSON.stringify(data, null, 4), 'utf8');
};

// --- Маршрути (Routes) ---

// Головна сторінка
app.get('/', (req, res) => {
    const db = loadData();
    let userAbsences = [];
    let currentUser = null;

    if (req.session.user_id) {
        currentUser = db.users.find(u => u.id === req.session.user_id);

        if (currentUser) {
            // Фільтрація та об'єднання даних (JOIN logic)
            db.absences.forEach(a => {
                // Логіка доступу: Бачать адміни, вчителі АБО сам студент
                if (['ADMIN', 'TEACHER'].includes(req.session.role) || a.student_id === req.session.user_id) {
                    const subject = db.subjects.find(s => s.id === a.subject_id);
                    if (subject) {
                        const teacher = db.users.find(u => u.id === subject.teacher_id);
                        const student = db.users.find(u => u.id === a.student_id);

                        userAbsences.push({
                            id: a.id,
                            subject_name: subject.name || 'Невідомо',
                            teacher_name: teacher ? teacher.fullname : "Викладач",
                            teacher_email: teacher ? teacher.email : "-",
                            room: teacher ? teacher.room : "???",
                            student_name: student ? student.fullname : "Студент",
                            deadline: a.deadline || '2024-01-01T00:00'
                        });
                    }
                }
            });
        }
    }

    res.render('index', {
        session: req.session,
        currentUser: currentUser,
        user_absences: userAbsences,
        all_users: db.users,
        all_subjects: db.subjects,
        creators: db.creators || []
    });
});

// Логін
app.post('/login', (req, res) => {
    const db = loadData();
    const { email, pass } = req.body;
    
    // Пошук користувача
    const user = db.users.find(u => u.email === email && u.password === pass);

    if (user) {
        req.session.user_id = user.id;
        req.session.role = user.role;
        req.session.username = user.username;
        res.redirect('/');
    } else {
        res.redirect('/?error=login_failed');
    }
});

// Вихід
app.get('/logout', (req, res) => {
    req.session.destroy();
    res.redirect('/');
});

// API: Додати користувача
app.post('/api/add_user', (req, res) => {
    if (!['ADMIN', 'TEACHER'].includes(req.session.role)) return res.redirect('/');
    
    const db = loadData();
    const newUser = {
        id: db.users.length + 1,
        username: req.body.username,
        password: req.body.password,
        fullname: req.body.fullname,
        email: req.body.email,
        role: req.body.role,
        avatar: "https://cdn-icons-png.flaticon.com/512/354/354637.png",
        room: req.body.role === 'TEACHER' ? (req.body.room || '???') : 'Не вказано'
    };
    
    db.users.push(newUser);
    saveData(db);
    res.redirect('/?tab=admin');
});

// API: Додати "Н-ку" (Absence)
app.post('/api/add_absence', (req, res) => {
    if (!['ADMIN', 'TEACHER'].includes(req.session.role)) return res.redirect('/');

    const db = loadData();
    db.absences.push({
        id: db.absences.length + 1,
        student_id: parseInt(req.body.student_id),
        subject_id: parseInt(req.body.subject_id),
        deadline: req.body.deadline,
        status: "active"
    });
    
    saveData(db);
    res.redirect('/?tab=timers');
});

// API: Видалити (Відпрацювати)
app.get('/api/resolve/:id', (req, res) => {
    const db = loadData();
    const id = parseInt(req.params.id);
    db.absences = db.absences.filter(a => a.id !== id);
    saveData(db);
    res.json({ success: true });
});

// API: Оновити аватар
app.post('/api/update_avatar', (req, res) => {
    if (!req.session.user_id) return res.redirect('/');
    
    const db = loadData();
    const user = db.users.find(u => u.id === req.session.user_id);
    if (user) {
        user.avatar = req.body.url;
        saveData(db);
    }
    res.redirect('/?tab=profile');
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
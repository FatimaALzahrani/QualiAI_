from datetime import datetime
from flask import Flask, render_template,render_template_string, request, redirect, url_for, session, send_from_directory,abort,send_file
import firebase_admin
from firebase_admin import credentials, auth, firestore
import pandas as pd
from fpdf import FPDF
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import numpy as np
import os, uuid
import json
import plotly.graph_objs as go
from plotly.offline import plot
from tabulate import tabulate
import requests

from config import firebase_config

app = Flask(__name__)
app.secret_key = 'AIzaSyAr1hQK-pqmDlStxEScGJsXeLd3ZxabdhQ'

cred = credentials.Certificate("credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
print("✅ Firebase Initialized Successfully!")

UPLOAD_FOLDER = 'uploads'
REPORTS_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER

data_categories = {
    "عدد الطلاب المُخطط إلتحاقهم بالبرنامج": "عدد الطلاب المُخطط إلتحاقهم بالبرنامج",
    "العدد الكلي للطلاب الملتحقين بالبرنامج": "العدد الكلي للطلاب الملتحقين بالبرنامج",
    "عدد الطلاب الدوليين الملتحقين بالبرنامج": "عدد الطلاب الدوليين الملتحقين بالبرنامج",
    "متوسط عدد الطلاب في الشعب الدراسية": "متوسط عدد الطلاب في الشعب الدراسية",
    "نسبة عدد الطلاب لهيئة التدريس": "نسبة عدد الطلاب لهيئة التدريس"
}

FIREBASE_API_KEY = "AIzaSyABMZmTlio-nZ8sLJPSlDmB82mMD9Orb4M"

def login_with_password(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, json=payload)

    return response.json() if response.status_code == 200 else None

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            user_data = login_with_password(email, password)
            if user_data:
                user_info = auth.get_user_by_email(email)

                session["user_id"] = user_info.uid
                session["email"] = email

                return jsonify({"success": True, "message": "تم تسجيل الدخول بنجاح!", "type": "success"})
            else:
                return jsonify({"success": False, "message": "البريد الإلكتروني أو كلمة المرور غير صحيحة", "type": "error"})

        except firebase_admin.auth.UserNotFoundError:
            return jsonify({"success": False, "message": "البريد الإلكتروني غير مسجل.", "type": "error"})
        except Exception:
            return jsonify({"success": False, "message": "حدث خطأ أثناء تسجيل الدخول.", "type": "error"})

    return render_template("login.html")

@app.route("/forgot-password", methods=["GET"])
def forgot_password():
    return render_template("forgot_password.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        position = request.form["position"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        try:
            if len(username) < 3:
                return jsonify({"success": False, "message": "اسم المستخدم يجب أن يكون 3 أحرف على الأقل.", "type": "error"})
            if len(password) < 6:
                return jsonify({"success": False, "message": "كلمة المرور يجب أن تكون 6 أحرف على الأقل.", "type": "error"})
            if password != confirm_password:
                return jsonify({"success": False, "message": "كلمة المرور وتأكيدها غير متطابقين!", "type": "error"})
            if len(phone) != 10:
                return jsonify({"success": False, "message": "يجب أن يتكون رقم الهاتف من 10 أرقام", "type": "error"})

            user = auth.create_user(email=email, password=password)

            db.collection("users").document(user.uid).set({"username": username, "email": email, "phone":phone,"position":position})

            session["user_id"] = user.uid
            session["email"] = email

            return jsonify({"success": True, "message": "تم إنشاء الحساب بنجاح!", "type": "success"})

        except firebase_admin.auth.EmailAlreadyExistsError:
            return jsonify({"success": False, "message": "البريد الإلكتروني مسجل بالفعل.", "type": "error"})
        except Exception as e:
            return jsonify({"success": False, "message": "حدث خطأ أثناء إنشاء الحساب.", "type": "error"})

    return render_template("register.html")

@app.route('/logout')
def logout():
    session.pop('user_id', None)  
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    
    if not user_id:
        return redirect(url_for('login')) 

    user_ref = db.collection('users').document(user_id).get()
    if user_ref.exists:
        user_data = user_ref.to_dict()
    else:
        user_data = {}

    user_reports = []
    report_ids = user_data.get('reports', [])
    for report_id in report_ids:
        report_ref = db.collection('reports').document(report_id).get()
        if report_ref.exists:
            report = report_ref.to_dict()
            report['id'] = report_id 
            user_reports.append(report)

    return render_template('profile.html', user_data=user_data, user_reports=user_reports)

@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user_ref = db.collection('users').document(user_id)
    user_data = user_ref.get().to_dict()

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        position = request.form.get('position')

        updated_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'position': position
        }
        user_ref.update(updated_data)
        return redirect(url_for('profile'))  

    return render_template('update_profile.html', user_data=user_data)

UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
ALLOWED_EXTENSIONS = {'pdf', 'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

TOTAL_STEPS = 4

criteria = {
    "المعيار الأول: إدارة البرنامج وضمان جودته": "تفاصيل المعايير الفرعية...",
    "المعيار الثاني: التعليم والتعلم": "تفاصيل المعايير الفرعية...",
    "المعيار الثالث: الطلاب": "تفاصيل المعايير الفرعية...",
    "المعيار الرابع: هيئة التدريس": "تفاصيل المعايير الفرعية...",
    "المعيار الخامس: مصادر التعلم والتجهيزات": "تفاصيل المعايير الفرعية...",
    "المعيار السادس: البحوث العلمية والمشاريع": "تفاصيل المعايير الفرعية..."
}

STANDARDS_FILES = {
    "المعيار الأول: إدارة البرنامج وضمان جودته": [
        "سياسات الإدارة",
        "خطط التطوير",
        "نظام الجودة المؤسسي (إن وجد)",
        "أدلة وإجراءات تقييم الأداء"
    ],
    "المعيار الثاني: التعليم والتعلم": [
        "وصف البرنامج والمقررات",
        "نماذج تقويم الطلاب",
        "سياسات الاختبارات",
        "خطة تطوير المناهج"
    ],
    "المعيار الثالث: الطلاب": [
        "تقارير القبول والتسجيل",
        "دليل الخدمات الطلابية",
        "بيانات الخريجين",
        "خطط الأنشطة اللاصفية"
    ],
    "المعيار الرابع: هيئة التدريس": [
        "بيانات أعضاء هيئة التدريس",
        "برامج التطوير المهني",
        "معايير تقييم الأداء",
        "نماذج إنجازات البحث العلمي"
    ],
    "المعيار الخامس: مصادر التعلم والمرافق": [
        "قوائم مصادر التعلم",
        "تقارير صيانة المعامل والمرافق",
        "خطة السلامة والإخلاء",
        "إحصائيات استخدام مصادر التعلم"
    ],
    "المعيار السادس: البحوث العلمية والمشاريع": [
        "سياسات البحث العلمي",
        "تقارير مشاريع التخرج",
        "خطة تمويل الأنشطة البحثية",
        "أدلة وضوابط أخلاقيات البحث"
    ]
}


requirements_data = {
    1: {
        "title": "المعلومات الأساسية",
        "description": "يرجى تعبئة البيانات الأساسية للتقرير.",
        "allowed_extensions": []
    },
    2: {
        "title": "ملف البرنامج",
        "description": "يرجى تعبئة النقاط الخاصة بملف البرنامج ورفع الملفات الداعمة.",
        "allowed_extensions": list(ALLOWED_EXTENSIONS)
    },
    3: {
        "title": "الدراسة الذاتية للبرنامج",
        "description": "يرجى تعبئة الدراسة الذاتية للبرنامج.",
        "allowed_extensions": []
    },
    4: {
        "title": "التقويم الذاتي وفق معايير الاعتماد",
        "description": "يرجى تعبئة بيانات التقويم الذاتي ورفع الملفات الداعمة.",
        "allowed_extensions": list(ALLOWED_EXTENSIONS)
    }
}

def analyze_faculty_classification(data):
    fc = data.get('faculty_classify', {})
    analysis = {}
    for mode, mode_data in fc.items():
        analysis[mode] = {}
        for work_type, work_data in mode_data.items():
            sub_analysis = {}
            for sub_category, values in work_data.items():
                sub_analysis[sub_category] = values
            analysis[mode][work_type] = sub_analysis
    return analysis

def analyze_faculty(data):
    faculty_data = data.get('faculty', {})
    analysis = {}
    for category, positions in faculty_data.items():
        analysis[category] = {}
        for pos, counts in positions.items():
            male = counts.get('male', 0)
            female = counts.get('female', 0)
            total = counts.get('total', 0)
            perc_female = (female / total * 100) if total != 0 else 0
            diff = abs(male - female)
            analysis[category][pos] = {
                'male': male,
                'female': female,
                'total': total,
                'gender_gap': diff,
                'female_percentage': perc_female
            }
    return analysis

def analyze_students(data):
    students = data.get('students_table', {})
    analysis = {}
    
    total_students = students.get('العدد الكلي للطلاب الملتحقين بالبرنامج', {}).get('total', {})
    intl_students = students.get('عدد الطلاب الدوليين الملتحقين بالبرنامج', {}).get('total', {})
    ratio_trends = {}
    for year in total_students.keys():
        total = total_students.get(year, 1)
        intl = intl_students.get(year, 0)
        ratio_trends[year] = (intl / total) * 100
    analysis['intl_ratio_trends'] = ratio_trends
    
    teacher_ratio = students.get('نسبة عدد الطلاب لهيئة التدريس', {}).get('total', {})
    analysis['teacher_ratio'] = teacher_ratio

    avg_class_size = students.get('متوسط عدد الطلاب في الشعب الدراسية', {}).get('total', {})
    analysis['avg_class_size'] = avg_class_size

    return analysis

def analyze_enrollment(data):
    enrollment = data.get('enrollment_data', {})
    analysis = {}
    for mode, details in enrollment.items():
        total = details.get('الإجمالي', 0)
        saudi = details.get('سعودي', {})
        non_saudi = details.get('غير سعودي', {})
        analysis[mode] = {
            'total': total,
            'saudi_total': saudi.get('total', 0),
            'non_saudi_total': non_saudi.get('total', 0)
        }
    return analysis

def analyze_graduates(data):
    graduates_data = data.get('graduates_data', {})
    grad_counts = graduates_data.get('graduates', {})
    employment = graduates_data.get('employment', {})
    
    total_grad = 0
    count_grad_years = 0
    for year, counts in grad_counts.items():
        total_grad += counts.get('total', 0)
        count_grad_years += 1
    avg_graduates = total_grad / count_grad_years if count_grad_years else 0

    emp_rates = [details.get('employment_rate', 0) for details in employment.values()]
    avg_emp_rate = sum(emp_rates) / len(emp_rates) if emp_rates else 0

    return {
        'avg_graduates': avg_graduates,
        'avg_employment_rate': avg_emp_rate,
        'grad_years': grad_counts,
        'employment_details': employment
    }

def generate_recommendations(data):
    recommendations = {
        "نقاط القوة": [],
        "نقاط الضعف": [],
        "مجالات التحسين": []
    }
    
    fc_analysis = analyze_faculty_classification(data)
    if fc_analysis:
        recommendations["نقاط القوة"].append("تنوع أساليب التدريس (انتظام وعن بعد) يوفر خيارات متعددة تلبي احتياجات الطلاب.")
    
    faculty_analysis = analyze_faculty(data)
    if faculty_analysis.get('متوسط عبئ التدريس', {}).get('أستاذ', {}):
        prof = faculty_analysis['متوسط عبئ التدريس']['أستاذ']
        if prof['gender_gap'] > 20:
            recommendations["نقاط الضعف"].append(
                f"فجوة كبيرة في فئة 'أستاذ' (ذكور: {prof['male']}، إناث: {prof['female']}). نسبة الإناث {prof['female_percentage']:.1f}% تحتاج إلى تحسين."
            )
        else:
            recommendations["نقاط القوة"].append("توازن نسبي بين الجنسين في بعض فئات الكادر الأكاديمي.")
    
    students_analysis = analyze_students(data)
    intl_trends = students_analysis.get('intl_ratio_trends', {})
    current_intl_ratio = intl_trends.get('current_year', 0)
    if current_intl_ratio < 20:
        recommendations["نقاط الضعف"].append(
            f"نسبة الطلاب الدوليين للعام الحالي منخفضة ({current_intl_ratio:.1f}%) مما يؤثر على التنوع الدولي."
        )
    else:
        recommendations["نقاط القوة"].append("نسبة جيدة من الطلاب الدوليين تعزز البعد العالمي للبرنامج.")
    
    teacher_ratio = students_analysis.get('teacher_ratio', {}).get('current_year', 0)
    if teacher_ratio > 5:
        recommendations["نقاط الضعف"].append(
            f"ارتفاع نسبة الطلاب إلى هيئة التدريس (نسبة: {teacher_ratio}) قد يؤثر على جودة التفاعل والتدريس."
        )
        recommendations["مجالات التحسين"].append("زيادة عدد أعضاء هيئة التدريس أو تقسيم الفصول لتخفيف العبء.")
    else:
        recommendations["نقاط القوة"].append("نسبة مناسبة من الطلاب لكل عضو في هيئة التدريس.")
    
    enrollment_analysis = analyze_enrollment(data)
    for mode, stats in enrollment_analysis.items():
        ratio = (stats['non_saudi_total'] / stats['total']) if stats['total'] else 0
        if ratio < 0.25:
            recommendations["نقاط الضعف"].append(
                f"في وضع {mode}، نسبة الطلاب غير السعوديين ({stats['non_saudi_total']}) منخفضة مقارنة بالإجمالي ({stats['total']})."
            )
        else:
            recommendations["نقاط القوة"].append(
                f"توزيع جيد للطلاب بين الجنسيات في وضع {mode}."
            )
    
    grads_analysis = analyze_graduates(data)
    avg_emp_rate = grads_analysis.get('avg_employment_rate', 0)
    if avg_emp_rate < 65:
        recommendations["نقاط الضعف"].append(
            f"متوسط معدل توظيف الخريجين منخفض نسبياً ({avg_emp_rate:.1f}%) مما يستدعي تحسين آليات الإعداد لسوق العمل."
        )
        recommendations["مجالات التحسين"].append("تعزيز برامج التوجيه والتواصل مع سوق العمل لتطوير فرص توظيف الخريجين.")
    else:
        recommendations["نقاط القوة"].append(
            f"معدل توظيف جيد للخريجين بمتوسط {avg_emp_rate:.1f}% يدل على فعالية البرنامج."
        )

    recommendations["مجالات التحسين"].append("تطوير استراتيجيات واضحة لتعزيز التوازن بين الجنسين وتوفير برامج تطوير مهني مستمرة.")
    recommendations["مجالات التحسين"].append("تحسين المناهج الدراسية وربطها بمتطلبات سوق العمل والتكنولوجيا الحديثة.")
    
    return recommendations

def export_report(report, filename="academic_report.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
    print(f"تم تصدير التقرير إلى {filename}")


def calculate_kpi(data):
    kpis = [
        {
            "indicator": "معدل النمو في عدد الخريجين",
            "actual": round(((data['graduates_data']['graduates']['العام الماضي']['total'] - 
                              data['graduates_data']['graduates']['قبل عامين']['total']) /
                              data['graduates_data']['graduates']['قبل عامين']['total']) * 100, 2),
            "target": 0,
            "internal_ref": -3,
            "external_ref": -2
        },
        {
            "indicator": "متوسط نسبة التوظيف بعد التخرج",
            "actual": round(data['graduates_data']['employment']['العام الماضي']['employment_rate'], 2),
            "target": 70,
            "internal_ref": 65,
            "external_ref": 75
        },
        {
            "indicator": "نسبة الطلاب الدوليين من الإجمالي",
            "actual": round((data['students_table']['عدد الطلاب الدوليين الملتحقين بالبرنامج']['total']['current_year'] / 
                             data['students_table']['العدد الكلي للطلاب الملتحقين بالبرنامج']['total']['current_year']) * 100, 2),
            "target": 10,
            "internal_ref": 8,
            "external_ref": 12
        },
        {
            "indicator": "نسبة عدد الطلاب لهيئة التدريس",
            "actual": round(data['students_table']['نسبة عدد الطلاب لهيئة التدريس']['total']['current_year'], 2),
            "target": 3.0,
            "internal_ref": 2.8,
            "external_ref": 3.5
        }
    ]
    return kpis

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/report', methods=['GET'])
def report():    
    user_id = session['user_id']
    session.clear()
    session['user_id'] = user_id
    session['data'] = {}
    session['files'] = {}
    return redirect(url_for('step', step_number=1))

@app.route('/step/<int:step_number>', methods=['GET', 'POST'])
def step(step_number):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if step_number < 1 or step_number > TOTAL_STEPS:
        return redirect(url_for('index'))
    
    data = session.get('data', {})
    files_data = session.get('files', {})
    recommendations = {
    "نقاط القوة": [],
    "نقاط الضعف": [],
    "مجالات التحسين": []
}

    user_id = session.get('user_id')
    user = db.collection('users').document(user_id).get().to_dict()

    data['contactName'] = user.get('username', 'غير محدد')
    data['position'] = user.get('position', 'غير محدد')
    data['email'] = user.get('email', 'غير محدد')
    data['phone'] = user.get('phone', 'غير محدد')
    data['reportDate'] = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        if step_number == 1:
            data['institution'] = request.form.get('institution')
            data['college'] = request.form.get('college')
            data['department'] = request.form.get('department')
            data['program'] = request.form.get('program')
            data['title'] = request.form.get('title')

        elif step_number == 2:
            fields = [
                'program_message', 'program_objectives', 'program_achievements',
                'program_hours', 'program_tracks', 'program_qualification',
                'program_progress', 'stats_students', 'stats_enrollment',
                'stats_graduates', 'stats_additional', 'stats_metrics', 'stats_ratio'
            ]
            

            for field in fields:
                data[field] = request.form.get(field, "").strip()

            track_count = int(request.form.get("program_tracks_count", 1) or 1)
            qual_count = int(request.form.get("program_qualification_count", 1) or 1)

            data['program_tracks'] = [
                {
                    "name": request.form.get(f"track_name_{i}", "").strip(),
                    "hours": int(request.form.get(f"track_hours_{i}", "0") or 0)
                }
                for i in range(1, track_count + 1)
            ]

            data['program_qualification'] = [
                {
                    "name": request.form.get(f"qualification_name_{i}", "").strip(),
                    "hours": int(request.form.get(f"qualification_hours_{i}", "0") or 0)
                }
                for i in range(1, qual_count + 1)
            ]

            uploaded_files = request.files.getlist('excel_students')
            saved_files = []
            students_data = []

            for file in uploaded_files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    saved_files.append({"name": filename, "path": file_path})

                    try:
                        df = pd.read_excel(file_path) 
                        students_data.extend(df.to_dict(orient='records'))  
                        print(f"✅ تم تحميل بيانات الطلاب من {filename} بنجاح")
                    except Exception as e:
                        print(f"❌ خطأ أثناء قراءة ملف Excel: {e}")

            df = pd.DataFrame(students_data)

            df["الفئة"].fillna(method="ffill", inplace=True)

            def safe_convert(value):
                try:
                    value = str(value).strip()
                    return float(value) if value.replace('.', '', 1).isdigit() else 0
                except ValueError:
                    return 0

            columns_to_convert = ["قبل عامين", "العام الماضي", "العام الحالي", "المُتوقع بعد عام"]
            for col in columns_to_convert:
                df[col] = df[col].apply(safe_convert)

            faculty_row = df[df["الفئة"].str.strip() == "إجمالي هيئة التدريس"]
            faculty_counts = {
                "two_years": faculty_row["قبل عامين"].sum(),
                "last_year": faculty_row["العام الماضي"].sum(),
                "current_year": faculty_row["العام الحالي"].sum(),
                "next_year": faculty_row["المُتوقع بعد عام"].sum(),
            }

            students_table = {}

            for _, row in df.iterrows():
                category = row["الفئة"].strip()
                gender = row["النوع"].strip()

                if category == "إجمالي هيئة التدريس":
                    continue 

                if category not in students_table:
                    students_table[category] = {"male": {}, "female": {}, "total": {}}

                values = {
                    "two_years": row["قبل عامين"],
                    "last_year": row["العام الماضي"],
                    "current_year": row["العام الحالي"],
                    "next_year": row["المُتوقع بعد عام"]
                }

                if gender == "ذكور":
                    students_table[category]["male"] = values
                elif gender == "إناث":
                    students_table[category]["female"] = values

            for category, values in students_table.items():
                male_vals = values.get("male", {})
                female_vals = values.get("female", {})

                total = {
                    "two_years": male_vals.get("two_years", 0) + female_vals.get("two_years", 0),
                    "last_year": male_vals.get("last_year", 0) + female_vals.get("last_year", 0),
                    "current_year": male_vals.get("current_year", 0) + female_vals.get("current_year", 0),
                    "next_year": male_vals.get("next_year", 0) + female_vals.get("next_year", 0)
                }
                students_table[category]["total"] = total

           
            students_table["نسبة عدد الطلاب لهيئة التدريس"] = {
                "male": {
                    year: round(students_table["العدد الكلي للطلاب الملتحقين بالبرنامج"]["male"].get(year, 0) / faculty_counts.get(year, 1), 2)
                    if faculty_counts.get(year, 0) > 0 else "غير متوفر"
                    for year in ["two_years", "last_year", "current_year", "next_year"]
                },
                "female": {
                    year: round(students_table["العدد الكلي للطلاب الملتحقين بالبرنامج"]["female"].get(year, 0) / faculty_counts.get(year, 1), 2)
                    if faculty_counts.get(year, 0) > 0 else "غير متوفر"
                    for year in ["two_years", "last_year", "current_year", "next_year"]
                },
                "total": {
                    year: round(students_table["العدد الكلي للطلاب الملتحقين بالبرنامج"]["total"].get(year, 0) / faculty_counts.get(year, 1), 2)
                    if faculty_counts.get(year, 0) > 0 else "غير متوفر"
                    for year in ["two_years", "last_year", "current_year", "next_year"]
                }
            }
            data["students_table"] = students_table
      
            if "excel_enrollment" in request.files:
                file = request.files["excel_enrollment"]
                if file.filename.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(file, header=None)
                    
                    df = df.fillna(0)

                    enrollment_data = {
                        "انتظام": {
                             "سعودي": {
                                "male": int(df.iloc[3, 2] if pd.notna(df.iloc[3, 2]) else 0),
                                "female": int(df.iloc[3, 3] if pd.notna(df.iloc[3, 3]) else 0), 
                                "total": int(df.iloc[3, 2] + df.iloc[3, 3] if pd.notna(df.iloc[3, 3]) and pd.notna(df.iloc[3, 2]) else 0)
                            },
                            "غير سعودي": {
                                "male": int(df.iloc[3, 4] if pd.notna(df.iloc[3, 4]) else 0), 
                                "female": int(df.iloc[3, 5] if pd.notna(df.iloc[3, 5]) else 0), 
                                "total": int(df.iloc[3, 4] + df.iloc[3, 5] if pd.notna(df.iloc[3, 4]) and pd.notna(df.iloc[3, 5]) else 0)
                            },
                            "الإجمالي": (int(df.iloc[3, 4] + df.iloc[3, 5] if pd.notna(df.iloc[3, 4]) and pd.notna(df.iloc[3, 5]) else 0))+(int(df.iloc[3, 2] + df.iloc[3, 3] if pd.notna(df.iloc[3, 3]) and pd.notna(df.iloc[3, 2]) else 0))
                        },
                        "تعليم عن بعد": {
                            "سعودي": {
                                "male": int(df.iloc[4, 2] if pd.notna(df.iloc[4, 2]) else 0),
                                "female": int(df.iloc[4, 3] if pd.notna(df.iloc[4, 3]) else 0), 
                                "total": int(df.iloc[4, 2] + df.iloc[4, 3] if pd.notna(df.iloc[4, 3]) and pd.notna(df.iloc[4, 2]) else 0)
                            },
                            "غير سعودي": {
                                "male": int(df.iloc[4, 4] if pd.notna(df.iloc[4, 4]) else 0), 
                                "female": int(df.iloc[4, 5] if pd.notna(df.iloc[4, 5]) else 0), 
                                "total": int(df.iloc[4, 4] + df.iloc[4, 5] if pd.notna(df.iloc[4, 4]) and pd.notna(df.iloc[4, 5]) else 0)
                            },
                            "الإجمالي": (int(df.iloc[4, 4] + df.iloc[4, 5] if pd.notna(df.iloc[4, 4]) and pd.notna(df.iloc[4, 5]) else 0))+(int(df.iloc[4, 2] + df.iloc[4, 3] if pd.notna(df.iloc[4, 3]) and pd.notna(df.iloc[4, 2]) else 0))
                        },
                    }

                    data['enrollment_data'] =enrollment_data

            if "excel_graduates" in request.files:
                file = request.files["excel_graduates"]
                if file.filename.endswith((".xlsx", ".xls")):
                    graduates = pd.read_excel(file, header=None)
            
                    graduates_data = {
                        "graduates": {
                            "قبل ثلاثة أعوام": {
                                "male": int(graduates.iloc[2, 1]),
                                "female": int(graduates.iloc[3, 1]),
                                "total": int(graduates.iloc[2, 1]) + int(graduates.iloc[3, 1]),
                            },
                            "قبل عامين": {
                                "male": int(graduates.iloc[3, 2]),
                                "female": int(graduates.iloc[3, 2]),
                                "total": int(graduates.iloc[3, 2]) + int(graduates.iloc[2, 2]),
                            },
                            "العام الماضي": {
                                "male": int(graduates.iloc[2, 3]),
                                "female": int(graduates.iloc[3, 3]),
                                "total": int(graduates.iloc[3, 3]) + int(graduates.iloc[2, 3]),
                            },
                        },
                        "employment": {
                            "قبل ثلاثة أعوام": {
                                "employees": int(graduates.iloc[5, 1]),
                                "employment_rate": round((int(graduates.iloc[5, 1])/(int(graduates.iloc[3, 1]) + int(graduates.iloc[2, 1])))*100,2),
                            },
                            "قبل عامين": {
                                "employees": int(graduates.iloc[5, 2]),
                                "employment_rate": round((int(graduates.iloc[5, 2])/(int(graduates.iloc[3, 2]) + int(graduates.iloc[2, 2])))*100,2),
                            },
                            "العام الماضي": {
                                "employees": int(graduates.iloc[5, 3]),
                                "employment_rate": round((int(graduates.iloc[5, 3])/(int(graduates.iloc[2, 3]) + int(graduates.iloc[2, 3])))*100,2),
                            },
                        },
                }
                    data['graduates_data'] = graduates_data
            
            if "excel_faculty" in request.files:
                file = request.files["excel_faculty"]
                if file.filename.endswith((".xlsx", ".xls")):
                    faculty = pd.read_excel(file, header=None)
            
                    faculty_data = {
                        "سعودي": {
                            "أستاذ": {
                                "male": int(faculty.iloc[2, 2]),
                                "female": int(faculty.iloc[2, 3]),
                                "total": int(faculty.iloc[2, 2]) + int(faculty.iloc[2, 3]),
                            },
                            "أستاذ مشارك": {
                                "male": int(faculty.iloc[3, 2]),
                                "female": int(faculty.iloc[3, 3]),
                                "total": int(faculty.iloc[3, 2]) + int(faculty.iloc[3, 3]),
                            },
                            "أستاذ مساعد":
                            {
                            "male": int(faculty.iloc[4, 2]),
                            "female": int(faculty.iloc[4, 3]),
                            "total": int(faculty.iloc[4, 2]) + int(faculty.iloc[4, 3]),
                            },
                            "الإجمالي":{
                            "male": int(faculty.iloc[2, 2]) + int(faculty.iloc[3, 2]) + int(faculty.iloc[4, 2]),
                            "female": int(faculty.iloc[2, 3]) + int(faculty.iloc[3, 3]) + int(faculty.iloc[4, 3]),
                            "total": (int(faculty.iloc[2, 2]) + int(faculty.iloc[3, 2]) + int(faculty.iloc[4, 2]))+(int(faculty.iloc[2, 3]) + int(faculty.iloc[3, 3]) + int(faculty.iloc[4, 3])),
                            }
                        },
                        "غير سعودي": {
                            "أستاذ": {
                                "male": int(faculty.iloc[2, 4]),
                                "female": int(faculty.iloc[2, 5]),
                                "total": int(faculty.iloc[2, 4]) + int(faculty.iloc[2, 5]),
                            },
                            "أستاذ مشارك": {
                                "male": int(faculty.iloc[3, 4]),
                                "female": int(faculty.iloc[3, 5]),
                                "total": int(faculty.iloc[3, 4]) + int(faculty.iloc[3, 5]),
                            },
                            "أستاذ مساعد": {
                                "male": int(faculty.iloc[4, 4]),
                                "female": int(faculty.iloc[4, 5]),
                                "total": int(faculty.iloc[4, 4]) + int(faculty.iloc[4, 5]),
                            },
                            "الإجمالي":{
                                "male": int(faculty.iloc[2, 4]) + int(faculty.iloc[3, 4]) + int(faculty.iloc[4, 4]),
                                "female": int(faculty.iloc[2, 5]) + int(faculty.iloc[3, 5]) + int(faculty.iloc[4, 5]),
                                "total": (int(faculty.iloc[2, 4]) + int(faculty.iloc[3, 4]) + int(faculty.iloc[4, 4]))+(int(faculty.iloc[2, 5]) + int(faculty.iloc[3, 5]) + int(faculty.iloc[4, 5])),
                            }
                        },
                        "متوسط عبئ التدريس": {
                            "أستاذ": {
                                "male": int(faculty.iloc[2, 6]),
                                "female": int(faculty.iloc[2, 7]),
                                "total": int(faculty.iloc[2, 6]) + int(faculty.iloc[2, 7]),
                            },
                            "أستاذ مشارك": {
                                "male": int(faculty.iloc[3, 6]),
                                "female": int(faculty.iloc[3, 7]),
                                "total": int(faculty.iloc[3, 6]) + int(faculty.iloc[3, 7]),
                            },
                            "أستاذ مساعد":{
                                "male": int(faculty.iloc[4, 6]),
                                "female": int(faculty.iloc[4, 7]),
                                "total": int(faculty.iloc[4, 6]) + int(faculty.iloc[4, 7]),
                            },
                            "الإجمالي":{
                                "male": int(faculty.iloc[2, 6]) + int(faculty.iloc[3, 6]) + int(faculty.iloc[4, 6]),
                                "female": int(faculty.iloc[2, 7]) + int(faculty.iloc[3, 7]) + int(faculty.iloc[4, 7]),
                                "total": (int(faculty.iloc[2, 6]) + int(faculty.iloc[3, 6]) + int(faculty.iloc[4, 6]))+(int(faculty.iloc[2, 7]) + int(faculty.iloc[3, 7]) + int(faculty.iloc[4, 7])),
                            }
                        },
                }
                    data['faculty'] = faculty_data
              
            if "excel_faculty_classify" in request.files:
                file = request.files["excel_faculty_classify"]
                if file.filename.endswith((".xlsx", ".xls")):
                    faculty_classify = pd.read_excel(file, header=None)
            
                    faculty_classify_data = {
                        "انتظام": {
                            "بدوام كامل": {
                                "male": int(faculty_classify.iloc[3, 1]),
                                "female": int(faculty_classify.iloc[4, 1]),
                                "total": int(faculty_classify.iloc[3, 1]) + int(faculty_classify.iloc[4, 1]),
                            },
                            "بدوام جزئي": {
                                "العدد":
                                {
                                "male": int(faculty_classify.iloc[3, 2]),
                                "female": int(faculty_classify.iloc[4, 2]),
                                "total": int(faculty_classify.iloc[3, 2]) + int(faculty_classify.iloc[4, 2]),
                                },
                                "ما يعادله":
                                {
                                "male": int(faculty_classify.iloc[3, 3]),
                                "female": int(faculty_classify.iloc[4, 3]),
                                "total": int(faculty_classify.iloc[3, 3]) + int(faculty_classify.iloc[4, 3]),
                                },
                            },
                        },
                        "عن بعد": {
                            "بدوام كامل": {
                                "male": int(faculty_classify.iloc[3, 4]),
                                "female": int(faculty_classify.iloc[4, 4]),
                                "total": int(faculty_classify.iloc[4, 4]) + int(faculty_classify.iloc[3, 4]),
                            },
                            "بدوام جزئي": {
                                "العدد":
                                {
                                "male": int(faculty_classify.iloc[3, 5]),
                                "female": int(faculty_classify.iloc[4, 5]),
                                "total": int(faculty_classify.iloc[3, 5]) + int(faculty_classify.iloc[4, 5]),
                                },
                                "ما يعادله":
                                {
                                "male": int(faculty_classify.iloc[3, 6]),
                                "female": int(faculty_classify.iloc[4, 6]),
                                "total": int(faculty_classify.iloc[3, 6]) + int(faculty_classify.iloc[4, 6]),
                                },
                            },
                        }
                }
                    data['faculty_classify'] = faculty_classify_data
                        
            # NAVY = "#001f3f"  
            # GOLD = "#FFD700"  

            # def get_faculty_distribution_div(faculty_analysis, category='متوسط عبئ التدريس'):
            #     if category not in faculty_analysis:
            #         return ""
            #     positions = faculty_analysis[category]
            #     labels = list(positions.keys())
            #     male_counts = [positions[pos]['male'] for pos in labels]
            #     female_counts = [positions[pos]['female'] for pos in labels]

            #     trace1 = go.Bar(x=labels, y=male_counts, name='ذكور', marker=dict(color=NAVY))
            #     trace2 = go.Bar(x=labels, y=female_counts, name='إناث', marker=dict(color=GOLD))

            #     layout = go.Layout(
            #         title=f'توزيع الكادر الأكاديمي - {category}',
            #         barmode='group',
            #         xaxis=dict(title='الرتب الأكاديمية'),
            #         yaxis=dict(title='عدد الأفراد')
            #     )

            #     fig = go.Figure(data=[trace1, trace2], layout=layout)
            #     return fig.to_html(full_html=False)

            # def get_student_intl_ratio_div(intl_ratio_trends):
            #     if not intl_ratio_trends:
            #         return ""
            #     years = list(intl_ratio_trends.keys())
            #     ratios = [intl_ratio_trends[year] for year in years]
            #     trace = go.Scatter(x=years, y=ratios, mode='lines+markers', line=dict(color=NAVY, width=2), marker=dict(color=GOLD))
            #     layout = go.Layout(
            #         title='اتجاه نسبة الطلاب الدوليين',
            #         xaxis=dict(title='السنوات'),
            #         yaxis=dict(title='نسبة الطلاب الدوليين (%)'),
            #         template='plotly_dark'
            #     )
            #     fig = go.Figure(data=[trace], layout=layout)
            #     div = plot(fig, output_type="div", include_plotlyjs=False)
            #     return div

            # def get_employment_rate_div(employment_details):
                # if not employment_details:
                #     return ""
                # years = list(employment_details.keys())
                # rates = [employment_details[year]['employment_rate'] for year in years]
                # trace = go.Bar(x=years, y=rates, marker=dict(color=GOLD, line=dict(color=NAVY, width=1.5)))
                # layout = go.Layout(
                #     title='معدلات التوظيف للخريجين',
                #     xaxis=dict(title='السنوات'),
                #     yaxis=dict(title='معدل التوظيف (%)'),
                #     template='plotly_dark'
                # )
                # fig = go.Figure(data=[trace], layout=layout)
                # div = plot(fig, output_type="div", include_plotlyjs=False)
                # return div
            
            fc_result = analyze_faculty_classification(data)
            faculty_result = analyze_faculty(data)
            students_result = analyze_students(data)
            enrollment_result = analyze_enrollment(data)
            graduates_result = analyze_graduates(data)
            recommendations = generate_recommendations(data)

            # faculty_graph_div = get_faculty_distribution_divte(faculty_result, category='متوسط عبئ التدريس')
            # student_intl_div = get_student_intl_ratio_div(students_result.get('intl_ratio_trends', {}))
            # employment_div = get_employment_rate_div(graduas_result.get('employment_details', {}))

            recommendations = generate_recommendations(data)

            data["recommendations"] = recommendations
            # data["faculty_graph_div"] = faculty_graph_div
            # data["student_intl_div"] = student_intl_div
            # data["employment_div"] = employment_div

              
            data['kpis_row'] = calculate_kpi(data)  

        elif step_number == 3:
          indicators = request.form.getlist("indicator[]")
          actuals = request.form.getlist("actual[]")
          targets = request.form.getlist("target[]")
          internal_refs = request.form.getlist("internal_ref[]")
          external_refs = request.form.getlist("external_ref[]")

          new_kpis = []
          for i in range(len(indicators)):
              new_kpi = {
                  "indicator": indicators[i],
                  "actual": float(actuals[i]) if actuals[i] else 0.0,
                  "target": float(targets[i]) if targets[i] else 0.0,
                  "internal_ref": float(internal_refs[i]) if internal_refs[i] else 0.0,
                  "external_ref": float(external_refs[i]) if external_refs[i] else 0.0,
              }
              new_kpis.append(new_kpi)

          data['kpis'] = new_kpis

        elif step_number == 4:
            for idx in range(1, len(criteria)+1):
                data[f"evaluation_{idx}"] = request.form.get(f"evaluation_{idx}")
                data[f"strengths_{idx}"] = request.form.get(f"strengths_{idx}")
                data[f"improvements_{idx}"] = request.form.get(f"improvements_{idx}")
            uploaded_files = request.files.getlist('criteria_files')
            saved_files = []
            for file in uploaded_files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    saved_files.append({"name": filename, "type": filename.rsplit('.',1)[1].lower(), "path": file_path})
            files_data['criteria_files'] = saved_files

            for i in range(1, 7):
                field_name = f"files_{i}"
                uploaded_files = request.files.getlist(field_name)
                for file in uploaded_files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)

            for i in range(1, 7):
                comment_name = f"comments_{i}"
                comment_value = request.form.get(comment_name)
                session['data'][comment_name] = comment_value
        
        session['data'] = data
        session['files'] = files_data

        if step_number < TOTAL_STEPS:
              return redirect(url_for('step', step_number=step_number+1))
        else:
            return redirect(url_for('create_final_report'))
      
    if request.method == 'GET' and step_number == TOTAL_STEPS:
        return render_template('step.html',
                               step_number=step_number,
                               total_steps=TOTAL_STEPS,
                               data=data,
                               standards_files=STANDARDS_FILES)
    
    return render_template('step.html', total_steps=TOTAL_STEPS, step_number=step_number, criteria=criteria, data=data,recommendations=recommendations)

@app.route('/final_report', methods=['GET', 'POST'])
def create_final_report():
    if request.method == 'GET':
        session.pop('report_id', None) 

        report_id = session.get('report_id')
        if report_id:
            return redirect(url_for('view_final_report', report_id=report_id))

        data = session.get('data', {})

        files_data = session.get('files', {})

        report_content = render_template('report_content.html', data=data)
        report_id = str(uuid.uuid4()) 
        session['report_id'] = report_id 

        shareable_link = url_for('view_final_report', report_id=report_id, _external=True)
        user_id = session.get('user_id')
        user_data = {}
        if user_id:
            user_ref = db.collection('users').document(user_id).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
        
        report_doc = {
            "report_content": report_content,
            "data": data,
            "files_data": files_data,
            "user_id": user_id,
            "user": user_data,
            "created_at": firestore.SERVER_TIMESTAMP,
            "shareable_link": shareable_link
        }
        db.collection('reports').document(report_id).set(report_doc)
        if user_id:
            db.collection('users').document(user_id).update({
                "reports": firestore.ArrayUnion([report_id])
            })
        
        return redirect(url_for('view_final_report', report_id=report_id))

@app.route('/final_report/<report_id>')
def view_final_report(report_id):
    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get()

    if not doc.exists:
        abort(404, description="التقرير غير موجود")
    report_data = doc.to_dict()
    data = report_data.get("data", {})

    if isinstance(data.get("program_qualification"), str):
      data["program_qualification"] = json.loads(data["program_qualification"])

    if isinstance(data.get("program_tracks"), str):
      data["program_tracks"] = json.loads(data["program_tracks"])

    report_content = render_template('report_content.html', data=data)
    return render_template('final_report.html', report_content=report_content, report_id=report_id, data=data)

@app.route('/edit_report/<report_id>', methods=['GET'])
def edit_report(report_id):
    current_user_id = session.get('user_id')

    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return render_template('error.html', message="التقرير غير موجود!")

    report_data = doc.to_dict() or {}
    owner_id = report_data.get("user_id")

    if current_user_id != owner_id:
        return render_template('error.html', message="ليس لديك صلاحية لتعديل هذا التقرير!", redirect_url=request.referrer or url_for('home'))
    
    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        abort(404, description="التقرير غير موجود")
    
    report_data = doc.to_dict() or {} 
    data = report_data.get("data", {})  

    if not isinstance(data, dict):
        data = {}

    for key in ["program_qualification", "program_tracks"]:
        if isinstance(data.get(key), str):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                data[key] = []  

    graduates_data = data.get("graduates_data", {"graduates": {}, "employment": {}})
    faculty_data = data.get("faculty", {"سعودي": {}, "غير سعودي": {}, "متوسط عبئ التدريس": {}})

    return render_template('edit_report.html', report=data, report_id=report_id,categories=data_categories, graduates_data=graduates_data,faculty_data=faculty_data)

@app.route('/update_report/<report_id>', methods=['POST'])
def update_report(report_id):
    form_data = request.form.to_dict()

    if not form_data:
        return redirect(url_for('edit_report', report_id=report_id))

    doc_ref = db.collection('reports').document(report_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return redirect(url_for('edit_report', report_id=report_id))

    report_data = doc.to_dict()
    data = report_data.get('data', {})

    entities = request.form.getlist('entity[]')
    reasons = request.form.getlist('reason[]')
    comparison_entities = [{"entity": e, "reason": r} for e, r in zip(entities, reasons)]
    data["comparison_entities"] = comparison_entities

    indicators = request.form.getlist("indicator[]")
    actuals = request.form.getlist("actual[]")
    targets = request.form.getlist("target[]")
    internal_refs = request.form.getlist("internal_ref[]")
    external_refs = request.form.getlist("external_ref[]")

    kpis = []
    for i in range(len(indicators)):
        kpi = {
            "indicator": indicators[i],
            "actual": float(actuals[i]) if actuals[i] else 0.0,
            "target": float(targets[i]) if targets[i] else 0.0,
            "internal_ref": float(internal_refs[i]) if internal_refs[i] else 0.0,
            "external_ref": float(external_refs[i]) if external_refs[i] else 0.0,
        }
        kpis.append(kpi)
    data["kpis"] = kpis

    students_table = data.get("students_table", {})
    enrollment_data = data.get("enrollment_data", {})
    graduates_data = data.get("graduates_data", {"graduates": {}, "employment": {}})
    faculty_data = data.get("faculty", {"سعودي": {}, "غير سعودي": {}, "متوسط عبئ التدريس": {}})
    faculty_classify = data.get("faculty_classify", {"انتظام": {}, "عن بعد": {}})

    for field, value in form_data.items():
        keys = field.split("[")
        keys = [k.strip("]") for k in keys]

        if len(keys) == 4 and keys[0] == "students_table":
            _, category, gender, year = keys
            students_table.setdefault(category, {}).setdefault(gender, {})[year] = float(value)

        elif len(keys) == 4 and keys[0] == "enrollment_data":
            _, category, nationality, gender = keys
            enrollment_data.setdefault(category, {}).setdefault(nationality, {})[gender] = float(value)

        elif len(keys) == 4 and keys[0] == "graduates_data":
            _, section, year, gender = keys
            if section == "graduates":
                graduates_data["graduates"].setdefault(year, {})[gender] = int(value)
            elif section == "employment" and gender == "employees":
                graduates_data["employment"].setdefault(year, {})["employees"] = int(value)

        elif keys[0] == "faculty":
            _, category, rank, gender = keys
            try:
                faculty_data.setdefault(category, {}).setdefault(rank, {})[gender] = int(value) if value.strip() else 0
            except ValueError:
                faculty_data.setdefault(category, {}).setdefault(rank, {})[gender] = 0

        elif keys[0] == "faculty_classify":
          if len(keys) == 5:
              category, work_type, sub_category, gender = keys[1:]

              if category not in faculty_classify:
                  faculty_classify[category] = {}

              if work_type not in faculty_classify[category]:
                  faculty_classify[category][work_type] = {}

              if sub_category not in faculty_classify[category][work_type]:
                  faculty_classify[category][work_type][sub_category] = {"female": 0, "male": 0, "total": 0}

              try:
                  faculty_classify[category][work_type][sub_category][gender] = int(value) if value.strip() else 0
              except ValueError:
                  faculty_classify[category][work_type][sub_category][gender] = 0

              faculty_classify[category][work_type][sub_category]["total"] = (
                  faculty_classify[category][work_type][sub_category].get("female", 0) +
                  faculty_classify[category][work_type][sub_category].get("male", 0)
              )

          elif len(keys) == 4:
              category, work_type, gender = keys[1:]

              if category not in faculty_classify:
                  faculty_classify[category] = {}

              if work_type not in faculty_classify[category]:
                  faculty_classify[category][work_type] = {"female": 0, "male": 0, "total": 0}

              try:
                  faculty_classify[category][work_type][gender] = int(value) if value.strip() else 0
              except ValueError:
                  faculty_classify[category][work_type][gender] = 0

              faculty_classify[category][work_type]["total"] = (
                  faculty_classify[category][work_type].get("female", 0) +
                  faculty_classify[category][work_type].get("male", 0)
              )

          else:
              print(f"⚠️ بنية المفتاح غير متوقعة: {keys}")
              continue


    for category in faculty_data:
        for rank in faculty_data[category]:
            male = faculty_data[category][rank].get("male", 0)
            female = faculty_data[category][rank].get("female", 0)
            faculty_data[category][rank]["total"] = male + female

    for year in graduates_data["graduates"]:
        male = graduates_data["graduates"][year].get("male", 0)
        female = graduates_data["graduates"][year].get("female", 0)
        total = male + female
        graduates_data["graduates"][year]["total"] = total

        employees = graduates_data["employment"].get(year, {}).get("employees", 0)
        employment_rate = (employees / total * 100) if total > 0 else 0
        graduates_data["employment"].setdefault(year, {})["employment_rate"] = round(employment_rate, 2)

    data["students_table"] = students_table
    data["enrollment_data"] = enrollment_data
    data["graduates_data"] = graduates_data
    data["faculty"] = faculty_data 
    data["faculty_classify"] = faculty_classify

    recommendations = generate_recommendations(data)
    data["recommendations"] = recommendations

    try:
        doc_ref.update({
            'data': data,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        print("✅ تم التحديث بنجاح!")
    except Exception as e:
        print("❌ خطأ أثناء التحديث في Firestore:", e)

    return redirect(url_for('view_final_report', report_id=report_id))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(host="0.0.0.0", port=port, debug=True)
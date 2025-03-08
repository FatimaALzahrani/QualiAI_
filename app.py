from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory,abort,send_file
import firebase_admin
from firebase_admin import credentials, auth, firestore
import pandas as pd
from fpdf import FPDF
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import numpy as np
# from sentence_transformers import SentenceTransformer
# from llama_cpp import Llama
import faiss
import os, uuid
import uuid

app = Flask(__name__)
app.secret_key = 'AIzaSyAr1hQK-pqmDlStxEScGJsXeLd3ZxabdhQ'

cred = credentials.Certificate("credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

UPLOAD_FOLDER = 'uploads'
REPORTS_FOLDER = 'reports'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        try:
            user = auth.create_user(email=email, password=password)
            db.collection('users').document(user.uid).set({
                'username': username,
                'email': email
            })
            session['user_id'] = user.uid  
            return redirect(url_for('report')) 
        except Exception as e:
            return f"حدث خطأ أثناء التسجيل: {str(e)}"
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid 
            return redirect(url_for('report'))  
        except Exception as e:
            return f"فشل تسجيل الدخول: {str(e)}"
    
    return render_template('login.html')

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
        bio = request.form.get('bio')

        updated_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'bio': bio
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

# دالة للتأكد من صلاحية الملفات
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/report', methods=['GET'])
def report():
    # if 'user_id' not in session:
    #     return redirect(url_for('login'))
    
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

    if request.method == 'POST':
        if step_number == 1:
            data['title'] = request.form.get('title')
            data['institution'] = request.form.get('institution')
            data['college'] = request.form.get('college')
            data['department'] = request.form.get('department')
            data['program'] = request.form.get('program')
            data['reportDate'] = request.form.get('reportDate')
            data['contactName'] = request.form.get('contactName')
            data['position'] = request.form.get('position')
            data['email'] = request.form.get('email')
            data['phone'] = request.form.get('phone')
        elif step_number == 2:
            data['program_message'] = request.form.get('program_message')
            data['program_objectives'] = request.form.get('program_objectives')
            data['program_achievements'] = request.form.get('program_achievements')
            data['program_hours'] = request.form.get('program_hours')
            data['program_tracks'] = request.form.get('program_tracks')
            data['program_qualification'] = request.form.get('program_qualification')
            data['program_progress'] = request.form.get('program_progress')

            data['stats_students'] = request.form.get('stats_students')
            data['stats_enrollment'] = request.form.get('stats_enrollment')
            data['stats_graduates'] = request.form.get('stats_graduates')
            data['stats_additional'] = request.form.get('stats_additional')
            data['stats_metrics'] = request.form.get('stats_metrics')
            data['stats_ratio'] = request.form.get('stats_ratio')
            uploaded_files = request.files.getlist('files')
            saved_files = []
            for file in uploaded_files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    if '.' in filename:
                        ext = filename.rsplit('.', 1)[1].lower()
                    else:
                        ext = ''
                    saved_files.append({"name": filename, "type": ext, "path": file_path})
            files_data['program_files'] = saved_files
        elif step_number == 3:
            data['self_study_comparison'] = request.form.get('self_study_comparison')
            data['self_study_indicators'] = request.form.get('self_study_indicators')
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
            return redirect(url_for('final_report'))
    
    if request.method == 'GET' and step_number == 4:
        return render_template('step.html',
                               step_number=step_number,
                               total_steps=TOTAL_STEPS,
                               data=session.get('data', {}),
                               standards_files=STANDARDS_FILES)
    
    return render_template('step.html', total_steps=TOTAL_STEPS, step_number=step_number, criteria=criteria, data=data)

@app.route('/final_report')
def final_report():
    data = session.get('data', {})
    files_data = session.get('files', {})
    
    report_content = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>تقرير الدراسة الذاتية</title>
    <!-- استخدام خط من جوجل لتحسين المظهر -->
    <link
      href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600&display=swap"
      rel="stylesheet"
    />
    <style>
      /* متغيرات الألوان لتسهيل التعديل */
      :root {{
           --primary-color: #0b3c6d;
    --secondary-color: #2b5279;
    --accent-color: #d4af37;
    --light-color: #f4f4f4;
    --dark-color: #333;
      }}
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      body {{
        font-family: "Cairo", sans-serif;
        background: var(--light-color);
        color: var(--dark-color);
        line-height: 1.6;
      }}
      header {{
        background: var(--primary-color);
        color: #fff;
        padding: 2rem;
        text-align: center;
        position: relative;
      }}
      header::after {{
        content: "";
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 5px;
        background: var(--accent-color);
      }}
      nav {{
        background: var(--secondary-color);
        padding: 1rem 2rem;
        position: sticky;
        top: 0;
        z-index: 1000;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }}
      nav ul {{
        display: flex;
        justify-content: center;
        list-style: none;
        flex-wrap: wrap;
      }}
      nav ul li {{
        margin: 0 1rem;
      }}
      nav ul li a {{
        color: #fff;
        text-decoration: none;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: background 0.3s ease;
        border-radius: 5px;
      }}
      nav ul li a:hover {{
        background: var(--accent-color);
      }}
      .container {{
        max-width: 1200px;
        margin: 2rem auto;
        padding: 0 2rem;
        background: #fff;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border-radius: 8px;
      }}
      section {{
        padding: 2rem;
        border-bottom: 1px solid #e0e0e0;
      }}
      section:last-child {{
        border-bottom: none;
      }}
      section h2 {{
        margin-bottom: 1rem;
        color: var(--primary-color);
        border-left: 5px solid var(--accent-color);
        padding-left: 1rem;
      }}
      footer {{
        background: var(--primary-color);
        color: #fff;
        text-align: center;
        padding: 1.5rem;
        margin-top: 2rem;
      }}
      @media (max-width: 768px) {{
        nav ul {{
          flex-direction: column;
        }}
        nav ul li {{
          margin: 0.5rem 0;
        }}
        .container {{
          margin: 1rem;
          padding: 1rem;
        }}
      }}
      td, th {{
        border: 1px solid #bdc3c7;
        transition: background 0.3s;
    }}

    tr:hover:not(thead tr) {{
        background: #f5f6fa !important;
    }}

    input[type="radio"] {{
        transform: scale(1.3);
        accent-color: #3498db;
    }}

    td:not(:first-child) {{
        text-align: center;
        min-width: 80px;
    }}
    </style>
  </head>
  <body>
    <header>
      <h1>{data.get('title', '')}</h1>
    </header>

    <nav>
      <ul>
        <li><a href="#intro">الرئيسية</a></li>
        <li><a href="#table-of-contents">جدول المحتويات</a></li>
        <li><a href="#self-study">الدراسة الذاتية</a></li>
        <li><a href="#executive-summary">الملخص التنفيذي</a></li>
        <li><a href="#program-file">ملف البرنامج</a></li>
        <li><a href="#statistics">الإحصاءات والبيانات</a></li>
        <li><a href="#evaluation">التقويم والمعايير</a></li>
        <li><a href="#attachments">المرفقات والتوصيات</a></li>
      </ul>
    </nav>

        <div class="container">
      <!-- القسم الأول: الرئيسية -->
      <section id="intro">
        <h2>الرئيسية</h2>
        <div
          class="intro-content"
          style="display: flex; flex-wrap: wrap; gap: 2rem"
        >
          <!-- البيانات الأساسية -->
          <div class="institution-data" style="flex: 1; min-width: 250px">
            <h3 style="color: var(--accent-color)">البيانات الأساسية</h3>
            <p><strong>المؤسسة:</strong>  {data.get('institution', '')}</p>
            <p><strong>الكلية:</strong> {data.get('college', '')}</p>
            <p><strong>القسم العلمي:</strong> {data.get('department', '')}</p>
            <p><strong>البرنامج:</strong>{data.get('program', '')}</p>
            <p><strong>تاريخ إعداد التقرير:</strong> {data.get('reportDate', '')}</p>
          </div>
          <!-- بيانات التواصل -->
          <div class="contact-data" style="flex: 1; min-width: 250px">
            <h3 style="color: var(--accent-color)">بيانات التواصل</h3>
            <p><strong>الاسم:</strong> {data.get('contactName', '')}</p>
            <p><strong>المنصب:</strong> {data.get('position', '')}</p>
            <p><strong>البريد الإلكتروني:</strong>  {data.get('email', '')}</p>
            <p><strong>الهاتف الجوال:</strong> {data.get('phone', '')}</p>
          </div>
        </div>
      </section>

      <!-- القسم الثاني: جدول المحتويات
      <section id="table-of-contents">
        <h2>جدول المحتويات</h2>
        <p>
          ضع هنا جدول المحتويات بالتفصيل كما هو موضح في الملف، مع الحفاظ على
          التنسيق الأصلي.
        </p>
      </section> -->

      <!-- القسم الثالث: الدراسة الذاتية
      <section id="self-study">
        <h2>الدراسة الذاتية</h2>
        <p>
          يتم إدراج كافة تفاصيل الدراسة الذاتية والتقويم الذاتي للبرنامج هنا مع
          تنظيم المعلومات بطريقة واضحة وسهلة القراءة.
        </p>
      </section> -->

      <!-- القسم الرابع: الملخص التنفيذي -->
      <section
        id="executive-summary"
        style="
          margin: 2rem 0;
          padding: 1.5rem;
          background: #fdfdfd;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
        "
      >
        <h2
          style="
            border-left: 5px solid var(--accent-color, #e74c3c);
            padding-left: 1rem;
            color: var(--primary-color, #2c3e50);
          "
        >
          الملخص التنفيذي
        </h2>

        <table style="width: 100%; border-collapse: collapse; margin: 1.5rem 0">
          <thead>
            <tr style="background: #fafafa; border: 1px solid #ccc">
              <th
                style="
                  padding: 0.5rem;
                  text-align: left;
                  border: 1px solid #ccc;
                "
              >
                م
              </th>
              <th
                style="
                  padding: 0.5rem;
                  text-align: left;
                  border: 1px solid #ccc;
                "
              >
                المعيار
              </th>
              <th
                style="
                  padding: 0.5rem;
                  text-align: left;
                  border: 1px solid #ccc;
                "
              >
                التقويم الإجمالي للمعيار
              </th>
            </tr>
          </thead>
          <tbody>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">1</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                إدارة البرنامج وضمان جودته
              </td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">2</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                التعليم والتعلم
              </td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">3</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">الطلاب</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">4</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                هيئة التدريس
              </td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">5</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                افق والتجهيزات (مصادر التعلم والمر)
              </td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
            <tr style="border: 1px solid #ccc">
              <td style="padding: 0.5rem; border: 1px solid #ccc">6</td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                البحوث العلمية والمشاريع
              </td>
              <td style="padding: 0.5rem; border: 1px solid #ccc">
                ..............................................
              </td>
            </tr>
          </tbody>
        </table>

        <div style="margin: 1rem 0">
          <p style="font-weight: bold">أبرز جوانب القوة:</p>
          <p>• .........................................................</p>
        </div>

        <div style="margin: 1rem 0">
          <p style="font-weight: bold">أبرز جوانب التحسين:</p>
          <p>• .........................................................</p>
        </div>

        <div style="margin: 1rem 0">
          <p style="font-weight: bold">التوصيات التنفيذية:</p>
          <p>• .........................................................</p>
        </div>
      </section>

      <!-- القسم الخامس: ملف البرنامج -->
      <section
        id="program-file"
        style="
          margin: 2rem 0;
          padding: 1.5rem;
          background: #fdfdfd;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
        "
      >
        <h2
          style="
            border-left: 5px solid var(--accent-color, #e74c3c);
            padding-left: 1rem;
            color: var(--primary-color, #2c3e50);
          "
        >
          ملف البرنامج
        </h2>
        <div class="program-file-content" style="line-height: 1.8">
          <!-- رسالة البرنامج -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              رسالة البرنامج (1.1)
            </h3>
            <p>{data.get('program_message', '')}</p>
          </div>

          <!-- أهداف البرنامج -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              أهداف البرنامج (2.1)
            </h3>
            <p>{data.get('program_objectives', '')}</p>
          </div>

          <!-- قائمة الإنجازات والجوائز -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              قائمة بأبرز إنجازات البرنامج والجوائز (3.1)
            </h3>
             <p>{data.get('program_achievements', '')}</p>
          </div>

          <!-- إجمالي الساعات المعتمدة -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              إجمالي الساعات المعتمدة (4.1)
            </h3>
            <p style="margin: 0.5rem 0">
            {data.get('program_hours', '')}            </p>
          </div>

          <!-- المسارات الرئيسة للبرنامج -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              المسارات الرئيسة للبرنامج (إن وجدت)
            </h3>
            <table
              style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
            >
              <thead>
                <tr style="background: #fafafa; border: 1px solid #ccc">
                  <th style="padding: 0.5rem; border: 1px solid #ccc">
                    المسار
                  </th>
                  <th style="padding: 0.5rem; border: 1px solid #ccc">
                    إجمالي الساعات المعتمدة
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">1</td>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">
                    ..............................
                  </td>
                </tr>
                <tr>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">2</td>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">
                    ..............................
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- المؤهل الممنوح / نقاط الخروج -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              المؤهل الممنوح / نقاط الخروج (إن وجدت)
            </h3>
            <table
              style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
            >
              <thead>
                <tr style="background: #fafafa; border: 1px solid #ccc">
                  <th style="padding: 0.5rem; border: 1px solid #ccc">
                    المؤهل الممنوح/نقاط الخروج
                  </th>
                  <th style="padding: 0.5rem; border: 1px solid #ccc">
                    إجمالي الساعات المعتمدة
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">
                    ..............................
                  </td>
                  <td style="padding: 0.5rem; border: 1px solid #ccc">
                    ..............................
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- الفروع التي تقدم البرنامج -->
          <div
            class="card"
            style="
              margin-bottom: 1.5rem;
              padding: 1rem;
              background: #f9f9f9;
              border: 1px solid #ccc;
              border-radius: 8px;
            "
          >
            <h3 style="color: var(--accent-color, #e74c3c)">
              الفروع التي تقدم البرنامج (7.1)
            </h3>
            <ul style="margin: 0.5rem 0 0 1.5rem">
              <li>فرع 1: ........................................</li>
              <li>فرع 2: ........................................</li>
              <!-- يمكن إضافة المزيد من الفروع حسب الحاجة -->
            </ul>
          </div>
        </div>
      </section>

      <section
        id="statistics"
        style="
          margin: 2rem 0;
          padding: 1.5rem;
          background: #fdfdfd;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
        "
      >
        <h2
          style="
            border-left: 5px solid var(--accent-color, #e74c3c);
            padding-left: 1rem;
            color: var(--primary-color, #2c3e50);
          "
        >
          8.1 البيانات الإحصائية للبرنامج الأكاديمي
        </h2>

        <!-- تطور أعداد الطلاب الملتحقين بالبرنامج -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.1 تطور أعداد الطلاب الملتحقين بالبرنامج
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">السنة</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الطلاب الذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الطالبات الإناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الإجمالي
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  العام الحالي
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  العام الماضي
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- تصنيف الطلاب حسب نظام الدراسة -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.2 تصنيف الطلاب حسب نظام الدراسة (خلال العام الحالي)
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">التصنيف</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  السعوديين - ذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  السعوديين - إناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  غير السعوديين - ذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  غير السعوديين - إناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الإجمالي
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">انتظام</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  تعليم عن بعد
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- أعداد خريجي البرنامج -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.3 تطور أعداد خريجي البرنامج
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">السنة</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  عدد الخريجين الذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  عدد الخريجات الإناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الإجمالي
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  العام الحالي
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  العام الماضي
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- توظيف الخريجين -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.4 توظيف الخريجين
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  عدد الخريجين الموظفين
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  نسبة التوظيف إلى إجمالي الخريجين
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- أعداد هيئة التدريس -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.5 أعداد هيئة التدريس
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الرتبة الأكاديمية
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  سعوديين - ذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  سعوديين - إناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  غير سعوديين - ذكور
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  غير سعوديين - إناث
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  الإجمالي
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">أستاذ</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  أستاذ مشارك
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">
                  أستاذ مساعد
                </td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">......</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- مناقشة البيانات الإحصائية -->
        <div
          style="
            margin-top: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            8.1.6 مناقشة البيانات الإحصائية
          </h3>
          <p style="font-weight: bold">أبرز جوانب القوة:</p>
          <p>• .........................................................</p>
          <p style="font-weight: bold">أبرز جوانب التحسين:</p>
          <p>• .........................................................</p>
          <p style="font-weight: bold">توصيات التطوير:</p>
          <p>• .........................................................</p>
        </div>
      </section>

      <section
        id="self-study"
        style="
          margin: 2rem 0;
          padding: 1.5rem;
          background: #fdfdfd;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
        "
      >
        <h2
          style="
            border-left: 5px solid var(--accent-color, #e74c3c);
            padding-left: 1rem;
            color: var(--primary-color, #2c3e50);
          "
        >
          2. الدراسة الذاتية للبرنامج
        </h2>

        <!-- 7.1 جهات المقارنة وسبب اختيارها -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            2.1 جهات المقارنة وسبب اختيارها
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">م</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">الجهة</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  سبب الاختيار
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">1</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
              </tr>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">2</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 7.2 ملخص مؤشرات الأداء الرئيسة -->
        <div
          class="card"
          style="
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f9f9f9;
            border: 1px solid #ccc;
            border-radius: 8px;
          "
        >
          <h3 style="color: var(--accent-color, #e74c3c)">
            2.2 ملخص مؤشرات الأداء الرئيسة
          </h3>
          <table
            style="width: 100%; border-collapse: collapse; margin-top: 0.5rem"
          >
            <thead>
              <tr style="background: #fafafa; border: 1px solid #ccc">
                <th style="padding: 0.5rem; border: 1px solid #ccc">م</th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  مؤشر الأداء
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  مستوى الأداء الفعلي
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  مستوى الأداء المستهدف
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  المستوى المرجعي الداخلي
                </th>
                <th style="padding: 0.5rem; border: 1px solid #ccc">
                  المستوى المرجعي الخارجي (إن وجد)
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="padding: 0.5rem; border: 1px solid #ccc">1</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
                <td style="padding: 0.5rem; border: 1px solid #ccc">...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

    <!-- 3. التقويم الذاتي وفقا لمعايير الاعتماد -->
    <div class="card" style="margin-bottom: 1.5rem; padding: 1rem; background: #f9f9f9; border: 1px solid #ccc; border-radius: 8px;">
      <h3 style="color: var(--accent-color, #e74c3c);">3. التقويم الذاتي وفقا لمعايير الاعتماد</h3>
      <h4 style="color: var(--primary-color, #2c3e50);">المعيار الأول: إدارة البرنامج وضمان جودته</h4>

      <table dir="rtl" border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: 'Segoe UI', Tahoma; margin: 20px auto;">
          <!-- Header Section -->
          <thead style="background: #2c3e50; color: white;">
              <tr>
                  <th colspan="7" style="font-size: 1.2em; padding: 15px;">نموذج تقييم المعايير الأكاديمية</th>
              </tr>
              <tr>
                  <th  colspan="2" >المحكات</th>
                  <th style="background: #27ae60;">امتثال كامل<br>(5 نقاط)</th>
                  <th style="background: #2980b9;">امتثال جزئي<br>(3 نقاط)</th>
                  <th style="background: #f1c40f;">تحسين مطلوب<br>(2 نقطة)</th>
                  <th style="background: #e74c3c;">عدم امتثال<br>(0 نقطة)</th>
                  <th>الدرجة<br>المتحققة</th>
              </tr>
            </thead>

            <!-- Evaluation Levels -->
            <tbody>
                <!-- Main Criteria -->
                <tr style="background: #ecf0f1;">
                    <td colspan="7" style="padding: 12px; font-weight: bold;">1.1 إدارة البرنامج</td>
                </tr>
    
                <tr>
                    <td colspan="2" style="text-align: right;">تنسيق الرسالة والأهداف مع المؤسسة</td>
                    <td><input type="radio" name="10.1-1"></td>
                    <td><input type="radio" name="10.1-1"></td>
                    <td><input type="radio" name="10.1-1"></td>
                    <td><input type="radio" name="10.1-1"></td>
                    <td style="background: #f8f9fa;">____</td>
                </tr>
        <tr>
            <td colspan="2" style="text-align: right;">يتوفير لدى البرنامج العدد الكلي من الكوادر للإفادة للقيام بالقيام الإدارية والثانية، ويتم سياسات محددة *</td>
            <td><input type="radio" name="10.1-2"></td>
            <td><input type="radio" name="10.1-2"></td>
            <td><input type="radio" name="10.1-2"></td>
            <td><input type="radio" name="10.1-2"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">يتوفير للبرنامج مناخ تنظيمي وبيئة أكاديمية داعمة.</td>
            <td><input type="radio" name="10.1-3"></td>
                    <td><input type="radio" name="10.1-3"></td>
                    <td><input type="radio" name="10.1-3"></td>
                    <td><input type="radio" name="10.1-3"></td>
                    <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">قبائع القائمون على البرنامج مدى تحقق أهدافه وتنفيذ الإجراءات اللازمة للتحسين</td>
            <td><input type="radio" name="10.1-4"></td>
                    <td><input type="radio" name="10.1-4"></td>
                    <td><input type="radio" name="10.1-4"></td>
                    <td><input type="radio" name="10.1-4"></td>
                    <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تطبق إدارة البرنامج المباشرة عن الزمنة والمعدالة والمساواة في جميع مسارساتها الككاديمية والإدارية، ومن تساوي الطلب والطلبات والشروع (أرد وجدت).</td>
            <td><input type="radio" name="10.1-5"></td>
                    <td><input type="radio" name="10.1-5"></td>
                    <td><input type="radio" name="10.1-5"></td>
                    <td><input type="radio" name="10.1-5"></td>
                    <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تستغيب إدارة البرنامج من أولاً لمتبين والخبراء في تخصص البرنامج في تقييم وتطوير وتحسين أدائه .</td>
            <td><input type="radio" name="10.1-6"></td>
            <td><input type="radio" name="10.1-6"></td>
            <td><input type="radio" name="10.1-6"></td>
            <td><input type="radio" name="10.1-6"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تتيح إدارة البرنامج معلومات موثوقة ومعلنة تتضمن وصف البرنامج، وأدائه وإنجازاته بما يناسب مع احتياجات المستفيدين.</td>
            <td><input type="radio" name="10.1-7"></td>
                    <td><input type="radio" name="10.1-7"></td>
                    <td><input type="radio" name="10.1-7"></td>
                    <td><input type="radio" name="10.1-7"></td>
                    <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تلتزم إدارة البرنامج تفعيل قيم الأمانة العلمية وحقوق الملكية الفكرية وقواعد المسارسات الأخلاقية والمساواة القويم في جميع المجالات والأنشطة الأكاديمية والبحثية والإدارية والعنصية *</td>
            <td><input type="radio" name="10.1-8"></td>
                    <td><input type="radio" name="10.1-8"></td>
                    <td><input type="radio" name="10.1-8"></td>
                    <td><input type="radio" name="10.1-8"></td>
                    <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تطبق إدارة البرنامج الأنشطة واللوائح والإجراءات المتعددة من قبل المؤسسة/ الكلية، بما في ذلك التنظم، والشكاوى، والفضلها التذبيرة.</td>
            <td><input type="radio" name="10.1-9"></td>
            <td><input type="radio" name="10.1-9"></td>
            <td><input type="radio" name="10.1-9"></td>
            <td><input type="radio" name="10.1-9"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr style="background: #ecf0f1;">
            <td colspan="7" style="padding: 12px; font-weight: bold;">1.2 ضمان جودة البرنامج</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">تطبق إدارة البرنامج نظاماً فاعلاً لضمان الجودة وإدارتها، يتسق مع نظام الجودة المؤسسي.</td>
            <td><input type="radio" name="10.1-11"></td>
            <td><input type="radio" name="10.1-11"></td>
            <td><input type="radio" name="10.1-11"></td>
            <td><input type="radio" name="10.1-11"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">يقوم البرنامج بتعليل مؤشرات الأداء الرئيسية وبيانات التقويم مسؤولياً وبســـتفاد منها في عمليات التخطيط والتطويره اتخاذ القرارات.*</td>
            <td><input type="radio" name="10.1-12"></td>
            <td><input type="radio" name="10.1-12"></td>
            <td><input type="radio" name="10.1-12"></td>
            <td><input type="radio" name="10.1-12"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        <tr>
            <td colspan="2" style="text-align: right;">يجري البرنامج تقويماً دورياً شاملاً ويضع خططاً للتحسين، وبناءً تنفيذها.</td>
            <td><input type="radio" name="10.1-13"></td>
            <td><input type="radio" name="10.1-13"></td>
            <td><input type="radio" name="10.1-13"></td>
            <td><input type="radio" name="10.1-13"></td>
            <td style="background: #f8f9fa;">____</td>
        </tr>
        
        <!-- التقييم الكلي -->
        <tr>
            <td colspan="3" style="background-color: #f2f2f2; text-align: center; padding: 15px;">
                <strong>التقييم الكلي للمعيار</strong>
            </td>
        </tr>
    </table>

    <table dir="rtl" border="1" cellpadding="12" cellspacing="0" style="border-collapse: collapse; width: 100%; font-family: 'Tahoma'; margin: 20px auto; background: white;">
        <!-- التقييم العام -->
        <thead style="background: #34495e; color: white;">
            <tr>
                <th colspan="4" style="padding: 15px; font-size: 18px;">التقويم الأكاديمي للبرنامج</th>
            </tr>
            <tr>
                <th style="width: 25%; background: #27ae60;">مرضي</th>
                <th style="width: 25%; background: #e74c3c;">غير مرضي</th>
                <th style="width: 25%; background: #f1c40f;">امتثال جزئي</th>
                <th style="width: 25%;">مؤشرات</th>
            </tr>
        </thead>
    
        <tbody>
            <tr>
                <td>امتثال كامل (4)</td>
                <td>عدم امتثال متوسط (3)</td>
                <td>امتثال كبير (2)</td>
                <td rowspan="2" style="vertical-align: middle;">المستوى المعياري</td>
            </tr>
    
            <!-- المكانات -->
            <tr style="background: #f8f9fa;">
                <td colspan="3" style="padding: 15px;">
                    <strong>المكانات:</strong>
                    <ul style="text-align: right; list-style: none; padding-right: 0;">
                        <li>■ عدد المكانات المحتملة: 12</li>
                        <li>■ متوسط تقييم المعيار: 3.4/5</li>
                    </ul>
                </td>
            </tr>
    
            <!-- التقييم الإجمالي -->
            <tr>
                <td colspan="4" style="background: #ecf0f1; padding: 15px;">
                    <div style="display: flex; justify-content: space-between;">
                        <strong>درجة التقويم الإجمالي للمعيار:</strong>
                        <span style="color: #2ecc71;">7.8/10</span>
                    </div>
                </td>
            </tr>
    
            <!-- التعليقات -->
            <tr>
                <td colspan="4" style="padding: 20px; text-align: right;">
                    <h4 style="color: #3498db; margin: 0 0 10px 0;">التعليق على النتائج:</h4>
                    <p style="line-height: 1.6; margin: 0;">
                        يجب ربط نتائج التقويم بمؤشرات الأداء ذات العلاقة<br>
                        والاستشهاد بالبيانات الداعمة مع مراعاة:
                    </p>
                    <ol style="padding-right: 20px;">
                        <li>إدارة البرنامج</li>
                        <li>جودة العمليات الأكاديمية</li>
                    </ol>
                </td>
            </tr>
    
            <!-- التقييم النهائي -->
            <tr style="background: #2c3e50; color: white;">
                <td colspan="4" style="padding: 15px;">
                    <strong>التقويم العام لجودة المعيار:</strong>
                    <div style="margin-top: 10px;">
                        <span style="color: #27ae60;">■ أبرز جوانب القوة: نظام إدارة فعال</span><br>
                        <span style="color: #e74c3c;">■ مجالات التحسين: تطوير آليات التقييم</span>
                    </div>
                </td>
            </tr>
        </tbody>
    </table>
  </section>
  .<br/>
  .<br/>
  .<br/>
  
  
      <!-- القسم السابع: التقويم والمعايير -->
      <!-- <section id="evaluation">
        <h2>التقويم والمعايير</h2>
        <p>
          يتضمن هذا القسم تفاصيل التقويم الذاتي للبرنامج والمعايير المختلفة مثل
          إدارة البرنامج، التعليم والتعلم، الطلاب، هيئة التدريس، مصادر التعلم،
          والبحوث.
        </p>
      </section>

      <section id="attachments">
        <h2>المرفقات والتوصيات</h2>
        <p>
          يمكن إضافة كافة المرفقات مثل تقرير الرأي المستقل والتوصيات التنفيذية
          والموارد المطلوبة، مع تنظيمها بشكل يسهل الوصول إليها.
        </p>
      </section> -->
    </div>

    <footer>
      <p>&copy; 2025 جميع الحقوق محفوظة - QualiAI</p>
    </footer>
  </body>
</html>
    """

    
    report_id = str(uuid.uuid4())
    shareable_link = url_for('view_report', report_id=report_id, _external=True)

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
    
    return render_template('final_report.html', shareable_link=shareable_link)

@app.route('/report/<report_id>')
def view_report(report_id):
    report_ref = db.collection('reports').document(report_id).get()
    if report_ref.exists:
        report_data = report_ref.to_dict()
        return report_data.get('report_content', '<h3>لا يوجد محتوى للتقرير</h3>')
    else:
        abort(404, description="التقرير غير موجود")

if __name__ == '__main__':
    app.run(debug=True)

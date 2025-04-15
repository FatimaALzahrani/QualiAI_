from datetime import datetime
from flask import Flask, render_template,render_template_string, request, redirect, url_for, session, send_from_directory,abort,send_file
import firebase_admin
from firebase_admin import credentials, auth, firestore
import pandas as pd
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import numpy as np
import os, uuid
import json
import plotly.graph_objs as go
from plotly.offline import plot
import requests

from config import firebase_config
from sentence_transformers import SentenceTransformer, util
import pandas as pd
from textblob import TextBlob
from openai import OpenAI
import openai
import re
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'AIzaSyAr1hQK-pqmDlStxEScGJsXeLd3ZxabdhQ'

api_key = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY)
openai.api_key = os.getenv("OPENAI_API_KEY")

# model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
model = SentenceTransformer('all-MiniLM-L6-v2')

cred = credentials.Certificate("credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
print("✅ Firebase Initialized Successfully!")

UPLOAD_FOLDER = 'uploads'
REPORTS_FOLDER = 'reports'
EVIDENCE_FOLDER = 'evidences'
app.config['ANALYSIS_FOLDER'] = os.path.join(os.getcwd(), 'analysis_results')
if not os.path.exists(app.config['ANALYSIS_FOLDER']):
    os.makedirs(app.config['ANALYSIS_FOLDER'])
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)
os.makedirs(EVIDENCE_FOLDER, exist_ok=True) 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REPORTS_FOLDER'] = REPORTS_FOLDER
app.config['EVIDENCE_FOLDER'] = EVIDENCE_FOLDER 
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, '.flask_session')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SECRET_KEY'] = 'AIzaSyAr1hQK-pqmDlStxEScGJsXeLd3ZxabdhQ' 
Session(app)

data_categories = {
    "عدد الطلاب المُخطط إلتحاقهم بالبرنامج": "عدد الطلاب المُخطط إلتحاقهم بالبرنامج",
    "العدد الكلي للطلاب الملتحقين بالبرنامج": "العدد الكلي للطلاب الملتحقين بالبرنامج",
    "عدد الطلاب الدوليين الملتحقين بالبرنامج": "عدد الطلاب الدوليين الملتحقين بالبرنامج",
    "متوسط عدد الطلاب في الشعب الدراسية": "متوسط عدد الطلاب في الشعب الدراسية",
    "نسبة عدد الطلاب لهيئة التدريس": "نسبة عدد الطلاب لهيئة التدريس"
}

FIREBASE_API_KEY = "AIzaSyABMZmTlio-nZ8sLJPSlDmB82mMD9Orb4M"

DEFAULT_STUDENT_STANDARDS = {
    "3.1": {
        "text": "يطبق البرنامج معايير وشروط معتمدة ومعلنة لقبول الطلاب وتسجيلهم وتوزيعهم، والانتقال إلى البرنامج ومعادلة ما تعلمه الطلاب سابقاً، بما يتناسب مع طبيعة البرنامج ومستواه.",
        "mandatory": False
    },
    "3.2": {
        "text": "يوفر البرنامج المعلومات الأساسية للطلاب، مثل: متطلبات الدراسة، الخدمات، والتكاليف المالية (إن وجدت)، بوسائل متنوعة.",
        "mandatory": False
    },
    "3.3": {
        "text": "يتوفر لطلاب البرنامج خدمات فعالة للإرشاد والتوجيه الأكاديمي والمهني والنفسي والاجتماعي، من خلال كوادر مؤهلة وكافية.",
        "mandatory": True
    },
    "3.4": {
        "text": "تطبق آليات ملائمة للتعرف على الطلاب الموهوبين والمبدعين والمتفوقين والمتعثرين في البرنامج، وتتوفر برامج مناسبة لرعاية وتحفيز ودعم كل فئة منهم.",
        "mandatory": False
    },
    "3.5": {
        "text": "يطبق البرنامج آلية فعالة للتواصل مع الخريجين وإشراكهم في مناسباته وأنشطته، واستطلاع آرائهم والاستفادة من خبراتهم، ودعمهم، وتوفر قواعد بيانات محدثة وشاملة عنهم.",
        "mandatory": False
    },
    "3.6": {
        "text": "تطبق آليات فعــالة لتقويم كفاية وجودة الخدمات المقدمة للطلاب وقياس رضاهم عنها، والاستفادة من النتائج في التحسين.",
        "mandatory": True
    }
}


def extract_list(section_title, text):
    stop_words = ['نقاط القوة', 'نقاط الضعف', 'مجالات التحسين', 'التوصيات', 'الخطة الاستراتيجية', 'الضعف']
    stop_words = [w for w in stop_words if w != section_title] 
    stop_pattern = "|".join([re.escape(w) for w in stop_words])
    
    section_pattern = rf"(?:\[{section_title}\]|{section_title})\s*[:：]?\s*"

    pattern = rf"{section_pattern}(.*?)(?=\n(?:{stop_pattern})|\Z)"
    
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        section_text = match.group(1).strip()
        
        items = re.findall(r"(?:^-|\d+[.)])\s*(.+)", section_text, re.MULTILINE)
        return [item.strip() for item in items if item.strip()]
    
    return []

def process_students_standard(uploaded_files, standards_data):
    if not uploaded_files or not any(f.filename for f in uploaded_files):
        return {"error": "لم يتم رفع أي ملفات"}
    
    all_questions = []
    sources = []
    
    for file in uploaded_files:
        if file and file.filename.endswith(('.xlsx', '.xls')):
            try:
                filename = secure_filename(file.filename)
                upload_dir = app.config['UPLOAD_FOLDER']
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                df = pd.read_excel(filepath)
                excluded_cols = ['الوقت', 'اسم الكلية', 'اسم البرنامج (القسم)', 'الجنس']
                questions = [
                    col for col in df.columns
                    if col not in excluded_cols 
                    and isinstance(col, str) 
                    and len(col.strip()) > 10
                ]
                all_questions.extend(questions)
                sources.extend([filename] * len(questions))
            except Exception as e:
                app.logger.error(f"خطأ في معالجة الملف {file.filename}: {str(e)}")
                continue

    if not all_questions:
        return {"error": "لم يتم العثور على أسئلة صالحة في الملفات المرفوعة"}
    
    try:
        std_texts = [std["text"] for std in standards_data]
        std_ids = [std["id"] for std in standards_data]
        
        q_emb = model.encode(all_questions, convert_to_tensor=True)
        std_emb = model.encode(std_texts, convert_to_tensor=True)
        cosine_scores = util.cos_sim(q_emb, std_emb)
        
        students_map = {sid: [] for sid in std_ids}
        for i, question in enumerate(all_questions):
            best_score = float(cosine_scores[i].max())
            best_index = int(cosine_scores[i].argmax())
            if best_score > 0.3:
                matched_sid = std_ids[best_index]
                students_map[matched_sid].append({
                    "question": question,
                    "score": best_score,
                    "source": sources[i]
                })
    except Exception as e:
        return {"error": "حدث خطأ فني أثناء معالجة البيانات"}

    sub_evaluations = []
    total_sub_score = 0
    applicable_count = 0
    
    for sid, questions in students_map.items():
        if not questions:
            continue
        try:
            std_entry = next((std for std in standards_data if std["id"] == sid), {})
            std_text = std_entry.get("text", "")
            evidences = std_entry.get("evidences", [])
            
            evidence_content = "\n".join(
                f"{i+1}. {ev['description']} ({ev.get('file_name', 'ملف مرفق')})" 
                if ev.get('type') == 'file' else 
                f"{i+1}. {ev['description']} ({ev.get('link', 'رابط')})"
                for i, ev in enumerate(evidences))
            
            evaluation_prompt = f"""\
                المهمة: تقييم أداء البرنامج وفق المعيار {sid}

                نص المعيار:
                {std_text}

                البيانات المستخلصة:
                {chr(10).join(q['question'] for q in questions)}

                الشواهد الداعمة:
                {evidence_content}

                المطلوب:
                1. تحليل مفصل (200-300 كلمة) يركز على:
                - مدى توافق الممارسات مع متطلبات المعيار
                - جودة الأدلة الداعمة
                - الثغرات الرئيسية

                2. تحديد العناصر التالية:
                - نقاط القوة (2-3 نقاط كحد أقصى)
                - نقاط الضعف (2-3 نقاط كحد أقصى)
                - توصيات التحسين (3 توصيات عملية)

                3. التقييم النهائي حسب المقياس:
                0 = غير مطبق
                1 = امتثال متدنٍ (<25%)
                2 = امتثال جزئي (25-50%)
                3 = امتثال كبير (51-75%)
                4 = امتثال كامل (>75%)

                التنسيق المطلوب:
                [التحليل]
                ...
                [نقاط القوة]
                - ...
                [نقاط الضعف] 
                - ...
                [التوصيات]
                - ...
                [التقييم] X
                """

            evaluation_response = generate_comment(evaluation_prompt)
            
            analysis = re.search(r'\[التحليل\](.*?)(\[نقاط القوة\]|$)', evaluation_response, re.DOTALL)
            strengths = extract_list('نقاط القوة', evaluation_response)
            weaknesses = extract_list('نقاط الضعف', evaluation_response)
            improvements = extract_list('التوصيات', evaluation_response)
            eval_match = re.search(r'\[التقييم\]\s*(\d+)', evaluation_response)
            
            eval_score = int(eval_match.group(1)) if eval_match else 0
            if eval_score > 0:
                applicable_count += 1
                total_sub_score += eval_score
            
            sub_evaluations.append({
                "substandard_id": sid,
                "substandard_text": std_text,
                "questions": questions,
                "analysis": analysis.group(1).strip() if analysis else "",
                "strengths": strengths[:3],
                "weaknesses": weaknesses[:3],
                "improvements": improvements[:3],
                "evaluation": eval_score,
                "evidences": evidences
            })
        except:
            print("error")

    overall = {
        "overall_comment": "لم يتم العثور على بيانات كافية للتقييم",
        "recommendations": {
            "نقاط القوة": [],
            "نقاط الضعف": [],
            "مجالات التحسين": []
        }
    }
    
    if applicable_count > 0:
        try:
            context = "\n\n".join(
                f"المعيار: {sub['substandard_id']} ({sub['evaluation']}/4)\n"
                f"التحليل: {sub['analysis']}\n"
                f"النقاط الإيجابية: {', '.join(sub['strengths'])}\n"
                f"المجالات التحسينية: {', '.join(sub['improvements'])}"
                for sub in sub_evaluations
            )

            overall_prompt = f"""\
المهمة: إعداد تقرير تقييم نهائي لمعيار الطلاب

السياق:
{context}

المتطلبات:
1. صياغة تحليل شامل (300-400 كلمة) يشمل:
   - ملخص للأداء العام
   - العلاقات بين النتائج الفرعية
   - التحديات المشتركة
   - الفرص الاستراتيجية

2. تحديد العناصر الرئيسية:
   - 3-5 نقاط قوة جوهرية
   - 3-5 مجالات تحسين حرجة
   - 5 توصيات استراتيجية ذات أولوية

3. صياغة احترافية تناسب:
   - صناع القرار
   - جهات الاعتماد
   - لجان التطوير الأكاديمي

التنسيق المطلوب:
[التحليل الشامل]
...
[النقاط الرئيسية]
القوة:
- ...
الضعف:
- ...
[الخطة الاستراتيجية]
- ...
"""

            overall_response = generate_comment(overall_prompt)
            
            overall_comment = re.search(r'\[التحليل الشامل\](.*?)(\[النقاط الرئيسية\]|$)', overall_response, re.DOTALL)
            strengths = extract_list('القوة', overall_response)
            weaknesses = extract_list('الضعف', overall_response)
            improvements = extract_list('الخطة الاستراتيجية', overall_response)

            avg_score = total_sub_score / (applicable_count * 4)
            rating = (
                "امتثال كامل" if avg_score >= 0.75 else
                "امتثال كبير" if avg_score >= 0.5 else
                "امتثال جزئي" if avg_score >= 0.25 else
                "امتثال متدنٍ"
            )

            overall["overall_comment"] = f"{rating}\n\n{(overall_comment.group(1) if overall_comment else '').strip()}"
            overall["recommendations"] = {
                "نقاط القوة": strengths[:5],
                "نقاط الضعف": weaknesses[:5],
                "مجالات التحسين": improvements[:5]
            }
            overall["overall"] = overall_response

        except Exception as e:
            app.logger.error(f"خطأ في التقييم الشامل: {str(e)}")

    try:
        analysis_dir = app.config['ANALYSIS_FOLDER']
        os.makedirs(analysis_dir, exist_ok=True)
        save_path = os.path.join(analysis_dir, 'students_evaluation.json')
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump({
                "sub_evaluations": sub_evaluations,
                "overall_evaluation": overall
            }, f, ensure_ascii=False, indent=4)
    except Exception as e:
        app.logger.error(f"خطأ في حفظ النتائج: {str(e)}")
        return {"error": "حدث خطأ أثناء حفظ النتائج"}

    return {
        "sub_evaluations": sub_evaluations,
        "overall_evaluation": overall
    }
    
    
def login_with_password(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, json=payload)

    return response.json() if response.status_code == 200 else None

def save_data_to_firestore(user_id, data):
    try:
        report_id = str(uuid.uuid4())
        
        data['report_id'] = report_id
        data['created_at'] = datetime.now().isoformat()
        data['user_id'] = user_id
        
        db.collection('reports').document(report_id).set(data)
        
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            reports = user_data.get('reports', [])
            reports.append(report_id)
            user_ref.update({'reports': reports})
        
        return report_id
    except Exception as e:
        print(f"Error saving data to Firestore: {e}")
        return None

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


def generate_comment(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "أنت مساعد أكاديمي خبير."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500
    )
    return response.choices[0].message.content.strip()


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
import json

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

student_substandards = {
"3.1": "يطبق البرنامج معايير وشروط معتمدة ومعلنة لقبول الطلاب وتسجيلهم وتوزيعهم، والانتقال إلى البرنامج ومعادلة ما تعلمه الطلاب سابقاً، بما يتناسب مع طبيعة البرنامج ومستواه.",
"3.2": "يوفر البرنامج المعلومات الأساسية للطلاب، مثل: متطلبات الدراسة، الخدمات، والتكاليف المالية (إن وجدت)، بوسائل متنوعة.",
"3.3": "يتوفر لطلاب البرنامج خدمات فعالة للإرشاد والتوجيه الأكاديمي والمهني والنفسي والاجتماعي، من خلال كوادر مؤهلة وكافية.",
"3.4": "تطبق آليات ملائمة للتعرف على الطلاب الموهوبين والمبدعين والمتفوقين والمتعثرين في البرنامج، وتتوفر برامج مناسبة لرعاية وتحفيز ودعم كل فئة منهم.",
"3.5": "يطبق البرنامج آلية فعالة للتواصل مع الخريجين وإشراكهم في مناسباته وأنشطته، واستطلاع آرائهم والاستفادة من خبراتهم، ودعمهم، وتوفر قواعد بيانات محدثة وشاملة عنهم.",
"3.6": "تطبق آليات فعــالة لتقويم كفاية وجودة الخدمات المقدمة للطلاب وقياس رضاهم عنها، والاستفادة من النتائج في التحسين."}

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
        "description": "يرجى تعبئة النقاط الخاصة بملف البرنامج.",
        "allowed_extensions": [".xlsx", ".xls"]
    },
    3: {
        "title": "الدراسة الذاتية للبرنامج",
        "description": "يرجى تعبئة البيانات الخاصة بالدراسة الذاتية للبرنامج.",
        "allowed_extensions": []
    },
    4: {
        "title": "التقويم الذاتي وفق معايير الاعتماد",
        "description": "يرجى تعبئة البيانات الخاصة بالتقويم الذاتي وفق معايير الاعتماد.",
        "allowed_extensions": []
    }
}

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

            recommendations = generate_recommendations(data)

            data["recommendations"] = recommendations
              
            data['kpis_row'] = calculate_kpi(data)  

        elif step_number == 3:
            entities = request.form.getlist('entity[]')
            reasons = request.form.getlist('reason[]')
            
            comparison_entities = []
            for i in range(len(entities)):
                comparison_entities.append({
                    'entity': entities[i],
                    'reason': reasons[i] if i < len(reasons) else ''
                })
            
            data['comparison_entities'] = comparison_entities
            
            indicators = request.form.getlist('indicator[]')
            actuals = request.form.getlist('actual[]')
            targets = request.form.getlist('target[]')
            internal_refs = request.form.getlist('internal_ref[]')
            external_refs = request.form.getlist('external_ref[]')
            
            kpis = []
            for i in range(len(indicators)):
                kpis.append({
                    'indicator': indicators[i],
                    'actual': float(actuals[i]) if i < len(actuals) and actuals[i] else 0,
                    'target': float(targets[i]) if i < len(targets) and targets[i] else 0,
                    'internal_ref': float(internal_refs[i]) if i < len(internal_refs) and internal_refs[i] else 0,
                    'external_ref': float(external_refs[i]) if i < len(external_refs) and external_refs[i] else 0
                })
            
            data['kpis_row'] = kpis
                        
        elif step_number == 4:
            try:
                standards_data = []
                standard_ids = request.form.getlist("standard_id[]")
                standard_texts = request.form.getlist("standard_text[]")
                standard_mandatory = request.form.getlist("standard_mandatory[]")
                
                if not standard_texts:
                    return jsonify({"error": "يرجى إدخال محكات للمعيار قبل المتابعة."})
                
                for i in range(len(standard_texts)):
                    standard_id = standard_ids[i] if i < len(standard_ids) else f"3.{i+1}"
                    is_mandatory = standard_mandatory[i] == "true" if i < len(standard_mandatory) else False
                    
                    evidence_indices = request.form.getlist(f"evidence_index_{i}[]")
                    evidences = []
                    
                    for j in range(len(evidence_indices)):
                        evidence_desc = request.form.get(f"evidence_desc_{i}_{j}")
                        evidence_type = request.form.get(f"evidence_type_{i}_{j}")
                        
                        evidence_data = {
                            "description": evidence_desc,
                            "type": evidence_type
                        }
                        
                        if evidence_type == "file":
                            evidence_file = request.files.get(f"evidence_file_{i}_{j}")
                            if evidence_file and evidence_file.filename:
                                filename = secure_filename(evidence_file.filename)
                                filepath = os.path.join(app.config['EVIDENCE_FOLDER'], filename)
                                evidence_file.save(filepath)
                                evidence_data["file_path"] = filepath
                                evidence_data["file_name"] = filename
                        elif evidence_type == "link":
                            evidence_link = request.form.get(f"evidence_link_{i}_{j}")
                            evidence_data["link"] = evidence_link
                        
                        evidences.append(evidence_data)
                    
                    standards_data.append({
                        "id": standard_id,
                        "text": standard_texts[i],
                        "mandatory": is_mandatory,
                        "evidences": evidences
                    })
                
                uploaded_files = request.files.getlist('analysis_files')
                analysis_results = process_students_standard(uploaded_files, standards_data)
                
                data['standards'] = standards_data
                data['analysis_results'] = analysis_results
                                        
            except Exception as e:
                return jsonify({"error": f"حدث خطأ أثناء معالجة البيانات: {str(e)}"})

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
                               standards_files=STANDARDS_FILES,student_substandards=student_substandards)
    
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

    
    # data['contactName'] = user.get('username', 'غير محدد')
    # data['position'] = user.get('position', 'غير محدد')
    # data['email'] = user.get('email', 'غير محدد')
    # data['phone'] = user.get('phone', 'غير محدد')
    # data['reportDate'] = datetime.now().strftime('%Y-%m-%d')

    # data['institution'] = request.form.get('institution')
    # data['college'] = request.form.get('college')
    # data['department'] = request.form.get('department')
    # data['program'] = request.form.get('program')
    # data['title'] = request.form.get('title')

    # fields = [
    #     'program_message', 'program_objectives', 'program_achievements',
    #     'program_hours', 'program_tracks', 'program_qualification',
    #     'program_progress', 'stats_students', 'stats_enrollment',
    #     'stats_graduates', 'stats_additional', 'stats_metrics', 'stats_ratio'
    # ]
    

    # for field in fields:
    #     data[field] = request.form.get(field, "").strip()

    # track_count = int(request.form.get("program_tracks_count", 1) or 1)
    # qual_count = int(request.form.get("program_qualification_count", 1) or 1)

    # data['program_tracks'] = [
    #     {
    #         "name": request.form.get(f"track_name_{i}", "").strip(),
    #         "hours": int(request.form.get(f"track_hours_{i}", "0") or 0)
    #     }
    #     for i in range(1, track_count + 1)
    # ]

    # data['program_qualification'] = [
    #     {
    #         "name": request.form.get(f"qualification_name_{i}", "").strip(),
    #         "hours": int(request.form.get(f"qualification_hours_{i}", "0") or 0)
    #     }
    #     for i in range(1, qual_count + 1)
    # ]

    entities = request.form.getlist('entity[]')
    reasons = request.form.getlist('reason[]')
    comparison_entities = [{"entity": e, "reason": r} for e, r in zip(entities, reasons)]
    data["comparison_entities"] = comparison_entities

    indicators = request.form.getlist("indicator[]")
    actuals = request.form.getlist("actual[]")
    targets = request.form.getlist("target[]")
    internal_refs = request.form.getlist("internal_ref[]")
    external_refs = request.form.getlist("external_ref[]")
    non_table_data = {}

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
        print(field , ' ', value)
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
          
        else:
            data.setdefault(field, value)
            non_table_data.setdefault(field,value)
    
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

    data = {**data, **non_table_data}
    print("data ",data)

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
    app.run(host="0.0.0.0", port=10000)

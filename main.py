
import streamlit as st
import json
import random
import smtplib
import google.generativeai as genai
from email.message import EmailMessage
import os
import hashlib
from datetime import date, datetime
import matplotlib.pyplot as plt
import re
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import timedelta
import time

# Use secrets for security
genai.configure(api_key="AIzaSyBrNii9tvFNkRL3LEvQCBlS_jV2TA__VZc")

# Folders
os.makedirs("data", exist_ok=True)
os.makedirs("progress", exist_ok=True)
os.makedirs("schedules", exist_ok=True)
os.makedirs("auth", exist_ok=True)

USER_FILE = 'auth/users.json'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def auth_ui():
    st.sidebar.subheader("🔐 Login or Signup")
    users = load_users()
    action = st.sidebar.radio("Choose Action", ["Login", "Signup"])

    if action == "Signup":
        new_user = st.sidebar.text_input("Create Username")
        new_email = st.sidebar.text_input("Your Email")
        new_pass = st.sidebar.text_input("Create Password", type="password")
        if st.sidebar.button("Signup"):
            if not new_user or not new_email or not new_pass:
                st.sidebar.warning("Please fill in all fields.")
            elif new_user in users:
                st.sidebar.warning("Username already exists!")
            else:
                users[new_user] = {
                    "password": hash_password(new_pass),
                    "email": new_email
                }
                save_users(users)
                st.sidebar.success("Signup successful! Please login.")
                st.rerun()

    elif action == "Login":
        user = st.sidebar.text_input("Username")
        passwd = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            if user in users and users[user]['password'] == hash_password(passwd):
                st.session_state.logged_in = True
                st.session_state.username = user
                st.session_state.email = users[user]['email']
                st.success(f"Welcome, {user}!")
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials")

def get_user_progress_file():
    return f"progress/{st.session_state['username']}_progress.json"

def load_progress():
    path = get_user_progress_file()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            return {}
    return {}

def save_progress(topic, correct=1, total=1):
    today = str(date.today())
    progress = load_progress()

    if today not in progress:
        progress[today] = {}

    if topic not in progress[today]:
        progress[today][topic] = {"correct": 0, "total": 0}

    progress[today][topic]["correct"] += correct
    progress[today][topic]["total"] += total

    with open(get_user_progress_file(), 'w') as f:
        json.dump(progress, f, indent=2)


def get_user_schedule_file():
    return f"schedules/{st.session_state['username']}_schedule.json"

def load_schedule():
    path = get_user_schedule_file()
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_schedule(schedule):
    path = get_user_schedule_file()
    with open(path, 'w') as f:
        json.dump(schedule, f, indent=2)

def send_email_alert(subject, message, to_email=None, attachment_bytes=None, attachment_filename="report.pdf"):
    try:
        from_email = "ai.smart.study.bot@gmail.com"
        password = "xdkizopaxxathrho"
        if to_email is None:
            to_email = st.session_state.get('email')

        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        if attachment_bytes:
            msg.add_attachment(attachment_bytes.getvalue(),
                               maintype='application',
                               subtype='pdf',
                               filename=attachment_filename)

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        st.error(f"❌ Email alert failed: {e}")



def extract_json(text):
    try:
        cleaned = re.sub(r"```(json)?", "", text).strip()
        return json.loads(cleaned)
    except Exception:
        st.error("⚠️ Failed to parse generated quiz JSON.")
        raise
def generate_pdf_report(topic, answers):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, f"DSA Quiz Report - {topic}")
    c.setFont("Helvetica", 12)
    y -= 30

    for i, q in enumerate(answers):
        lines = [
            f"Q{i+1}: {q['question']}",
            f"Your Answer: {q['your_answer']}",
            f"Correct Answer: {q['correct_answer']}",
            f"Hint: {q['hint']}",
            f"Explanation: {q['explanation']}"
        ]
        for line in lines:
            if y < 60:
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", 12)
            c.drawString(40, y, line[:100])  # truncate long lines
            y -= 20
        y -= 10

    c.save()
    buffer.seek(0)
    return buffer


def quiz_interface(topic, questions):
    st.subheader(f"🧠 Quiz on {topic}")

    num_questions = len(questions)
    total_duration = timedelta(minutes=num_questions)

    # Initialize or reset quiz session state
    if 'quiz_index' not in st.session_state or st.session_state.get("quiz_topic") != topic:
        st.session_state.quiz_index = 0
        st.session_state.quiz_topic = topic
        st.session_state.quiz_submitted = False
        st.session_state.shuffled_questions = questions
        st.session_state.selected_option = None
        st.session_state.correct_count = 0
        st.session_state.show_hint = False
        st.session_state.quiz_answers = []
        st.session_state.quiz_start_time = datetime.now()
        st.session_state.quiz_duration = total_duration

    # Time check
    time_elapsed = datetime.now() - st.session_state.quiz_start_time
    time_left = st.session_state.quiz_duration - time_elapsed

    if time_left.total_seconds() <= 0:
        st.warning("⏰ Time's up! Submitting the quiz automatically...")
        save_progress(topic, correct=st.session_state.correct_count, total=len(st.session_state.shuffled_questions))
        pdf_buffer = generate_pdf_report(topic, st.session_state.quiz_answers)
        send_email_alert(
            subject=f"🧠 DSA Quiz Report: {topic}",
            message=f"Hi {st.session_state.username},\n\nYour time-bound quiz on '{topic}' has ended. The report is attached.\n\nKeep practicing!",
            attachment_bytes=pdf_buffer,
            attachment_filename=f"{topic}_quiz_report.pdf"
        )
        st.download_button("📄 Download PDF Report", data=pdf_buffer, file_name=f"{topic}_quiz_report.pdf", mime="application/pdf")
        st.stop()

    # LIVE countdown display
    minutes, seconds = divmod(int(time_left.total_seconds()), 60)
    st.info(f"⏳ **Time left:** {minutes:02}:{seconds:02}")

    idx = st.session_state.quiz_index
    if idx >= len(st.session_state.shuffled_questions):
        st.success("🎉 Quiz completed!")
        st.info(f"✅ Correct Answers: {st.session_state.correct_count} out of {len(st.session_state.shuffled_questions)}")

        save_progress(topic, correct=st.session_state.correct_count, total=len(st.session_state.shuffled_questions))

        pdf_buffer = generate_pdf_report(topic, st.session_state.quiz_answers)
        st.download_button("📄 Download PDF Report", data=pdf_buffer, file_name=f"{topic}_quiz_report.pdf", mime="application/pdf")

        send_email_alert(
            subject=f"🧠 DSA Quiz Report: {topic}",
            message=f"Hi {st.session_state.username},\n\nPlease find your quiz report on '{topic}' attached as a PDF.\n\nGreat job and keep learning!",
            attachment_bytes=pdf_buffer,
            attachment_filename=f"{topic}_quiz_report.pdf"
        )
        return

    q = st.session_state.shuffled_questions[idx]
    st.markdown(f"**Question {idx + 1}:** {q['question']}")

    if not st.session_state.show_hint:
        if st.button("💡 Show Hint"):
            st.session_state.show_hint = True
            st.rerun()
    else:
        st.info(f"💡 **Hint:** {q['hint']}")

    st.session_state.selected_option = st.radio(
        "Choose an answer",
        q['options'],
        index=None,
        key=f"radio_{idx}"
    )

    if not st.session_state.quiz_submitted:
        if st.button("Submit"):
            if st.session_state.selected_option is None:
                st.warning("Please select an option before submitting.")
            else:
                st.session_state.quiz_submitted = True
                st.session_state.quiz_answers.append({
                    "question": q["question"],
                    "your_answer": st.session_state.selected_option,
                    "correct_answer": q["answer"],
                    "hint": q["hint"],
                    "explanation": q["explanation"]
                })

                if st.session_state.selected_option == q['answer']:
                    st.success("✅ Correct!")
                    st.session_state.correct_count += 1
                else:
                    st.error("❌ Incorrect.")

    if st.session_state.quiz_submitted:
        st.markdown(f"🧠 **Explanation:** {q['explanation']}")
        btn_label = "Submit Quiz" if idx == len(st.session_state.shuffled_questions) - 1 else "Next Question"
        if st.button(btn_label):
            st.session_state.quiz_index += 1
            st.session_state.quiz_submitted = False
            st.session_state.selected_option = None
            st.session_state.show_hint = False
            st.rerun()
def show_progress():
    st.subheader("📊 Your DSA Progress")
    progress = load_progress()
    if not progress:
        st.info("No progress yet. Take a quiz!")
        return

    dates = sorted(progress.keys())
    topics = sorted({t for daily in progress.values() for t in daily})

    st.write("### 📈 Topic-wise Progress (% Accuracy Over Time)")

    weak_topics = []

    for t in topics:
        accuracy = []
        for d in dates:
            if d in progress and t in progress[d]:
                entry = progress[d][t]

                # ✅ Safe handling of dict/int/malformed cases
                if isinstance(entry, dict) and "correct" in entry and "total" in entry:
                    correct = entry["correct"]
                    total = entry["total"]
                elif isinstance(entry, int):
                    correct = entry
                    total = entry  # assume total = correct if only int stored
                else:
                    correct, total = 0, 0

                acc = round((correct / total) * 100, 2) if total > 0 else 0
                accuracy.append(acc)
            else:
                accuracy.append(None)

        # Detect weak topics (last recorded accuracy < 60%)
        recent_valid = [a for a in accuracy if a is not None]
        if recent_valid and recent_valid[-1] < 60:
            weak_topics.append(t)

        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(dates, accuracy, marker='o', linestyle='-', color='teal')
        ax.set_ylim(0, 100)
        ax.set_title(f"{t} Accuracy Over Time")
        ax.set_ylabel("% Correct")
        ax.set_xlabel("Date")
        st.pyplot(fig)

    if weak_topics:
        st.warning("⚠️ You should focus more on: " + ", ".join(weak_topics))
    else:
        st.success("✅ You're doing well in all topics!")

    # Optional: Latest accuracy summary
    st.write("### 🔢 Latest Accuracy Summary")
    summary_data = []

    for t in topics:
        for d in reversed(dates):
            if d in progress and t in progress[d]:
                entry = progress[d][t]
                if isinstance(entry, dict) and "correct" in entry and "total" in entry:
                    c = entry["correct"]
                    tot = entry["total"]
                elif isinstance(entry, int):
                    c = entry
                    tot = entry
                else:
                    continue  # skip malformed entries

                pct = round((c / tot) * 100, 2) if tot > 0 else 0
                summary_data.append({"Topic": t, "Date": d, "Accuracy (%)": pct})
                break

    if summary_data:
        st.dataframe(summary_data)



def show_scheduler():
    st.subheader("📅 Smart Study Scheduler")
    schedule = load_schedule()

    task = st.text_input("Enter a new task")
    study_date = st.date_input("Select study date", value=date.today())
    study_time = st.time_input("Time to study")

    if st.button("Add Task"):
        task_entry = {
            "task": task,
            "date": str(study_date),
            "time": str(study_time),
            "reminded": False
        }
        schedule.setdefault("tasks", []).append(task_entry)
        save_schedule(schedule)
        st.success(f"Task added: {task} on {study_date} at {study_time}")
        send_email_alert("📚 Study Reminder Added", f"New task: {task} on {study_date} at {study_time}")

    tasks = schedule.get("tasks", [])
    tasks.sort(key=lambda x: (x["date"], x["time"]))
    today = str(date.today())
    now = datetime.now().time()

    if tasks:
        st.write("### 📋 Your Scheduled Tasks")
        for i, t in enumerate(tasks):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.write(f"**{t['task']}** on {t['date']} at {t['time']}")
            with col2:
                if st.button("🗑️", key=f"delete_{i}"):
                    tasks.pop(i)
                    schedule['tasks'] = tasks
                    save_schedule(schedule)
                    st.success("Task deleted.")
                    st.rerun()

            if t.get("date") == today and not t.get("reminded", False):
                task_time = datetime.strptime(t["time"], "%H:%M:%S").time()
                if now >= task_time:
                    st.info(f"⏰ Reminder: {t['task']} scheduled for {t['time']}")
                    send_email_alert("📌 Study Reminder", f"Reminder: {t['task']} is scheduled today at {t['time']}")
                    t['reminded'] = True
                    save_schedule(schedule)

def show_chatbot():
    st.subheader("🤖 DSA Doubt-Resolving Chatbot (Gemini)")
    user_question = st.text_area("💬 Ask your DSA doubt")

    if st.button("Ask Chatbot"):
        if not user_question.strip():
            st.warning("Please type a valid question.")
            return

        try:
            model = genai.GenerativeModel(model_name="gemini-2.0-flash")
            response = model.generate_content(user_question)
            st.success("✅ Here's the explanation:")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"❌ Gemini API Error: {e}")

def main():
    st.set_page_config(page_title="DSA StudyBot", page_icon="🤖", layout="wide")
    st.title("📘 AI DSA StudyBot + Smart Tracker")

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'email' not in st.session_state:
        st.session_state.email = ""

    if not st.session_state.logged_in:
        auth_ui()
        return

    st.sidebar.write(f"👤 Logged in as: {st.session_state.username}")
    st.sidebar.write(f"📧 Email: {st.session_state.email}")
    menu = ["Take Quiz", "Track Progress", "📅 Smart Study Scheduler", "🤖 Ask DSA Doubt", "🔒 Logout"]
    choice = st.sidebar.radio("Select", menu)

    if choice == "Take Quiz":
        topic = st.selectbox("Choose a DSA Topic", ["Array", "Linked List", "Stack", "Queue", "Tree", "Graph", "DP"])
        num = st.selectbox("Number of Questions", [5, 10, 15, 20])
        level = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])

        if st.button("Generate Quiz"):
            prompt = f"""
            Generate {num} multiple choice DSA questions on the topic '{topic}' with {level} difficulty.
            Each question should be in the following JSON format:
            {{
                "question": "Your question?",
                "options": ["A", "B", "C", "D"],
                "answer": "Correct option from above",
                "hint": "Give a hint to solve the question",
                "explanation": "Explain why the answer is correct"
            }}
            Output only valid JSON array.
            """

            try:
                model = genai.GenerativeModel(model_name="gemini-2.0-flash")
                response = model.generate_content(prompt)
                questions = extract_json(response.text)
                st.session_state.shuffled_questions = questions
                quiz_interface(topic, questions)
            except Exception as e:
                st.error(f"❌ Failed to generate questions: {e}")

        elif 'shuffled_questions' in st.session_state:
            quiz_interface(topic, st.session_state.shuffled_questions)

    elif choice == "Track Progress":
        show_progress()
    elif choice == "📅 Smart Study Scheduler":
        show_scheduler()
    elif choice == "🤖 Ask DSA Doubt":
        show_chatbot()
    elif choice == "🔒 Logout":
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.email = ""
        st.success("Logged out successfully.")
        st.rerun()

if __name__ == "__main__":
    main()

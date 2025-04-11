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

# Folder setup
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
    st.sidebar.subheader("\U0001F510 Login or Signup")
    users = load_users()
    action = st.sidebar.radio("Choose Action", ["Login", "Signup"])

    if action == "Signup":
        new_user = st.sidebar.text_input("Create Username")
        new_email = st.sidebar.text_input("Your Email")
        new_pass = st.sidebar.text_input("Create Password", type="password")
        if st.sidebar.button("Signup"):
            if new_user in users:
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

def load_questions():
    with open('data/dsa_questions.json', 'r') as f:
        return json.load(f)

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

def save_progress(topic, increment=1):
    today = str(date.today())
    progress = load_progress()

    if today not in progress:
        progress[today] = {}
    if topic not in progress[today]:
        progress[today][topic] = 0
    progress[today][topic] += increment

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

def send_email_alert(subject, message, to_email=None):
    try:
        from_email = "ai.smart.study.bot@gmail.com"
        password = ""
        if to_email is None:
            to_email = st.session_state.get('email')

        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        st.error(f"❌ Email alert failed: {e}")

def quiz_interface(topic, questions):
    st.subheader(f"\U0001F9E0 Quiz on {topic}")

    if 'quiz_index' not in st.session_state or st.session_state.get("quiz_topic") != topic:
        st.session_state.quiz_index = 0
        st.session_state.quiz_topic = topic
        st.session_state.quiz_submitted = False
        st.session_state.shuffled_questions = random.sample(questions, len(questions))
        st.session_state.selected_option = None
        st.session_state.correct_count = 0
        st.session_state.show_hint = False

    idx = st.session_state.quiz_index
    if idx >= len(st.session_state.shuffled_questions):
        st.success("\U0001F389 Quiz completed!")
        st.info(f"✅ Correct Answers: {st.session_state.correct_count} out of {len(st.session_state.shuffled_questions)}")
        save_progress(topic, st.session_state.correct_count)
        return

    q = st.session_state.shuffled_questions[idx]

    st.markdown(f"**Question {idx + 1}:** {q['question']}")

    if not st.session_state.show_hint:
        if st.button("\U0001F4A1 Show Hint"):
            st.session_state.show_hint = True
            st.rerun()
    else:
        st.info(f"\U0001F4A1 **Hint:** {q['hint']}")

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
                if st.session_state.selected_option == q['answer']:
                    st.success("✅ Correct!")
                    st.session_state.correct_count += 1
                else:
                    st.error("❌ Incorrect.")
    if st.session_state.quiz_submitted:
        st.markdown(f"\U0001F9E0 **Explanation:** {q['explanation']}")
        btn_label = "Submit Quiz" if idx == len(st.session_state.shuffled_questions) - 1 else "Next Question"
        if st.button(btn_label):
            st.session_state.quiz_index += 1
            st.session_state.quiz_submitted = False
            st.session_state.selected_option = None
            st.session_state.show_hint = False
            st.rerun()

def show_progress():
    st.subheader("\U0001F4CA Your DSA Progress")
    progress = load_progress()
    if not progress:
        st.info("No progress yet. Take a quiz!")
        return

    dates = list(progress.keys())
    topics = set()
    for daily in progress.values():
        topics.update(daily.keys())

    topics = sorted(topics)

    topic_data = {t: [] for t in topics}
    for d in dates:
        for t in topics:
            topic_data[t].append(progress[d].get(t, 0))

    st.write("### Progress Over Time")
    fig, ax = plt.subplots(figsize=(10, 5))
    for t in topics:
        ax.plot(dates, topic_data[t], marker='o', label=t)
    ax.set_xlabel("Date")
    ax.set_ylabel("Questions Solved")
    ax.set_title("DSA Progress (Topic-wise)")
    ax.legend()
    st.pyplot(fig)

def show_scheduler():
    st.subheader("\U0001F4C5 Smart Study Scheduler")
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
        send_email_alert("\U0001F4DA Study Reminder Added", f"New task: {task} on {study_date} at {study_time}")

    tasks = schedule.get("tasks", [])
    tasks.sort(key=lambda x: (x["date"], x["time"]))

    today = str(date.today())
    current_time = datetime.now().strftime("%H:%M:%S")

    if tasks:
        st.write("### \U0001F4C4 Your Scheduled Tasks")
        for i, t in enumerate(tasks):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.write(f"**{t['task']}** on `{t['date']}` at `{t['time']}`")
            with col2:
                if st.button("🗑️", key=f"delete_{i}"):
                    tasks.pop(i)
                    schedule['tasks'] = tasks
                    save_schedule(schedule)
                    st.success("Task deleted.")
                    st.rerun()

            if t.get("date") == today and not t.get("reminded", False) and current_time >= t["time"]:
                st.info(f"⏰ Reminder: {t['task']} scheduled for {t['time']}")
                send_email_alert("📌 Study Reminder", f"Reminder: {t['task']} is scheduled today at {t['time']}")
                t['reminded'] = True
                save_schedule(schedule)
def show_chatbot():
    st.subheader("🤖 DSA Doubt-Resolving Chatbot (Gemini)")

    # Load your Gemini API Key
    genai.configure(api_key="")

    user_question = st.text_area("💬 Ask your DSA doubt (e.g., What is memoization in DP?)")

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
    st.set_page_config(page_title="DSA StudyBot", page_icon="\U0001F916", layout="wide")
    st.title("\U0001F4DA AI DSA StudyBot + Smart Tracker")

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'email' not in st.session_state:
        st.session_state.email = ""

    if not st.session_state.logged_in:
        auth_ui()
        return

    st.sidebar.write(f"👤 Logged in as: `{st.session_state.username}`")
    st.sidebar.write(f"📧 Email: `{st.session_state.email}`")
    menu = ["Take Quiz", "Track Progress", "\U0001F4C5 Smart Study Scheduler","🤖 Ask DSA Doubt", "\U0001F512 Logout"]
    choice = st.sidebar.radio("Select", menu)

    try:
        data = load_questions()
        topics = sorted(data.keys())
    except Exception as e:
        st.error(f"Error loading questions: {e}")
        return

    if choice == "Take Quiz":
        selected_topic = st.selectbox("Choose a topic", topics)
        topic_questions = data[selected_topic]
        quiz_interface(selected_topic, topic_questions)

    elif choice == "Track Progress":
        show_progress()

    elif choice == "\U0001F4C5 Smart Study Scheduler":
        show_scheduler()
    elif choice == "🤖 Ask DSA Doubt":
        show_chatbot()
    

    elif choice == "\U0001F512 Logout":
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.email = ""
        st.success("Logged out successfully.")
        st.rerun()

if __name__ == "__main__":
    main()

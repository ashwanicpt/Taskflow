# 📖 User Guide: How to Use TaskFlow

Welcome to TaskFlow! This guide will help you master all the features of your new task management system and AI assistant.

## 🏗️ 1. Task Management

TaskFlow makes it easy to keep your life organized with a clean, modern interface.

✅ Creating Tasks

1.  Click the "Create New Task" button at the top of your dashboard.
2.  Enter a Title and Description.
3.  Set a Priority (High, Medium, or Low).
4.  Select a Due Date to stay on track.

📋 Managing the List

Status Badges: Tasks are color-coded by status (e.g., PENDING in yellow, COMPLETED in green).
Sorting: Use the dropdown at the top to sort your tasks by Newest, Due Date, or Priority.
Overdue Alerts: If a task's due date has passed, it will automatically highlight in red to grab your attention.

## 🤖 2. Using the AI Agent (ChatGPT-Style)

Your TaskFlow assistant is more than just a chatbot—it can actually perform actions for you!

💬 Starting a Chat

Click the floating blue bubble at the bottom-right of your screen to open the AI Agent.

🚀 What the AI can do for you

You can talk to the agent in plain English. Try commands like:

"Create a task called 'Submit project' for tomorrow."
"I need to go to the gym on Friday, set it as high priority."
"Show me my current tasks."
"Delete my gym task."

📁 Chat History & Sessions

Sessions: Every separate conversation is saved as a "Session" in the left sidebar.
New Chat: Click the "+ New chat" button to start a fresh interaction.
Switching: Click any previous session in the sidebar to instantly reload that conversation.

⚙️ Managing Sessions (Three-Dot Menu ⋮)

Hover over any chat in the sidebar to see the three-dots. Click them to:

✏️ Rename: Give your conversation a specific name.
🗑️ Delete: Permanently remove a chat session from your history.

## 🔔 3. Features & Productivity

🌓 Dark Mode

Toggle the theme by clicking the 🌓 icon in the top navigation bar. The app will remember your preference automatically.

🔔 Smart Notifications

The Bell icon in the navbar will light up and show a red badge if you have Urgent or Overdue tasks. Click it to see a quick list of what needs your immediate attention.

## 💬 4. Prompting Examples (Best Practices)

The AI Agent understands natural language. Here are some effective ways to communicate with it:

📝 Creating Tasks

Simple: "Add a task for buying milk."
With Priority: "Create a high priority task for the client meeting."
With Deadlines: "Add a task 'Finish Report' due this Friday at 5pm."
Specific: "Remind me to call the doctor on Monday morning, set priority to medium."

🔍 Viewing & Managing

List All: "Show me all my tasks." or "What's on my to-do list?"
Check Status: "Do I have any pending tasks?"
Search: "Find my gym task."

🗑️ Deleting Tasks

By Name: "Delete the task called gym."
Direct: "Remove 'Buy milk' from my list."

💡 General Interaction

Help: "What can you help me with?"
Reset: If you want to start over, just click the "+ New chat" button in the sidebar.

💡 Pro Tip

The AI Agent is best used for quick task creation. If you're in a hurry, just type "Add buying groceries to my list for 6pm tonight" and let the AI handle the forms for you!

## 📎 5. Import Tasks from a File

### Use the upload feature

1. Sign in and open the AI Agent using the floating chat button.
2. Click the paperclip button beside the message input.
3. Choose a `.xlsx` Excel workbook or a `.docx` Word document.
4. The agent extracts task titles and descriptions, then creates the tasks for your account.

Uploads create tasks immediately; there is no review or confirmation screen. Existing task titles for your account are skipped and reported in the chat. Imported tasks use medium priority and have no due date unless the task is edited afterward.

### File formats

Excel workbooks must have a header row with `title` and `description` columns. Header matching ignores capitalization and spaces, so `Task Title` and `Task Description` are also accepted. The active worksheet is read.

Word documents can use a table with `title` and `description` columns. If no matching table exists, the document text is sent to Gemini to extract tasks. The document should clearly identify task titles and descriptions; Gemini is instructed not to invent tasks.

Only `.xlsx` and `.docx` are supported. Older `.xls` and `.doc` files, PDFs, and files larger than 5 MB are rejected. A file may contain up to 100 tasks.

### Implementation overview

- `templates/base.html` provides the paperclip control and sends the selected file to `POST /agent/upload` as multipart form data.
- `src/frontend/router.py` authenticates the request, extracts tasks, skips duplicate titles belonging to the signed-in user, creates the remaining tasks, and records the import in chat history.
- `src/agent/file_import.py` reads Excel rows with `openpyxl` and Word documents with `python-docx`. Unstructured Word text is sent to Gemini, then checked for task titles and descriptions before creation.
- `requirements.txt` lists `openpyxl` and `python-docx`, in addition to the existing `python-multipart` upload dependency.

To install the dependencies and run the application locally:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 📋 6. Application Logs

Sign in and select **Application Logs** in the navigation bar to view application and server logs. The page supports severity and text filters, shows 100 entries per page with the newest first, and lets you page through all retained entries. Access requires a valid signed-in session.

Logs are written to `logs/application.log` and rotated after 2 MB, keeping up to five previous files. The `logs/` directory is excluded from Git. A new log file is created when the application starts and begins recording.

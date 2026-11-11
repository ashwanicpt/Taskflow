# TaskFlow - FastAPI Task Management Application

A modern Task Management System built with **FastAPI**, **Jinja2 Templates**, and **PostgreSQL**.

For a detailed guide on how to use all the features, see [USAGES.md](USAGES.md).

## 🌟 Key Features
- **Integrated Frontend**: Complete UI for login, registration, and task CRUD.
- **Task Priority**: High, Medium, and Low priorities with status badges.
- **Due Dates**: Set deadlines and automatically see overdue tasks in red.
- **Smart Sorting**: Sort tasks by Newest First, Priority, or Due Date.
- **Authentication**: Modern authentication with JWT and secure browser cookies.

---

## 🚀 Getting Started

### Run locally

Create and activate a virtual environment, then install dependencies:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set the required `DB_CONNECTION`, `SECRET_KEY`, `ALGORITHM`, and `EXP_Time` environment variables (or configure them in a local `.env` file). Set `GOOGLE_API_KEY` to enable the AI assistant.

Start the app:

```bash
python -m uvicorn main:app --reload
```

### Deploy to Render

1. Push the project to a GitHub repository. Do not commit `.env`, virtual environments, local database files, or API keys.
2. In Render, choose **New → Blueprint** and connect the repository containing `render.yaml`.
3. Review the Blueprint. It creates the `taskflow-app` web service and a PostgreSQL database.
4. Before deploying, provide `GOOGLE_API_KEY` in the web service's environment settings. The AI assistant requires a valid Google AI API key.
5. Apply the Blueprint and wait for the build and deploy to finish.
6. Open the web service's `onrender.com` URL and sign in or register.

The Blueprint generates `SECRET_KEY` and connects the app to its PostgreSQL database. It sets `/login` as the health check. If deployment fails, check **Events** and **Logs** in the Render dashboard.

> **Free-plan note:** Render's free web services spin down when idle, and their local files (including this app's log files) are ephemeral. Free Render Postgres expires 30 days after creation. Use a paid database plan for data you need to keep; see [Render's free-instance limitations](https://render.com/docs/free).

---

## 🏗️ Project Structure
- `main.py`: Application entry point and router integration.
- `src/frontend/`: Jinja2 frontend routes.
- `src/tasks/`: Task models, controllers, and schemas.
- `src/user/`: User authentication and registration.
- `templates/`: HTML templates.
- `static/`: CSS and frontend assets.

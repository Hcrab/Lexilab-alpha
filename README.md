# Lexilab Alpha

**English** · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

This is a quiz platform for practicing English. Teachers enter vocabulary and publish quizzes; students review meanings, fill in blanks, write sentences of their own, then revisit their scores and mistakes. It uses Next.js and Flask, with MongoDB for data storage.

The project was later rebuilt in [LexilabCode](https://github.com/Hcrab/LexilabCode), with the frontend moving from Next.js to react-scripts.

![The Lexilab Alpha student home screen, captured with fictional demo data](docs/media/home.png)

![A browser recording of the three-stage quiz flow](docs/media/quiz-walkthrough.gif)

| Quiz library | View word meanings |
| --- | --- |
| ![Today's and earlier quizzes](docs/media/quiz-library.png) | ![The vocabulary review stage](docs/media/quiz-review.png) |

| Fill in the blanks | Review an attempt |
| --- | --- |
| ![A fill-in-the-blank question with its word bank](docs/media/quiz-fill.png) | ![Quiz results and question-by-question feedback](docs/media/quiz-results.png) |

| Learning progress | Teacher tools |
| --- | --- |
| ![Completion, pass rate, and upcoming quizzes](docs/media/progress.png) | ![The quiz management screen](docs/media/admin-quizzes.png) |

These screens were captured in a local browser with fictional accounts. No real student records are included.

## Practice flow

```mermaid
flowchart LR
    T["Teacher enters words and publishes a quiz"] --> Q["Student opens today's quiz"]
    Q --> V["Review word meanings"]
    V --> B["Fill in the blanks"]
    B --> S["Write sentences with the target words"]
    S --> F["See scores and feedback"]
    F --> R["Bookmark mistakes and revisit attempts"]
    F --> P["Track learning progress"]
```

Each quiz has three stages: vocabulary review, fill-in-the-blanks, and sentence writing. Students can save their place, then see their scores, AI feedback, and earlier attempts after submitting. Teachers can manage users, word pools, quizzes, and statistics.

## Architecture

```mermaid
flowchart LR
    U["Student and teacher browsers"] --> N["Next.js: pages and API proxy"]
    N --> F["Flask: accounts, quizzes, results, and admin tools"]
    F --> M["MongoDB: users, questions, attempts, and saved mistakes"]
    F -.->|With an API key configured| A["DeepSeek: quiz authoring and sentence feedback"]
```

`frontend/` contains the Next.js 16, React 19, and TypeScript pages; `backend/` contains the Flask API. MongoDB stores users, quizzes, attempts, and bookmarks. The AI integration is optional: without a provider key, you can still browse the demo quizzes and existing results, but live generation and grading will not work.

## Run it locally

You will need Node.js, Python 3.11+, and a MongoDB instance listening only on your machine. The commands below use PowerShell; keep the frontend and backend in separate terminals.

1. Copy `.env.example` to `.env`. Generate a random `SECRET_KEY` and point `MONGO_URI` at your local MongoDB. To load the sample data, set `MONGO_DB_NAME=lexilab_alpha_demo` and choose a `DEMO_PASSWORD` of at least 12 characters. Do not commit `.env`.
2. Install and start the backend:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
   .\.venv\Scripts\python.exe demo\seed.py
   cd backend
   ..\.venv\Scripts\python.exe app.py
   ```

3. Start the frontend in another terminal:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

Open `http://127.0.0.1:3000`. The demo accounts are `demo_learner` and `demo_teacher`; both use the `DEMO_PASSWORD` you set in `.env`. The seed script accepts only a loopback MongoDB connection and the `lexilab_alpha_demo` database, and creates only fictional users, quizzes, and results. To try live AI grading, set `DEEPSEEK_API_KEY` separately.

## What this archive keeps

- The student's quiz, review, bookmark, progress, and profile screens, plus the teacher's quiz and user-management screens.
- Flask endpoints for authentication, word pools, quizzes, results, statistics, and AI features.
- A repeatable fictional-data seed script for recreating the main README screens.

I rebuilt this public copy from an old server archive. It does not include the old Git history, environment files, runtime logs, databases, student records, or downloaded dependencies. During the cleanup, I removed hard-coded credential fallbacks and request-header logging, closed a draft-quiz access bypass, and added login checks to results, progress, bookmarks, and AI requests.

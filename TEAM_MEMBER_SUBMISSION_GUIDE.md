# 🚨 Team Member Individual Submission Guide — Apex HackQube
## Step-by-Step Instructions for EVERY Team Member

> [!CAUTION]
> **HACKATHON ORGANIZER MANDATE:**
> Every individual team member must submit the Google Form individually with their own GitHub repository and submission proof screenshot. Submitting only as the team leader will result in disqualification of individual team members!

Follow these 4 simple steps to complete your submission in 5 minutes:

---

### STEP 1: Fork or Push Code to Your Personal GitHub Account

Each member needs the repository under their own GitHub username. Choose either **Option A** (Easiest - Fork) or **Option B** (Push direct):

#### **Option A: GitHub Web Fork (Recommended - 30 seconds)**
1. Open the primary repository:  
   👉 [https://github.com/aaditya-cse/Ecommerce-_Segementation_and_Sales_Performance_Project](https://github.com/aaditya-cse/Ecommerce-_Segementation_and_Sales_Performance_Project)
2. Click the **"Fork"** button in the top-right corner.
3. Select your personal GitHub account as the owner and click **"Create fork"**.
4. Your personal submission link will now be:  
   `https://github.com/<YOUR_GITHUB_USERNAME>/Ecommerce-_Segementation_and_Sales_Performance_Project`

#### **Option B: Push via Git Terminal**
If you want to push directly to a new repository on your account:
1. Create a new empty repository on your GitHub named:  
   `Ecommerce-_Segementation_and_Sales_Performance_Project`
2. Open terminal in the project folder and run:
   ```bash
   git remote set-url origin https://github.com/<YOUR_GITHUB_USERNAME>/Ecommerce-_Segementation_and_Sales_Performance_Project.git
   git branch -M main
   git push -u origin main
   ```

---

### STEP 2: Submission Proof Screenshots to Capture

The Google Form asks for a **screenshot / proof showing that you have successfully submitted your project or run it**.

Prepare either of these 3 high-impact screenshots:

#### 📸 Proof Option 1: Terminal Proof (28/28 Pytest Tests Passing)
Open terminal in the project folder and run:
```bash
.\multi_agent\.venv\Scripts\pytest.exe -v test/test_agent_pipeline.py
```
Take a screenshot showing:
```text
============================= 28 passed in 7.66s =============================
```
*(This proves full technical implementation and enterprise test coverage).*

#### 📸 Proof Option 2: Live Web App Running Locally
1. Start the app:
   ```bash
   python app.py
   ```
2. Open `http://127.0.0.1:5000` in your browser.
3. Click **"Run 5-Agent Swarm Intelligence"**.
4. Take a screenshot of the completed **Executive Intelligence Dashboard** showing the KPI cards, Data Hygiene score badge (99.1%), and generated charts.

#### 📸 Proof Option 3: Your Personal GitHub Repository
Take a full-window screenshot of your personal GitHub repository page showing the codebase, commit history, and `README.md`.

---

### STEP 3: Complete the Google Form

When the form opens, paste the following answers:

| Google Form Field | Your Input |
| :--- | :--- |
| **Team Name** | `Apex HackQube` |
| **Your Name** | `<YOUR FULL NAME>` |
| **Project Title** | `AgentOps BI Studio` |
| **Project Tagline** | `Autonomous 5-Agent Multi-Agent Swarm for Enterprise E-Commerce Intelligence` |
| **Project Repo URL** | `https://github.com/<YOUR_USERNAME>/Ecommerce-_Segementation_and_Sales_Performance_Project` |
| **Presentation Link** | `https://drive.google.com/file/d/1AblgKGlnSa7Ee54aVt3bQsTRni_cD8d_/view?usp=sharing` (or `https://docs.google.com/presentation/d/1wVW9v0u4WCwyx49aPKY3M9Mh2DkFNCZzUtvfvQuGTuQ/edit`) |
| **Project Description** | *(Copy from `PROJECT_SUBMISSION_KIT.md` Section 2 or 3)* |
| **Tech Stack** | `Python, LangGraph, LangChain, Groq LLMs, NumPy, Pandas, Scikit-Learn, Flask, AST Sandbox, Web Audio API` |
| **Submission Proof** | Upload the screenshot captured in **Step 2**. |

---

### STEP 4: Verify & Notify Team

Once you click **Submit** on Google Form:
1. Take a screenshot of the Google Form confirmation page (*"Your response has been recorded"*).
2. Save this screenshot for your personal records in case organizers request verification.
3. Drop a message in your team chat: *"Submitted individually! 🚀"*.

---
*Created for Team Apex HackQube — Let's bring home the 1st prize! 🏆*

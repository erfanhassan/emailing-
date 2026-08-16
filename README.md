# AI Outreach Dashboard

![Python](https://img.shields.io/badge/Python-3.11-blue.svg) ![License](https://img.shields.io/badge/License-MIT-green.svg) ![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg) ![Build](https://img.shields.io/badge/Build-Passing-brightgreen.svg)

**Human-in-the-loop AI cold outreach that finds leads, verifies emails, and sends personalized campaigns — all from a sleek dashboard.**

## 🌟 Why This Exists

Cold outreach is broken: generic emails get ignored, lead lists are stale, and manual follow-up is a time sink. **AI Outreach Dashboard** solves this by combining **AI-powered lead generation**, **email verification**, and **personalized drafting** into one streamlined workflow. You stay in control with a human-in-the-loop approval step, ensuring every email is on-brand and effective. Whether you're a startup founder, sales team, or marketer, this tool turns outreach from a chore into a growth engine.

## ✨ Key Features

- **AI-Powered Lead Scraping**: Automatically discover leads from the web using DuckDuckGo search and website scraping.
- **Smart Email Verification**: Validate email addresses before sending to reduce bounces and protect your sender reputation.
- **Personalized Email Drafting**: Leverage DeepSeek AI to draft tailored emails for each lead based on their website content.
- **Human-in-the-Loop Approval**: Review and edit every email before it goes out — no rogue bots.
- **Geo-Targeted Search**: Find leads by location with integrated geo-search capabilities.
- **Google Sheets Integration**: Seamlessly sync leads and campaign data with Google Sheets.
- **Background Worker**: Schedule and automate sending with APScheduler and FastAPI.
- **Interactive Dashboard**: Built with Streamlit and Plotly for real-time analytics and campaign management.

## 🛠️ Tech Stack & Architecture

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit, Plotly, Pandas |
| Backend | FastAPI, Uvicorn, APScheduler |
| AI | OpenAI, DeepSeek (via ai_agent.py) |
| Data Sources | DuckDuckGo Search, BeautifulSoup, Google Sheets (gspread) |
| Email | SMTP, email_verifier, email_sender |
| Deployment | Docker, Streamlit Cloud, local scripts |

**Architecture Overview:**

```
[User] <-> [Streamlit Dashboard] <-> [FastAPI Worker]
                |                        |
                v                        v
        [Scraper/Geo Search]    [Email Sender/Verifier]
                |                        |
                +-----> [AI Agent] <----+
```

The dashboard handles user interaction, the background worker manages scheduled tasks, and the AI agent orchestrates lead generation, email drafting, and verification.

## 📦 Quickstart & Installation

### Prerequisites
- Python 3.11+
- Google Sheets API credentials (for sheet sync)
- SMTP credentials or API keys for email sending
- OpenAI or DeepSeek API key for AI drafting

### Installation

```bash
# Clone the repository
git clone https://github.com/erfanhassan/emailing-.git
cd emailing-

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # Edit with your keys

# Run the Streamlit app
streamlit run app.py
```

### Docker Deployment

```bash
docker build -t ai-outreach-dashboard .
docker run -p 8501:8501 -p 8000:8000 ai-outreach-dashboard
```

## 📸 Screenshots

*Add screenshots of your dashboard here (e.g., `assets/dashboard.png`).*

![Dashboard Preview](assets/dashboard.png)

## 🤝 Contributing & Community

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) to get started. Whether you're fixing bugs, adding features, or improving documentation, your help is appreciated.

- **Report Issues**: [GitHub Issues](https://github.com/erfanhassan/emailing-/issues)
- **Submit PRs**: Fork the repo and create a pull request.
- **Join the Discussion**: Start a discussion in the GitHub Discussions tab.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Star this repo** ⭐ if you find it useful! Your support helps us grow and improve.
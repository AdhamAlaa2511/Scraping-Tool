# 🕵️ Competitor Intelligence Dashboard

**A powerful, self-hosted system to track competitor websites, detect changes, and visualize insights in a modern, real-time dashboard.**

![Dashboard Preview](https://via.placeholder.com/800x400?text=Competitor+Intelligence+Dashboard)

## 🚀 Features

-   **👀 Visual Change Detection**: Automatically monitors competitor pages (Pricing, Features, Blogs) and highlights what changed.
-   **⚡ Modern UI**: sleek interface with **Toast Notifications**, **Modals**, and **Real-time Updates**.
-   **🔔 Smart Notifications**: Get alerts via Email or Slack whenever a change is detected.
-   **📊 Interactive Dashboard**:
    -   **Overview**: Key stats at a glance.
    -   **Competitors**: Manage observed sites with easy "Edit" and "Delete" actions (with safe confirmation modals).
    -   **Changes Feed**: A timeline of all detected changes with a direct "🔗 Visit" link to the source.
-   **🛠️ Robust Scraper**: Handles various HTML structures and preserves data integrity.
-   **💾 SQLite Database**: Reliable local storage for all historical data.

---

## 🛠️ Quick Start

### 1. Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/AdhamAlaa2511/Scraping-Tool.git
cd Scraping-Tool
pip install -r requirements.txt
```

### 2. Configuration

Open `config.yaml` and add the competitors you want to track:

```yaml
competitors:
  - name: "Example Corp"
    website: "https://example.com"
    pages:
      - url: "https://example.com/pricing"
        type: "pricing"
        selector: ".pricing-table"  # Optional: CSS selector to target specific content
  
  - name: "Another Competitor"
    website: "https://another.com"
    pages:
      - url: "https://another.com/news"
        type: "blog"
        selector: "article"

dashboard:
  host: 0.0.0.0
  port: 5000
  debug: true
```

### 3. Run the Dashboard

Start the web application:

```bash
python dashboard.py
```

Open your browser and navigate to: **[http://localhost:5000](http://localhost:5000)**

---

## 🖥️ Usage Guide

### Managing Competitors
-   **Add**: Use the "Add Competitor" form in the **Competitors** tab.
-   **Edit**: Click the **✏️ Edit** button on any competitor card to update their tracked pages or details (opens a modal).
-   **Delete**: Click **🗑️ Delete** to remove a competitor (requires confirmation).

### Monitoring Changes
-   **Run Scraper**: Click the **🔄 Run Scraper** button in the dashboard to trigger an immediate check.
-   **View Details**: Click **👁️ View** to see exactly which pages are being tracked for a competitor.
-   **Visit Source**: In the **Changes** tab, click **🔗 Visit** to jump directly to the page where a change was detected.

### Automated Scheduling
To keep tracking in the background, run the scheduler:

```bash
python scheduler.py
```

This will run the scraper periodically based on the `check_interval_hours` in your `config.yaml`.

---

## ⚙️ Advanced Setup

### Notifications
Configure Email or Slack alerts in `config.yaml` to stay updated without checking the dashboard.

**Email:**
```yaml
notifications:
  email:
    enabled: true
    sender_email: "your@gmail.com"
    sender_password: "your-app-password"
    recipient_emails: ["team@company.com"]
```

**Slack:**
```yaml
notifications:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK"
```

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
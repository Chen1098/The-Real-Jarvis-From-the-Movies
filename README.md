# Jarvis AI Assistant

A sophisticated AI assistant modeled after J.A.R.V.I.S. from Iron Man, featuring voice control, WhatsApp integration, intelligent system control, meeting memory, and proactive assistance.

##  Features

### Core Capabilities
-  Answers your WhatsApp messages if it knows how to
  - this is based on previous chats with WhatsApp or through Jarvis, so It'll remember your preferences and things.
  - Including your meetings, preferences, and when you're busy.
- helps you reply to WhatsApp
- has access to your browser, so it can open up things for you.

- has access to your computer, so it can open browsers, files, apps, etc

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Microphone access**
- **Node.js 18+** (for WhatsApp integration)
- **API Keys:**
  - OpenAI API key ([Get here](https://platform.openai.com/api-keys))
  - Porcupine wake word key ([Get here](https://console.picovoice.ai/))

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Friday
   ```

2. **Create virtual environment**
   
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   
3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Node.js dependencies and run the bridge**
   
   ```bash
   cd friday/integrations
   npm install
   node whatsapp_bridge.js
   cd ../..
   ```
   
5. **Configure API keys**

   Create `.env` file in the root directory:
   ```bash
   OPENAI_API_KEY=sk-...
   PORCUPINE_ACCESS_KEY=your_porcupine_key
   ```

6. **Run Jarvis**
   ```bash
   python run.py
   ```

---

##  WhatsApp Setup

Jarvis can monitor your WhatsApp messages and auto-reply intelligently.

### Setup Steps

1. **Start WhatsApp bridge service**

   ```bash
   cd friday/integrations
   node whatsapp_bridge.js
   ```
   
2. **Scan QR code**
   - A QR code will appear in the terminal
   - Open WhatsApp on your phone → Settings → Linked Devices → Link a Device
   - Scan the QR code
   - WhatsApp is now connected!

3. **Start Jarvis**
   ```bash
   python run.py
   ```
   
4. **Test it out**
   - Have someone send you a WhatsApp message
   - Jarvis will analyze it and decide whether to auto-reply or notify you
   - Check logs to see Jarvis's decision-making process

### How WhatsApp Auto-Reply Works

1. **Incoming message** → WhatsApp bridge sends to Jarvis
2. **Context gathering:**
   - Last 50 messages with this contact
   - Your last 30 statements to Jarvis (user context)
   - Current time, date, day of week
   - Your stored meeting memory
3. **GPT-4o decision:** Based on `prompt.txt`, Jarvis decides:
   - `SHOULD_SEND=YES` → Auto-reply (50%+ confidence)
   - `SHOULD_SEND=NO` → Just notify you
4. **Conflict checking:** Jarvis checks stored meetings for conflicts
5. **Auto-reply sent** (if confident) + you're notified

### Auto-Reply Confidence Levels

- **50%+ confidence** → Jarvis auto-replies
- **Close relations** (family, close friends) → More likely to accept
- **Casual contacts** → Moderate acceptance
- **When you're free** (no meeting conflicts) → Default to YES
- **When you're busy** → Automatically declines with reason

---

## ⚙️ Configuration

### prompt.txt

Located at root: `prompt.txt`

This is Jarvis's personality and behavior definition. Edit this to customize:
- Personality traits
- Speech patterns
- Decision-making rules
- WhatsApp auto-reply behavior
- Meeting memory instructions

**Important:** Changes to `prompt.txt` take effect immediately on next conversation.

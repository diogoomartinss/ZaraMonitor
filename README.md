# 👗 Zara Stock Monitor Discord Bot

A Discord bot that monitors the stock status of Zara products and notifies your server when items come back in stock. Designed to be simple, configurable, and slash-command friendly.

---

## 📦 Features

- 🔍 Monitor any Zara product by URL  
- 🛎️ Notifies when sizes are back in stock  
- ⚙️ Slash command interface for ease of use  
- 🧼 Chat cleanup support  
- 🧠 Persistent tracking across sessions  
- 🌍 Regional support via Zara store country ID  

---

## 🔧 Configuration

All config is stored in a `config.json` file:

```json
{
    "country_id" : "10702", // Country id for Portugal
    "discord_token": "YOUR_DISCORD_TOKEN_GOES_HERE"
} 
```

## 🚀 Setup & Installation
### 1. Clone the Repo

```
git clone https://github.com/diogoomartinss/ZaraMonitor.git
cd ZaraMonitor
```

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Customize config.json
### 4. Run the bot
```
python DiscordBot.py
```

## 🗂️ Slash Commands
### /monitor url role img_url
Start monitoring a Zara product.

url: Link to the Zara product page

role: Discord role to mention when stock is detected

img_url: Image to include in the alert embed

### /stop index
Stop monitoring a product or list monitored products

### /status
Check the current monitoring status of all products

### /clear
Clear the channel history

## 🧠 How It Works

Parses Zara product data based on country ID in config.json

Periodically checks stock availability (interval set in code)

If a previously out-of-stock item is back, it sends an embedded message to the channel, pinging a designed role

Avoids duplicate notifications by storing state

## 📸 Example Alert

![Zara Bot Example](https://i.imgur.com/QNZeb0z.png)

## 📄 License

MIT License

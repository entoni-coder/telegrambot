import os
import logging
import json
import hashlib
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from dotenv import load_dotenv

# Configurazione iniziale
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Stati della conversazione
REGISTER, BUY_SPINS = range(2)

# Configurazione della ruota
WHEEL_PRIZES = [
    {"value": 10, "probability": 40, "label": "10 GKY", "color": "#FF6384"},
    {"value": 20, "probability": 30, "label": "20 GKY", "color": "#36A2EB"},
    {"value": 50, "probability": 15, "label": "50 GKY", "color": "#FFCE56"},
    {"value": 100, "probability": 10, "label": "100 GKY", "color": "#4BC0C0"},
    {"value": 200, "probability": 4, "label": "200 GKY", "color": "#9966FF"},
    {"value": 500, "probability": 1, "label": "500 GKY", "color": "#FF9F40"}
]

# Pacchetti spin disponibili
SPIN_PACKAGES = {
    '3_spins': {'spins': 3, 'price': 300, 'label': "3 spin - 300 GKY"},
    '5_spins': {'spins': 5, 'price': 500, 'label': "5 spin - 500 GKY"},
    '10_spins': {'spins': 10, 'price': 1000, 'label': "10 spin - 1000 GKY"}
}

# Inizializzazione database
def init_db():
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        wallet TEXT NOT NULL,
        balance INTEGER DEFAULT 100,
        spins INTEGER DEFAULT 3,
        referral_code TEXT UNIQUE,
        username TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        tx_type TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Funzioni database
def get_user(user_id):
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        columns = ['user_id', 'first_name', 'last_name', 'phone', 'wallet', 'balance', 'spins', 'referral_code', 'username', 'registered_at']
        return dict(zip(columns, user))
    return None

def update_user(user_id, updates):
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    
    set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [user_id]
    
    cursor.execute(f'UPDATE users SET {set_clause} WHERE user_id = ?', values)
    conn.commit()
    conn.close()

def create_user(user_data):
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    
    columns = ', '.join(user_data.keys())
    placeholders = ', '.join(['?'] * len(user_data))
    
    cursor.execute(f'INSERT INTO users ({columns}) VALUES ({placeholders})', list(user_data.values()))
    conn.commit()
    conn.close()

def create_transaction(user_id, amount, tx_type):
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO transactions (user_id, amount, tx_type)
    VALUES (?, ?, ?)
    ''', (user_id, amount, tx_type))
    
    conn.commit()
    conn.close()

# Handlers principali
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        logger.info(f"User {user_id} ha attivato /start")
        
        user = get_user(user_id)
        
        if not user:
            keyboard = [
                [InlineKeyboardButton("📝 Registrati", callback_data='register')],
                [InlineKeyboardButton("ℹ️ Info", callback_data='info')]
            ]
            
            await update.message.reply_text(
                "🎰 *Benvenuto su GiankyBot!* 🎰\n\n"
                "Per iniziare a giocare e vincere premi:\n"
                "1. Registrati con il tuo wallet\n"
                "2. Ottieni 3 spin GRATIS\n"
                "3. Gira la ruota per vincere GKY!\n\n"
                "Clicca il bottone qui sotto per registrarti:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🎡 Gira la Ruota", web_app=WebAppInfo(url=os.getenv('WEBAPP_URL')))],
                [InlineKeyboardButton("🛒 Compra Spin", callback_data='buy_spins')],
                [InlineKeyboardButton("📊 Le mie statistiche", callback_data='stats')],
                [InlineKeyboardButton("🔄 Restart Registrazione", callback_data='restart')]
            ]
            
            await update.message.reply_text(
                f"👋 *Bentornato, {user['first_name']}!*\n\n"
                f"💰 Saldo: `{user['balance']} GKY`\n"
                f"🎫 Spin disponibili: `{user['spins']}`\n\n"
                "Cosa vuoi fare?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        logger.error(f"Errore nel gestire /start: {e}")
        await update.message.reply_text("❌ Si è verificato un errore. Riprova.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} ha attivato /restart")
    
    # Rimuove l'utente esistente
    conn = sqlite3.connect('giankybot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

    # Richiama la registrazione
    await start(update, context)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "ℹ️ *Info sul Bot*\n\n"
        "GiankyBot è un bot divertente che ti permette di girare una ruota virtuale per vincere GKY! Puoi usare i tuoi GKY per acquistare spin, guadagnare premi e interagire con altri utenti. "
        "Inoltre, puoi guadagnare GKY gratis registrandoti e partecipando alla nostra community!\n\n"
        "Per iniziare, clicca su 'Registrati' oppure esplora le altre funzionalità del bot.",
        parse_mode='Markdown'
    )

async def buy_spins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await query.edit_message_text("ℹ️ Devi prima registrarti.")
        return
    
    keyboard = [
        [InlineKeyboardButton(p['label'], callback_data=f'buy_{key}') for key, p in SPIN_PACKAGES.items()]
    ]
    
    await query.edit_message_text(
        "🛒 *Acquista Spin*\n\n"
        "Scegli il pacchetto di spin che desideri acquistare:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUY_SPINS

/**
 * WhatsApp Web Bridge - Node.js server using whatsapp-web.js
 * Communicates with Python via HTTP/JSON API
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');

const app = express();
app.use(express.json());

// Initialize WhatsApp client
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: './whatsapp_session'
    }),
    puppeteer: {
        headless: false,
        executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',  // Use system Chrome
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

let clientReady = false;
let qrCode = null;
let newMessages = [];

// QR Code event
client.on('qr', (qr) => {
    console.log('[BRIDGE] QR Code received');
    qrCode = qr;
    qrcode.generate(qr, { small: true });
});

// Authenticated event
client.on('authenticated', () => {
    console.log('[BRIDGE] Authenticated successfully');
    qrCode = null;
});

// Ready event
client.on('ready', () => {
    console.log('[BRIDGE] WhatsApp client is ready!');
    clientReady = true;
    qrCode = null;
});

// Message event - NEW MESSAGES DETECTED HERE
client.on('message', async (msg) => {
    try {
        // Only track messages not from me
        if (!msg.fromMe) {
            // Get chat info (more reliable than contact)
            const chat = await msg.getChat();

            // Extract sender name from message or chat
            let senderName = 'Unknown';
            let chatName = 'Unknown';

            try {
                chatName = chat.name || msg.from || 'Unknown';
                // For group chats, try to get sender name
                if (chat.isGroup && msg.author) {
                    senderName = msg.author.split('@')[0]; // Extract phone number
                } else {
                    senderName = chatName;
                }
            } catch (e) {
                console.log('[BRIDGE] Warning: Could not get full chat/sender info, using fallback');
                chatName = msg.from || 'Unknown';
                senderName = msg.from || 'Unknown';
            }

            const messageData = {
                id: msg.id._serialized,
                from: msg.from,
                to: msg.to,
                body: msg.body || '',
                timestamp: msg.timestamp,
                isFromMe: msg.fromMe,
                chatName: chatName,
                senderName: senderName,
                type: msg.type,
                hasMedia: msg.hasMedia
            };

            console.log(`[BRIDGE] New message from ${messageData.senderName}: ${msg.body}`);
            newMessages.push(messageData);

            // Keep only last 100 messages in memory
            if (newMessages.length > 100) {
                newMessages.shift();
            }
        }
    } catch (error) {
        console.error('[BRIDGE] Error processing message:', error);
    }
});

// Disconnected event
client.on('disconnected', (reason) => {
    console.log('[BRIDGE] Client was disconnected:', reason);
    clientReady = false;
});

// Initialize client
console.log('[BRIDGE] Initializing WhatsApp client...');
client.initialize().catch(err => {
    console.error('[BRIDGE] Failed to initialize client:', err);
    process.exit(1);
});

// ========== HTTP API ENDPOINTS ==========

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        ready: clientReady,
        qrCode: qrCode
    });
});

// Get status
app.get('/status', (req, res) => {
    res.json({
        ready: clientReady,
        needsQR: qrCode !== null,
        qrCode: qrCode
    });
});

// Get new messages (polling endpoint)
app.get('/messages/new', (req, res) => {
    const messages = [...newMessages];
    newMessages = []; // Clear after retrieval
    res.json({
        count: messages.length,
        messages: messages
    });
});

// Send message
app.post('/messages/send', async (req, res) => {
    try {
        if (!clientReady) {
            return res.status(503).json({ error: 'Client not ready' });
        }

        const { chatId, message } = req.body;

        if (!chatId || !message) {
            return res.status(400).json({ error: 'chatId and message are required' });
        }

        // Format chat ID if it's just a number
        const formattedChatId = chatId.includes('@') ? chatId : `${chatId}@c.us`;

        const result = await client.sendMessage(formattedChatId, message);

        res.json({
            success: true,
            messageId: result.id._serialized
        });
    } catch (error) {
        console.error('[BRIDGE] Error sending message:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get all chats
app.get('/chats', async (req, res) => {
    try {
        if (!clientReady) {
            return res.status(503).json({ error: 'Client not ready' });
        }

        const chats = await client.getChats();
        const chatList = chats.map(chat => ({
            id: chat.id._serialized,
            name: chat.name,
            isGroup: chat.isGroup,
            unreadCount: chat.unreadCount,
            timestamp: chat.timestamp
        }));

        res.json({
            count: chatList.length,
            chats: chatList
        });
    } catch (error) {
        console.error('[BRIDGE] Error getting chats:', error);
        res.status(500).json({ error: error.message });
    }
});

// Get chat messages
app.get('/chats/:chatId/messages', async (req, res) => {
    try {
        if (!clientReady) {
            return res.status(503).json({ error: 'Client not ready' });
        }

        const chatId = req.params.chatId;
        const limit = parseInt(req.query.limit) || 50;

        const chat = await client.getChatById(chatId);
        const messages = await chat.fetchMessages({ limit: limit });

        const messageList = await Promise.all(messages.map(async (msg) => {
            const contact = await msg.getContact();
            return {
                id: msg.id._serialized,
                body: msg.body,
                timestamp: msg.timestamp,
                isFromMe: msg.fromMe,
                senderName: contact.pushname || contact.name || contact.number,
                type: msg.type
            };
        }));

        res.json({
            chatId: chatId,
            count: messageList.length,
            messages: messageList
        });
    } catch (error) {
        console.error('[BRIDGE] Error getting chat messages:', error);
        res.status(500).json({ error: error.message });
    }
});

// Search contacts
app.post('/contacts/search', async (req, res) => {
    try {
        if (!clientReady) {
            return res.status(503).json({ error: 'Client not ready' });
        }

        const { query } = req.body;

        const chats = await client.getChats();
        const results = chats.filter(chat =>
            chat.name && chat.name.toLowerCase().includes(query.toLowerCase())
        ).map(chat => ({
            id: chat.id._serialized,
            name: chat.name,
            isGroup: chat.isGroup
        }));

        res.json({
            query: query,
            count: results.length,
            results: results
        });
    } catch (error) {
        console.error('[BRIDGE] Error searching contacts:', error);
        res.status(500).json({ error: error.message });
    }
});

// Start server
const PORT = 3000;
app.listen(PORT, '127.0.0.1', () => {
    console.log(`[BRIDGE] HTTP API server listening on http://127.0.0.1:${PORT}`);
    console.log('[BRIDGE] Endpoints:');
    console.log('  GET  /health');
    console.log('  GET  /status');
    console.log('  GET  /messages/new');
    console.log('  POST /messages/send');
    console.log('  GET  /chats');
    console.log('  GET  /chats/:chatId/messages');
    console.log('  POST /contacts/search');
});

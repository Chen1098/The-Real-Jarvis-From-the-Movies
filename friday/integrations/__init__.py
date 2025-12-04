"""
WhatsApp and other integrations for Jarvis AI Assistant
"""

# Only import models - services are imported directly where needed
from .whatsapp_models import WhatsAppMessage, WhatsAppContact, WhatsAppChat

__all__ = ['WhatsAppMessage', 'WhatsAppContact', 'WhatsAppChat']

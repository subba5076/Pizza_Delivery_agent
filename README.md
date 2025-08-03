# Pizza_Delivery_agent
🤖 AI-powered Pizza Ordering Chatbot with voice support. Built using Flask, this agent lets users browse, customize, and place pizza orders through natural conversation via text or speech.
# 🍕 Pizza Ordering Chatbot Agent (with Voice Support)

## 👥 Team Members

| Name                      | GitHub Username      |
|---------------------------|----------------------|
| Subrahmanya Rajesh Nayak | [@subrahmanyaeu](https://github.com/subrahmanyaeu) |
| Rim Tafech                | [@rimtafech](https://github.com/rimtafech)         |
| Mohammad Samaiz Arshed   | [@samaizarshed](https://github.com/samaizarshed)   |
| Eli                       | [@eli](https://github.com/eli)                     |

This project was developed as part of our coursework for **[Artificial Intelligence]** at **SRH Berlin University of Applied Sciences**, under the guidance of **[Kristian Rother]**.

---

## 🧠 Project Overview

An AI-powered chatbot application to order pizza through text and voice. Users can browse the menu, customize their orders, and place them seamlessly using either typed input or speech. Built with Flask, this project integrates a conversational agent, order management, and speech recognition.

---

## 📁 Project Structure
'''bash
app/
│
├── init.py # App factory/init
├── agent.py # Core logic of the conversational agent
├── order_manager.py # Handles order state and customization
├── routes.py # Flask routes for frontend/backend interaction
├── speech_utils.py # Speech-to-text and text-to-speech utilities
├── menu.json # Pizza menu with items, descriptions, prices
├── static/ # Static assets (CSS, JS, audio)
├── templates/ # HTML templates (main UI)
└── run.py # Entry point to start the Flask server
'''

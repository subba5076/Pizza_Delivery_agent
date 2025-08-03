from flask import Blueprint, render_template, request, jsonify
from .agent import generate_response
from .speech_utils import speech_to_text
import os
import markdown
import json
import tempfile
import uuid

main = Blueprint('main', __name__)

menu_path = os.path.join(os.path.dirname(__file__), "menu.json")
with open(menu_path, "r") as f:
    MENU_DATA = json.load(f)

order_state = {
    "messages": [],
    "structured_order": { "items": [] },
    "stage": "start",
    "clarification_index": 0,
    "collected_special": None,
    "collected_confirmation": None,
    "collected_name": None,
    "collected_phone": None,
    "collected_address": None
}

WELCOME_MESSAGE = "Hello! Welcome to Mamma Mia's Pizza, Pasta & Drinks! Please choose what you'd like from our interactive menu. Once you're done, hit the 'Done with Order' button to proceed with your choices."

@main.route("/")
def home():
    order_state.clear()
    order_state.update({
        "messages": [],
        "structured_order": { "items": [] },
        "stage": "start",
        "clarification_index": 0,
        "collected_special": None,
        "collected_confirmation": None,
        "collected_name": None,
        "collected_phone": None,
        "collected_address": None
    })
    order_state["messages"].append({"user": "Bot initialized", "bot": WELCOME_MESSAGE})
    
    return render_template("index.html", initial_bot_message=WELCOME_MESSAGE, initial_menu_data=MENU_DATA)


@main.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")

    response_to_frontend = {
        "reply": "",
        "menu": None,
        "structured_order": order_state["structured_order"],
        "state": order_state
    }

    if user_input.lower() == "bot_restart_command":
        order_state.clear()
        order_state.update({
            "messages": [],
            "structured_order": { "items": [] },
            "stage": "start",
            "clarification_index": 0,
            "collected_special": None,
            "collected_confirmation": None,
            "collected_name": None,
            "collected_phone": None,
            "collected_address": None
        })
        response_to_frontend["reply"] = WELCOME_MESSAGE
        response_to_frontend["menu"] = MENU_DATA
        order_state["messages"].append({"user": "Bot Restarted", "bot": response_to_frontend["reply"]})
        return jsonify(response_to_frontend)

    current_user_message_for_llm = user_input

    try:
        parsed_input = json.loads(user_input)
        if parsed_input.get("type") == "order_finalized_from_menu":
            order_state["stage"] = "awaiting_item_details"
            order_state["structured_order"]["items"] = parsed_input["items"]
            order_state["clarification_index"] = 0
            
            current_user_message_for_llm = "The customer has finished selecting items from the menu. Please proceed to clarify order details for: " + ", ".join([item['name'] for item in parsed_input["items"]])
            
            response_to_frontend["menu"] = None 

    except json.JSONDecodeError:
        pass
    
    # Check if the user asks for the menu or if the LLM detects the menu isn't visible
    user_asked_for_menu = user_input.lower() in ["menu", "show menu", "list menu", "what do you have", "what's on the menu"]
    llm_detected_menu_issue = "it's not" in user_input.lower() or "not showing" in user_input.lower() or "where is it" in user_input.lower()

    if user_asked_for_menu or llm_detected_menu_issue:
        response_to_frontend["menu"] = MENU_DATA
        if user_asked_for_menu:
            current_user_message_for_llm = "The user asked for the menu. Please provide a brief conversational confirmation that the menu is now displayed."
        elif llm_detected_menu_issue:
             # Let the LLM handle the reply, but make sure the menu is sent to the client.
             current_user_message_for_llm = user_input

    reply_result = generate_response(
        messages=order_state["messages"],
        new_user_message=current_user_message_for_llm,
        current_state=order_state
    )

    response_to_frontend["reply"] = reply_result["reply"]
    order_state.update(reply_result["state"])

    if not (isinstance(user_input, str) and user_input.startswith('{"type":"order_finalized_from_menu"')):
        order_state["messages"].append({"user": user_input, "bot": response_to_frontend["reply"]})
    else:
        order_state["messages"].append({"user": "I'm done choosing from the menu.", "bot": response_to_frontend["reply"]})
    
    if order_state["stage"] == "completed":
        final_bot_message_for_history = response_to_frontend["reply"]
        
        order_state.clear()
        order_state.update({
            "messages": [],
            "structured_order": { "items": [] },
            "stage": "start",
            "clarification_index": 0,
            "collected_special": None,
            "collected_confirmation": None,
            "collected_name": None,
            "collected_phone": None,
            "collected_address": None
        })
        order_state["messages"].append({"user": "Session Restarted (Auto)", "bot": WELCOME_MESSAGE})
        response_to_frontend["menu"] = MENU_DATA

    return jsonify(response_to_frontend)

@main.route("/listen", methods=["POST"])
def listen():
    if "audio_data" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio_data"]
    
    temp_dir = tempfile.gettempdir()
    temp_audio_path = os.path.join(temp_dir, f"{uuid.uuid4()}.wav")
    audio_file.save(temp_audio_path)
    
    try:
        transcript = speech_to_text(temp_audio_path)
        return jsonify({"transcript": transcript})
    except Exception as e:
        print(f"Error in speech_to_text: {e}")
        return jsonify({"error": "Could not process audio"}), 500
    finally:
        os.remove(temp_audio_path)
# agent.py (corrected generate_response function)

import google.generativeai as genai
import re
import json
import os
import traceback
from .order_manager import calculate_price, find_item

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "API KEY HERE"))

menu_path = os.path.join(os.path.dirname(__file__), "menu.json")
with open(menu_path, "r") as f:
    MENU_DATA = json.load(f)

model = genai.GenerativeModel("gemini-2.0-flash")

SIZE_FULL_NAMES = {
    "s": "Small",
    "m": "Medium",
    "l": "Large",
    "single": "Single",
    "double": "Double",
    "regular": "Regular",
    "500ml": "500ml",
    "1l": "1 Liter"
}

# --- Helper Functions ---

def _get_order_summary_text(structured_order, collected_special=None, include_price=False):
    summary_lines = []
    items_for_price_calc = []

    if structured_order and structured_order.get("items"):
        for item in structured_order["items"]:
            item_name = item.get("name", "N/A Item")
            quantity = item.get("quantity", 1)
            item_category = item.get("category")
            item_size_option = item.get("size", "N/A")

            item_display = f"- {quantity}x {item_name}"
            
            # --- UPDATED LOGIC HERE ---
            # Correctly adds size to summary for any item that has a size
            if item_size_option != "N/A":
                item_display += f" ({SIZE_FULL_NAMES.get(item_size_option.lower(), item_size_option).upper()})"
            
            summary_lines.append(item_display)

            items_for_price_calc.append({
                "name": item.get("name"),
                "id": item.get("id"),
                "category": item.get("category"),
                "size": item.get("size"),
                "quantity": item.get("quantity", 1)
            })

    summary_text = ""
    if summary_lines:
        summary_text += "\n**Current Items:**\n" + "\n".join(summary_lines)
    else:
        summary_text += "\n**Current Items:** None"

    if collected_special is not None:
        special_text = collected_special if collected_special.lower() not in ["no", "none", "n/a"] else "None"
        summary_text += f"\n**Special requests:** {special_text}"

    if include_price:
        total_price, price_error = calculate_price(items_for_price_calc)
        if total_price is not None:
            summary_text += f"\n**Estimated Total:** ${total_price:.2f}"
        else:
            summary_text += f"\n**Total price:** Could not be calculated ({price_error or 'Unknown error.'})"
            
    return summary_text.strip()

def _get_menu_text():
    """Generates a hardcoded text menu from MENU_DATA to prevent hallucination."""
    menu_text = "Here is our menu:\n\n"
    for category, items in MENU_DATA.items():
        menu_text += f"**{category.title()}**:\n"
        for item in items:
            if isinstance(item, dict):
                menu_text += f"- {item['name']}\n"
            else:
                menu_text += f"- {item}\n"
    menu_text += "\n"
    return menu_text.strip()

# --- Main build_system_prompt ---
def build_system_prompt(current_state):
    prompt = (
        "You are Mamma Mia's friendly, helpful, polite, and efficient AI assistant. "
        "Your core task is to take customer orders for pizza, pasta, and drinks for delivery only. "
        "Maintain a warm and welcoming tone throughout the conversation.\n\n"
    )

    prompt += f"You are aware of the following menu items, their sizes, and prices:\n{_get_menu_text()}\n"
    prompt += "The customer has seen the interactive menu.\n\n"

    prompt += (
        "Here is the strict order process you must follow:\n"
        "1.  **Initial Greeting & Menu:** Greet the customer and confirm the menu is available. (Handled at start or when user asks for menu, you just confirm it's visible).\n"
        "2.  **Item Clarification (Options/Servings):** If the customer has finished selecting items from the menu, your *immediate next step* is to go through each selected item that has multiple options (e.g., different sizes for pizzas/pastas). **Ask for their specific option/serving one by one.** Do not proceed until all such items have a specified option. If an option is missing, clearly ask for it. **Crucial:** Adapt your language based on the item type and **always provide the exact available options you are given in the prompt (e.g., 'Small, Medium, Large')**:\n"
        "    - For pizzas/pastas: Ask 'What size would you like for the [Item Name]? (Available: [Exact Options])'\n"
        "3.  **Order Amendment/Addition:** The customer can request to modify or add items at any point *before final confirmation*. If they ask to modify/remove/add, acknowledge and ask for specifics, then update the `structured_order` and proceed to relevant clarification or re-confirmation. You should guide them through the amendment process.\n"
        "4.  **Special Requirements:** After *all* items requiring an option/serving have their options confirmed, and no more amendments are pending, then ask if they have any special requests (e.g., vegan, halal, gluten-free, or specific ingredient additions/removals like 'extra cheese' or 'no onions' for pizza/pasta).\n"
        "5.  **Order Confirmation (with Summary):** Before proceeding, explicitly summarize the entire order for the customer (including total price). The summary is provided to you in the prompt under 'Current Order Status for Customer Confirmation'. You MUST present this summary clearly and then ask them to confirm if everything is correct.\n"
        "6.  **Delivery Details:** Once confirmed, collect their full name, phone number, and complete delivery address. If the customer provides some but not all details, ask for the missing ones politely and concisely. Do not repeat already collected information unless confirming it.\n"
        "7.  **Final Summary & Farewell:** When you have ALL delivery details, provide a complete summary of their order, special requests, and delivery details, including the **total calculated price**. This final summary will be generated by the system, but your final conversational closing should be polite and warm.\n\n"
    )

    if current_state["stage"] in ["awaiting_confirmation", "awaiting_delivery_details", "completed", "awaiting_amendment"]:
        prompt += f"\n**Current Order Status for Customer Confirmation:**\n{_get_order_summary_text(current_state['structured_order'], current_state['collected_special'], include_price=True)}\n"
    elif current_state["stage"] == "awaiting_special_requests":
        prompt += f"\n**Current Order Items (for Special Request context):**\n{_get_order_summary_text(current_state['structured_order'])}\n"


    prompt += f"\n**Current Order State for Internal Reference:** {json.dumps(current_state, indent=2)}\n"
    prompt += "Based on this state and the conversation history, what should be your next response? Remember to be conversational and helpful."
    
    # This is the new, more dynamic instruction. It uses the state to guide the response.
    if current_state.get("collected_special"):
      prompt += "\n\n**Crucial:** A special request has been collected. You must start your reply by acknowledging it (e.g., 'Okay, I've noted your special request for...')."
    else:
      prompt += "\n\n**Crucial:** No special requests have been collected. You should start your reply by stating this (e.g., 'Okay, no special requests.')."
    
    prompt += "\n\n**Crucial:** After acknowledging special requests (or lack thereof), proceed directly to the summary for confirmation. Do NOT include the JSON from 'Current Order State for Internal Reference' in your response. It is for your internal reference only."

    return prompt
    # The n


def generate_response(messages, new_user_message, current_state=None):
    state = current_state if current_state is not None else {
        "stage": "start",
        "structured_order": { "items": [] },
        "clarification_index": 0,
        "collected_special": None,
        "collected_confirmation": None,
        "collected_name": None,
        "collected_phone": None,
        "collected_address": None
    }

    try:
        # --- NEW LOGIC: Handle initial welcome message and stage change ---
        if state["stage"] == "start" and not messages:
            state["stage"] = "awaiting_order" # Change state to prevent a second greeting
            return {
                "reply": "Hello! Welcome to Mamma Mia's Pizza, Pasta & Drinks! Please choose what you'd like from our interactive menu. Once you're done, hit the 'Done with Order' button to proceed with your choices.",
                "structured_order": state.get("structured_order"),
                "state": state
            }
        
        if new_user_message.lower() in ["where is it?", "it's not", "not showing"]:
            return {
                "reply": "Ah, no problem! It seems the interactive menu isn't visible. Let me list the menu items for you while we get that sorted out.\n\n" + _get_menu_text(),
                "structured_order": state.get("structured_order"),
                "state": state
            }
        
        chat_history = []
        
        # New logic to handle entering the amendment stage
        is_amendment_request = "remove" in new_user_message.lower() or \
           "change" in new_user_message.lower() or \
           ("add" in new_user_message.lower() and new_user_message.lower() != "i'd like to add")
        
        if is_amendment_request and state["stage"] not in ["start", "awaiting_amendment"]:
            state["stage"] = "awaiting_amendment"
            
        system_prompt_content = build_system_prompt(state)
        chat_history.append({"role": "user", "parts": [system_prompt_content]})

        for msg in messages:
            chat_history.append({"role": "user", "parts": [msg["user"]]})
            chat_history.append({"role": "model", "parts": [msg["bot"]]})

        chat_history.append({"role": "user", "parts": [new_user_message]})

        print("\n--- Sending to Gemini (Current State & History) ---\n")
        print(f"Current Stage: {state['stage']}")
        print(f"Current Clarification Index: {state['clarification_index']}")
        print("User message for LLM:", new_user_message)

        response = model.generate_content(chat_history)
        gemini_reply = response.text.strip() if hasattr(response, "text") and response.text else "Sorry, I didn’t catch that. Could you try again?"
        print("Gemini raw reply:", gemini_reply)

        final_reply_to_user = gemini_reply

        # --- NEW CODE FOR AMENDMENT STAGE ---
        if state["stage"] == "awaiting_amendment" and "ranch/bbq pizza" in new_user_message.lower() and state["collected_special"]:
            # Hardcoded example for now, should be generalized later
            # Check if a new item has been added and a special request exists
            last_item = state["structured_order"]["items"][-1] if state["structured_order"]["items"] else None
            if last_item and last_item.get("size"):
                final_reply_to_user = f"Alright! So that's one {SIZE_FULL_NAMES.get(last_item['size'], last_item['size']).upper()} {last_item['name']}. We previously noted a special request for '{state['collected_special']}'. Would you like these requests to apply to this new item as well?"
            else:
                 final_reply_to_user = gemini_reply

        elif state["stage"] == "awaiting_item_details":
            item_for_clarification = None
            for current_check_idx in range(state["clarification_index"], len(state["structured_order"]["items"])):
                potential_item = state["structured_order"]["items"][current_check_idx]
                menu_item_details = find_item(potential_item["category"], potential_item["id"])

                if menu_item_details and \
                   potential_item["category"] not in ["drinks"] and \
                   "sizes" in menu_item_details and \
                   len(menu_item_details["sizes"]) > 1 and \
                   "size" not in potential_item:
                    item_for_clarification = potential_item
                    state["clarification_index"] = current_check_idx
                    break
            
            if item_for_clarification is None:
                state["stage"] = "awaiting_special_requests"
                state["clarification_index"] = 0 
                # --- NEW LOGIC: MANUALLY GENERATE RESPONSE ---
                final_reply_to_user = "Wonderful! Now that we have all the details, do you have any special requests? For example, dietary needs (e.g., vegan, halal, gluten-free) or modifications (e.g., extra cheese, no onions)?"
            else:
                menu_item_details = find_item(item_for_clarification["category"], item_for_clarification["id"])
                if not menu_item_details:
                    final_reply_to_user = "I'm having trouble finding details for that item. Can you please specify which item you're referring to?"
                else:
                    available_size_options_raw = [s["size"].lower() for s in menu_item_details.get("sizes", [])]
                    size_found = None

                    if not new_user_message.startswith("The customer has finished selecting items from the menu.") and \
                       new_user_message.lower() not in ["yes", "ok", "confirm", "that's all", "no", "none"]:
                        for size_opt in available_size_options_raw:
                            if size_opt in new_user_message.lower():
                                size_found = size_opt
                                break

                    if size_found:
                        state["structured_order"]["items"][state["clarification_index"]]["size"] = size_found
                        state["clarification_index"] += 1

                        next_item_to_ask = None
                        for i in range(state["clarification_index"], len(state["structured_order"]["items"])):
                            next_potential_item = state["structured_order"]["items"][i]
                            next_menu_details = find_item(next_potential_item["category"], next_potential_item["id"])

                            if next_menu_details and \
                               "sizes" in next_menu_details and \
                               len(next_menu_details["sizes"]) > 1 and \
                               "size" not in next_potential_item:
                                next_item_to_ask = next_potential_item
                                state["clarification_index"] = i
                                break

                        if next_item_to_ask:
                            next_menu_details = find_item(next_item_to_ask["category"], next_item_to_ask["id"])
                            formatted_options = [SIZE_FULL_NAMES.get(s_opt['size'].lower(), s_opt['size']) for s_opt in next_menu_details.get('sizes', [])]
                            options_str = ', '.join(formatted_options)
                            
                            final_reply_to_user = f"Got it! A {SIZE_FULL_NAMES.get(size_found, size_found).upper()} {item_for_clarification['name']}. And for the {next_item_to_ask['name']}, what size would you like? (Available: {options_str})"
                        else:
                            state["stage"] = "awaiting_special_requests"
                            state["clarification_index"] = 0
                            # --- NEW LOGIC: MANUALLY GENERATE RESPONSE ---
                            final_reply_to_user = "Wonderful! Now that we have all the details, do you have any special requests? For example, dietary needs (e.g., vegan, halal, gluten-free) or modifications (e.g., extra cheese, no onions)?"

                    else:
                        formatted_options = [SIZE_FULL_NAMES.get(s_opt['size'].lower(), s_opt['size']) for s_opt in menu_item_details.get('sizes', [])]
                        options_str = ', '.join(formatted_options)
                        final_reply_to_user = f"Ah, bellissima! What size would you like for the {item_for_clarification['name']}? (Available: {options_str})"

        elif state["stage"] == "awaiting_special_requests":
            state["collected_special"] = new_user_message.strip()
            state["stage"] = "awaiting_confirmation"
            # --- MANUALLY GENERATE CONFIRMATION MESSAGE ---
            order_summary = _get_order_summary_text(state["structured_order"], state["collected_special"], include_price=True)
            
            # This is the corrected, dynamic logic for the reply opener
            if new_user_message.strip().lower() in ["no", "none", "n/a", "no special requests"]:
                opener = "Okay, no special requests. Before we proceed, let me confirm your order:"
            else:
                opener = f"Okay, I've noted your request for '{new_user_message.strip()}'. Before we proceed, let me confirm your order:"

            final_reply_to_user = f"{opener}\n\n{order_summary}\n\nDoes everything look correct?"

        elif state["stage"] == "awaiting_confirmation":
            if new_user_message.lower() in ["yes", "y", "correct", "confirm", "all correct", "that's correct"]:
                state["collected_confirmation"] = True
                state["stage"] = "awaiting_delivery_details"
            else:
                pass

        elif state["stage"] == "awaiting_delivery_details":
            extracted_name = re.search(r"my name is (.+?)(?:\.|$)", new_user_message, re.IGNORECASE)
            extracted_phone = re.search(r"(?:\D|^)(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})(?:\D|$)", new_user_message)
            extracted_address = re.search(r"address is (.+?)(?:$|\.|\,)", new_user_message, re.IGNORECASE)

            if extracted_name:
                state["collected_name"] = extracted_name.group(1).strip()
            if extracted_phone:
                state["collected_phone"] = extracted_phone.group(1).strip()
            if extracted_address:
                 state["collected_address"] = extracted_address.group(1).strip()

            if state["collected_name"] and state["collected_phone"] and state["collected_address"]:
                state["stage"] = "completed"
                order_summary_text = _get_order_summary_text(state["structured_order"], state["collected_special"], include_price=True)
                
                final_reply_to_user = (
                    f"Thank you for your order, {state['collected_name']}!\n\n"
                    f"Here is your full order summary:\n"
                    f"{order_summary_text}\n\n"
                    f"**Delivery to:** {state['collected_address']}\n"
                    f"**Phone:** {state['collected_phone']}\n\n"
                    "Your order is being prepared and will be delivered shortly. Enjoy your delicious meal!"
                )

                state = {
                    "stage": "start",
                    "structured_order": { "items": [] },
                    "clarification_index": 0,
                    "collected_special": None,
                    "collected_confirmation": None,
                    "collected_name": None,
                    "collected_phone": None,
                    "collected_address": None
                }
            else:
                pass

        else:
            pass

        print("Gemini formatted reply (after state logic):", final_reply_to_user)
        return {
            "reply": final_reply_to_user,
            "structured_order": state.get("structured_order"),
            "state": state
        }

    except Exception as e:
        print(f"Gemini API or processing error: {e}")
        traceback.print_exc()
        return {
            "reply": "I'm very sorry, but something went wrong on my end. Please try again shortly!",
            "structured_order": state.get("structured_order"),
            "state": state
        }
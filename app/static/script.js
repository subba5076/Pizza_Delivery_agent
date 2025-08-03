// script.js

const chatBox = document.getElementById("chat-box");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const micButton = document.getElementById("mic-button");
const restartButton = document.getElementById("restart-btn");

// Keep track of selected items in order
let currentOrderItems = []; // Initialize here to ensure it's always an array

function restartChat() {
  chatBox.innerHTML = "";
  removeCurrentMenu();
  currentOrderItems = [];
  sendMessage("BOT_RESTART_COMMAND"); // This signals a fresh start
}
// Keep a reference to the currently displayed menu div
let currentMenuDiv = null;

function appendMessage(text, isUser) {
  const msg = document.createElement("div");
  msg.className = "chat-bubble " + (isUser ? "user-msg" : "bot-msg");
  if (isUser) {
    msg.textContent = text;
  } else {
    msg.innerHTML = text;
  }
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// Function to remove the currently displayed interactive menu
function removeCurrentMenu() {
  if (currentMenuDiv) {
    currentMenuDiv.remove();
    currentMenuDiv = null;
  }
}

// Render the menu with sections and clickable buttons
function renderMenu(menu) {
  removeCurrentMenu(); // Always remove any existing menu before rendering a new one

  const interactiveMenuDiv = document.createElement("div");
  interactiveMenuDiv.className = "interactive-menu-container";
  currentMenuDiv = interactiveMenuDiv;

  function createSection(title) {
    const section = document.createElement("div");
    section.className = "menu-section";
    const header = document.createElement("h3");
    header.textContent = title;
    header.className = "menu-section-header";
    section.appendChild(header);
    return section;
  }

  // Helper to add item button, now passing category directly
  // The button text will show all available sizes for pizzas/pastas as info.
  function addItemButton(container, item, category) {
    const btn = document.createElement("button");
    btn.className = "menu-item-btn";
    let buttonText = item.name;
    if (item.sizes && item.sizes.length > 0) {
      // Show available sizes in the button text for info
      buttonText += ` - ${item.sizes.map(s => `${s.size}: $${s.price}`).join(", ")}`;
    } else if (item.price) { // For drinks that have a direct price
      buttonText += ` - $${item.price}`;
    }
    btn.textContent = buttonText;
    // When clicked, add the item ID, name, and category to currentOrderItems
    btn.onclick = () => addItemToOrder(item, category);
    container.appendChild(btn);
  }

  // Pizzas
  const pizzasSection = createSection("Pizzas 🍕");
  menu.pizzas.forEach(pizza => addItemButton(pizzasSection, pizza, "pizzas"));
  interactiveMenuDiv.appendChild(pizzasSection);

  // Pastas
  const pastasSection = createSection("Pastas 🍝");
  menu.pastas.forEach(pasta => addItemButton(pastasSection, pasta, "pastas"));
  interactiveMenuDiv.appendChild(pastasSection);

  // Drinks (if available)
  if (menu.drinks) {
    const drinksSection = createSection("Drinks 🍷");
    menu.drinks.forEach(drink => addItemButton(drinksSection, drink, "drinks"));
    interactiveMenuDiv.appendChild(drinksSection);
  }

  // Done button to submit the order
  const doneBtn = document.createElement("button");
  doneBtn.className = "done-order-btn";
  doneBtn.textContent = "Done with order";
  doneBtn.onclick = () => finishOrder();
  interactiveMenuDiv.appendChild(doneBtn);

  chatBox.appendChild(interactiveMenuDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// Store more details about the selected item. Quantity defaults to 1. Size will be clarified by bot.
function addItemToOrder(item, category) {
  currentOrderItems.push({
    id: item.id,
    name: item.name,
    category: category,
    quantity: 1 // Default quantity, can be clarified later if needed
  });
  appendMessage(`You added: ${item.name}`, true); // Show confirmation in the main chat box
}

// When done, send all selected items to the chat as a special message type
function finishOrder() {
  if (currentOrderItems.length === 0) {
    appendMessage("Please select at least one item before clicking 'Done with order'.", false); // Bot says this
    return;
  }
  // Send a special structured message to the backend
  sendMessage(JSON.stringify({
    type: "order_finalized_from_menu",
    items: currentOrderItems
  }));

  // Append a user-friendly message to the chat box before the bot replies
  appendMessage("I'm done choosing from the menu.", true);

  // Clear items after sending them to the backend, assuming backend will manage the order
  currentOrderItems = [];
  userInput.value = "";
  // IMPORTANT: Removed removeCurrentMenu(); from here.
  // The menu will now only be removed if the bot's response does not contain menu data.
}

// Send user message to backend and handle reply
async function sendMessage(text) {
  // Do NOT append the BOT_RESTART_COMMAND or the special JSON message
  // to the chatbox directly as user input, as they are internal.
  if (text !== "BOT_RESTART_COMMAND" && !text.startsWith('{"type":"order_finalized_from_menu"')) {
    appendMessage(text, true);
  }

  const response = await fetch("/chat", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  });

  const data = await response.json();
  console.log("Bot response:", data);

  // Crucial: Only render menu if data.menu is explicitly present and not empty
  if (data.menu && Object.keys(data.menu).length > 0) {
    renderMenu(data.menu);
  } else {
    // If bot sends no menu data, remove any existing menu
    removeCurrentMenu(); 
  }

  // Always append bot's text reply
  if (data.reply) {
    appendMessage(data.reply, false);
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = userInput.value.trim();
  if (text !== "") {
    sendMessage(text);
    userInput.value = "";
  }
});

restartButton.addEventListener("click", restartChat);

let mediaRecorder;
let audioChunks = [];

micButton.addEventListener("click", async () => {
  if (micButton.dataset.recording === "true") {
    mediaRecorder.stop();
    micButton.textContent = "🎤";
    micButton.dataset.recording = "false";
  } else {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Audio recording not supported in your browser");
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.start();
    micButton.textContent = "🎙️ Recording...";
    micButton.dataset.recording = "true";

    audioChunks = [];

    mediaRecorder.addEventListener("dataavailable", event => {
      audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener("stop", async () => {
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      const transcript = await uploadAudio(audioBlob);
      if (transcript) {
        sendMessage(transcript);
      }
    });
  }
});

async function uploadAudio(blob) {
  const formData = new FormData();
  formData.append("audio_data", blob, "user_audio.wav");

  try {
    const response = await fetch("/listen", {
      method: "POST",
      body: formData
    });
    const data = await response.json();
    return data.transcript;
  } catch (error) {
    console.error("Error uploading audio:", error);
    return "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  restartChat(); // Simulates a page load as a fresh start
});
// ========== BrokerAI Frontend ==========

const API_BASE = window.location.origin;

// --- DOM refs ---
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const btnVoice = document.getElementById("btn-voice");
const voiceStatus = document.getElementById("voice-status");
const threadInput = document.getElementById("thread-id");
const btnCheckStatus = document.getElementById("btn-check-status");

// Scrape
const btnScrapeUrl = document.getElementById("btn-scrape-url");
const btnScrapeText = document.getElementById("btn-scrape-text");
const scrapeResult = document.getElementById("scrape-result");

// --- Navigation ---
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document
      .querySelectorAll(".nav-btn")
      .forEach((b) => b.classList.remove("active"));
    document
      .querySelectorAll(".panel")
      .forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document
      .getElementById(`panel-${btn.dataset.panel}`)
      .classList.add("active");
  });
});

// --- Scrape Tabs ---
document.querySelectorAll(".scrape-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document
      .querySelectorAll(".scrape-tab")
      .forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document
      .getElementById("scrape-form-url")
      .classList.toggle("hidden", tab.dataset.tab !== "url");
    document
      .getElementById("scrape-form-text")
      .classList.toggle("hidden", tab.dataset.tab !== "text");
  });
});

// ========== Chat ==========

function addMessage(content, role = "bot") {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "bot" ? "🏠" : "👤";

  const body = document.createElement("div");
  body.className = "message-body";

  // Simple markdown-ish rendering
  const formatted = formatMessage(content);
  body.innerHTML = formatted;

  div.appendChild(avatar);
  div.appendChild(body);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function addTypingIndicator() {
  const div = document.createElement("div");
  div.className = "message bot";
  div.id = "typing-indicator";

  div.innerHTML = `
        <div class="message-avatar">🏠</div>
        <div class="message-body">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function formatMessage(text) {
  // Convert newlines to <br>, bold **text**, and bullet points
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = "";
  autoResize(chatInput);
  addMessage(text, "user");
  addTypingIndicator();
  btnSend.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        thread_id: threadInput.value || "default_user",
      }),
    });

    removeTypingIndicator();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      addMessage(`Грешка: ${err.detail || res.statusText}`, "bot");
      return;
    }

    const data = await res.json();
    addMessage(data.response, "bot");
  } catch (e) {
    removeTypingIndicator();
    addMessage(`Грешка при връзка със сървъра: ${e.message}`, "bot");
  } finally {
    btnSend.disabled = false;
    chatInput.focus();
  }
}

// Auto-resize textarea
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

chatInput.addEventListener("input", () => autoResize(chatInput));

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

btnSend.addEventListener("click", sendMessage);

// ========== Voice ==========

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

btnVoice.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      await sendVoice(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    btnVoice.classList.add("recording");
    voiceStatus.textContent = "🔴 Записване... (натиснете отново за спиране)";
    voiceStatus.classList.remove("hidden");
  } catch (e) {
    voiceStatus.textContent = "❌ Няма достъп до микрофон";
    voiceStatus.classList.remove("hidden");
    setTimeout(() => voiceStatus.classList.add("hidden"), 3000);
  }
});

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  isRecording = false;
  btnVoice.classList.remove("recording");
  voiceStatus.textContent = "⏳ Обработване на аудиото...";
}

async function sendVoice(blob) {
  addTypingIndicator();

  try {
    const formData = new FormData();
    formData.append("file", blob, "recording.webm");
    formData.append("thread_id", threadInput.value || "default_user");

    const res = await fetch(`${API_BASE}/api/chat/voice`, {
      method: "POST",
      body: formData,
    });

    removeTypingIndicator();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      addMessage(
        `Грешка при гласов вход: ${err.detail || res.statusText}`,
        "bot",
      );
      return;
    }

    const data = await res.json();

    if (data.transcription) {
      addMessage(data.transcription, "user");
    }
    addMessage(data.response, "bot");
  } catch (e) {
    removeTypingIndicator();
    addMessage(`Грешка при изпращане на аудио: ${e.message}`, "bot");
  } finally {
    voiceStatus.classList.add("hidden");
  }
}

// ========== Scrape ==========

btnScrapeUrl.addEventListener("click", () => scrape("url"));
btnScrapeText.addEventListener("click", () => scrape("text"));

async function scrape(mode) {
  const btn = mode === "url" ? btnScrapeUrl : btnScrapeText;
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Зареждане...";
  scrapeResult.classList.add("hidden");

  let body = {};
  if (mode === "url") {
    body.url = document.getElementById("scrape-url").value;
    body.max_pages =
      parseInt(document.getElementById("scrape-pages").value) || 3;
  } else {
    body.text = document.getElementById("scrape-text").value;
  }

  try {
    const res = await fetch(`${API_BASE}/api/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    scrapeResult.classList.remove("hidden", "success", "error");

    if (res.ok) {
      scrapeResult.classList.add("success");
      scrapeResult.textContent = formatScrapeResult(data);
    } else {
      scrapeResult.classList.add("error");
      scrapeResult.textContent = `Грешка: ${data.detail || JSON.stringify(data)}`;
    }
  } catch (e) {
    scrapeResult.classList.remove("hidden", "success", "error");
    scrapeResult.classList.add("error");
    scrapeResult.textContent = `Грешка: ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

function formatScrapeResult(data) {
  const lines = [];
  if (data.added_count !== undefined) {
    lines.push(`✅ Добавени имоти: ${data.added_count}`);
  }
  if (data.skipped_count !== undefined) {
    lines.push(`⏭ Пропуснати (дубликати): ${data.skipped_count}`);
  }
  if (data.total_found !== undefined) {
    lines.push(`📊 Общо намерени: ${data.total_found}`);
  }
  if (data.pages_scraped !== undefined) {
    lines.push(`📄 Обработени страници: ${data.pages_scraped}`);
  }
  if (data.status) {
    lines.push(`Статус: ${data.status}`);
  }
  return lines.length ? lines.join("\n") : JSON.stringify(data, null, 2);
}

// ========== Status Checks ==========

btnCheckStatus.addEventListener("click", checkStatus);

async function checkStatus() {
  const dots = {
    api: document.getElementById("status-api"),
    db: document.getElementById("status-db"),
    llm: document.getElementById("status-llm"),
  };

  // Reset all to loading
  Object.values(dots).forEach((d) => {
    d.className = "status-dot loading";
  });

  // API check
  try {
    const res = await fetch(`${API_BASE}/`);
    dots.api.className = res.ok ? "status-dot ok" : "status-dot err";
  } catch {
    dots.api.className = "status-dot err";
  }

  // DB check
  try {
    const res = await fetch(`${API_BASE}/test-db`);
    const data = await res.json();
    dots.db.className =
      data.status === "success" ? "status-dot ok" : "status-dot err";
  } catch {
    dots.db.className = "status-dot err";
  }

  // LLM check
  try {
    const res = await fetch(`${API_BASE}/test-llm`);
    const data = await res.json();
    dots.llm.className =
      data.status === "success" ? "status-dot ok" : "status-dot err";
  } catch {
    dots.llm.className = "status-dot err";
  }
}

// Run status check on load
checkStatus();

// ========== Scheduler / Appointments ==========

const btnBookAppt = document.getElementById("btn-book-appt");
const btnRefreshAppts = document.getElementById("btn-refresh-appts");
const appointmentsList = document.getElementById("appointments-list");
const apptFormMsg = document.getElementById("appt-form-msg");

btnBookAppt.addEventListener("click", bookAppointment);
btnRefreshAppts.addEventListener("click", loadAppointments);

// Load appointments when the schedule panel is shown
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.panel === "schedule") {
      loadAppointments();
    }
  });
});

async function bookAppointment() {
  const propertyId = document.getElementById("appt-property-id").value;
  const dateTime = document.getElementById("appt-datetime").value.trim();
  const contact =
    document.getElementById("appt-contact").value.trim() || "Anonymous";

  // Validation
  if (!propertyId || !dateTime) {
    showApptMsg("Моля, попълнете ID на имот и дата/час.", "error");
    return;
  }

  btnBookAppt.disabled = true;
  btnBookAppt.textContent = "Записване...";

  try {
    const res = await fetch(`${API_BASE}/api/appointments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        property_id: parseInt(propertyId),
        date_time: dateTime,
        user_contact: contact,
      }),
    });

    const data = await res.json();

    if (res.ok) {
      showApptMsg(
        `✅ Оглед #${data.appointment.id} записан за имот #${data.appointment.property_id} — ${data.appointment.date_time}`,
        "success",
      );
      // Clear form
      document.getElementById("appt-property-id").value = "";
      document.getElementById("appt-datetime").value = "";
      document.getElementById("appt-contact").value = "";
      // Refresh list
      loadAppointments();
    } else {
      showApptMsg(`Грешка: ${data.detail || JSON.stringify(data)}`, "error");
    }
  } catch (e) {
    showApptMsg(`Грешка: ${e.message}`, "error");
  } finally {
    btnBookAppt.disabled = false;
    btnBookAppt.textContent = "Запиши оглед";
  }
}

async function loadAppointments() {
  appointmentsList.innerHTML = '<p class="empty-state">Зареждане...</p>';

  try {
    const res = await fetch(`${API_BASE}/api/appointments`);
    const data = await res.json();

    if (!res.ok || !data.appointments) {
      appointmentsList.innerHTML =
        '<p class="empty-state">Грешка при зареждане.</p>';
      return;
    }

    if (data.appointments.length === 0) {
      appointmentsList.innerHTML =
        '<p class="empty-state">Няма записани огледи.</p>';
      return;
    }

    appointmentsList.innerHTML = data.appointments
      .map(
        (a) => `
        <div class="appt-card">
          <div class="appt-info">
            <div class="appt-main">
              <span class="appt-property">Имот #${a.property_id}</span>
              <span class="appt-status status-${(a.status || "confirmed").toLowerCase()}">${a.status || "Confirmed"}</span>
            </div>
            <div class="appt-details">
              <span>📅 ${a.date_time}</span>
              <span>👤 ${a.user_contact}</span>
            </div>
          </div>
          <button class="btn-cancel" data-id="${a.id}" title="Отмени оглед">✕</button>
        </div>
      `,
      )
      .join("");

    // Attach cancel handlers
    appointmentsList.querySelectorAll(".btn-cancel").forEach((btn) => {
      btn.addEventListener("click", () => cancelAppointment(btn.dataset.id));
    });
  } catch (e) {
    appointmentsList.innerHTML = `<p class="empty-state">Грешка: ${e.message}</p>`;
  }
}

async function cancelAppointment(id) {
  if (!confirm(`Сигурни ли сте, че искате да отмените оглед #${id}?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/appointments/${id}`, {
      method: "DELETE",
    });

    if (res.ok) {
      loadAppointments();
    } else {
      const data = await res.json().catch(() => ({}));
      alert(`Грешка: ${data.detail || "Неуспешна отмяна"}`);
    }
  } catch (e) {
    alert(`Грешка: ${e.message}`);
  }
}

function showApptMsg(text, type) {
  apptFormMsg.textContent = text;
  apptFormMsg.className = `appt-form-msg ${type}`;
  apptFormMsg.classList.remove("hidden");
  setTimeout(() => apptFormMsg.classList.add("hidden"), 5000);
}

// ========== ML Model Training ==========

const btnMlTrain = document.getElementById("btn-ml-train");
const btnMlCheck = document.getElementById("btn-ml-check");
const mlTrainResult = document.getElementById("ml-train-result");
const mlTrainedBadge = document.getElementById("ml-trained-badge");

btnMlTrain.addEventListener("click", trainModel);
btnMlCheck.addEventListener("click", checkModelStatus);

// Check model status when ML panel is shown
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.panel === "ml") {
      checkModelStatus();
    }
  });
});

async function checkModelStatus() {
  mlTrainedBadge.textContent = "Проверка...";
  mlTrainedBadge.className = "ml-badge ml-badge-unknown";

  try {
    const res = await fetch(`${API_BASE}/api/ml/status`);
    const data = await res.json();

    if (data.trained) {
      mlTrainedBadge.textContent = "✅ Обучен";
      mlTrainedBadge.className = "ml-badge ml-badge-ok";
    } else {
      mlTrainedBadge.textContent = "❌ Не е обучен";
      mlTrainedBadge.className = "ml-badge ml-badge-err";
    }
  } catch {
    mlTrainedBadge.textContent = "⚠️ Грешка";
    mlTrainedBadge.className = "ml-badge ml-badge-err";
  }
}

async function trainModel() {
  btnMlTrain.disabled = true;
  btnMlTrain.textContent = "⏳ Обучение...";
  mlTrainResult.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/ml/train`, {
      method: "POST",
    });
    const data = await res.json();

    mlTrainResult.classList.remove("hidden", "ml-result-ok", "ml-result-err");

    if (data.status === "success") {
      mlTrainResult.classList.add("ml-result-ok");
      mlTrainResult.innerHTML = `
        <strong>✅ Моделът е обучен успешно!</strong><br>
        📊 Използвани имоти: <strong>${data.samples_used}</strong><br>
        ⏭ Пропуснати (без площ): <strong>${data.samples_skipped}</strong><br>
        📈 Cross-validated R²: <strong>${data.cv_r2 !== null ? data.cv_r2.toFixed(4) : "N/A"}</strong>
      `;
      // Refresh status badge
      checkModelStatus();
    } else {
      mlTrainResult.classList.add("ml-result-err");
      mlTrainResult.textContent = `❌ ${data.message || "Неизвестна грешка"}`;
    }
  } catch (e) {
    mlTrainResult.classList.remove("hidden", "ml-result-ok", "ml-result-err");
    mlTrainResult.classList.add("ml-result-err");
    mlTrainResult.textContent = `❌ Грешка: ${e.message}`;
  } finally {
    btnMlTrain.disabled = false;
    btnMlTrain.textContent = "🚀 Обучи модела";
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const btnOn = document.getElementById("btn-on");
  const btnOff = document.getElementById("btn-off");
  const powerToggle = document.getElementById("power-toggle");
  const powerSwitch = document.querySelector(".power-switch");

  let isProcessing = false; // Prevent multiple simultaneous requests

  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error("status fetch failed");
      const data = await res.json();
      updateUI(data.relay_on, false); // false means this is from polling, not user action
    } catch (err) {
      console.error(err);
      powerSwitch.classList.add("offline");
    }
  }

  function updateUI(isOn, fromUserAction = true) {
    // Update current state
    currentState = isOn;

    // Update the power switch checkbox
    powerToggle.checked = isOn;

    // Update visual classes
    if (isOn) {
      powerSwitch.classList.add("power-on");
      powerSwitch.classList.remove("power-off", "offline");
      btnOn.classList.add("active");
      btnOff.classList.remove("active");
    } else {
      powerSwitch.classList.add("power-off");
      powerSwitch.classList.remove("power-on", "offline");
      btnOn.classList.remove("active");
      btnOff.classList.add("active");
    }
  }

  async function sendAction(action) {
    // Prevent multiple simultaneous requests
    if (isProcessing) {
      console.log("Request already in progress, skipping...");
      return;
    }

    try {
      isProcessing = true;
      const isOn = action === "on";

      // Immediate UI feedback - ALWAYS update UI when user clicks
      updateUI(isOn, true);

      // Button click animation
      if (action === "on") {
        btnOn.classList.add("clicking");
        setTimeout(() => btnOn.classList.remove("clicking"), 300);
      } else {
        btnOff.classList.add("clicking");
        setTimeout(() => btnOff.classList.remove("clicking"), 300);
      }

      // Send the action to the server
      const res = await fetch("/api/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });

      if (!res.ok) {
        throw new Error("Server response not OK");
      }

      const data = await res.json();

      // Update UI with server response to ensure sync
      updateUI(data.relay_on, true);
      
    } catch (e) {
      console.error("Error sending action:", e);
      // Revert UI on error by fetching current status
      await fetchStatus();
    } finally {
      // Always reset processing flag
      isProcessing = false;
    }
  }

  // Power switch toggle event
  powerToggle.addEventListener("change", function () {
    const action = this.checked ? "on" : "off";
    sendAction(action);
  });

  // Button event listeners - REMOVE the state checks that prevent clicking
  btnOn.addEventListener("click", function () {
    sendAction("on");
  });

  btnOff.addEventListener("click", function () {
    sendAction("off");
  });

  // Initial load
  fetchStatus();

  // Polling every 2s
  setInterval(fetchStatus, 2000);
});
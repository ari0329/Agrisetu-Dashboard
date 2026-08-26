/* AgriSetu — Interactive product tour (Driver.js) */

const TOUR_STORAGE_KEY = "agrisetu_tour_done_v1";

function tourPopoverHtml(title, body) {
  const encoded = encodeURIComponent(`${title}. ${body}`);
  return `
    <p class="tour-body">${body}</p>
    <button type="button" class="btn-tts tour-step-tts" data-tts-text="${encoded}" title="Listen to this step">
      🔊 Listen
    </button>`;
}

function buildTourSteps() {
  return [
    {
      element: "#field-id",
      popover: {
        title: "Select your field",
        description: tourPopoverHtml(
          "Select your field",
          "Choose the field paired with your ESP8266 device. Use + Field to add a new one with your Device ID from the Arduino sketch."
        ),
        side: "bottom",
        align: "start",
      },
    },
    {
      element: "#connection-banner",
      popover: {
        title: "Device connection",
        description: tourPopoverHtml(
          "Device connection",
          "This banner shows whether your Arduino sensors are online. Predictions and live advisories need an active connection."
        ),
        side: "bottom",
        align: "center",
      },
    },
    {
      element: "#card-sm",
      popover: {
        title: "Live sensor readings",
        description: tourPopoverHtml(
          "Live sensor readings",
          "Soil moisture, temperature, and water level update every few seconds from your field hardware."
        ),
        side: "bottom",
        align: "start",
      },
    },
    {
      element: "#advisory-list",
      popover: {
        title: "Actionable alerts",
        description: tourPopoverHtml(
          "Actionable alerts",
          "Irrigation, drought, heat, and flood alerts appear here. Tap the speaker icon on any alert to hear it read aloud."
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#irrigation-box",
      popover: {
        title: "Smart irrigation",
        description: tourPopoverHtml(
          "Smart irrigation",
          "Get a clear irrigate-now or wait recommendation with urgency, next check time, and suggested water volume."
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#risk-bars",
      popover: {
        title: "Environmental risk",
        description: tourPopoverHtml(
          "Environmental risk",
          "Track drought, flood, heat, and disease-climate yield risk scores. Use Refresh Advice to update."
        ),
        side: "left",
        align: "start",
      },
    },
    {
      element: "#btn-vision",
      popover: {
        title: "Crop health scan",
        description: tourPopoverHtml(
          "Crop health scan",
          "Upload a leaf photo or run a demo to detect disease, pest damage, and nutrient issues on-device."
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#btn-predict",
      popover: {
        title: "Crop prediction",
        description: tourPopoverHtml(
          "Crop prediction",
          "When sensors are online, predict the best crop from live conditions. Speaker icons read results aloud."
        ),
        side: "top",
        align: "start",
      },
    },
    {
      element: "#analyticsChart",
      popover: {
        title: "Farm analytics",
        description: tourPopoverHtml(
          "Farm analytics",
          "Review moisture and yield-risk trends over time to spot patterns in your field performance."
        ),
        side: "top",
        align: "center",
      },
    },
  ];
}

function markTourComplete() {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "1");
  } catch {
    /* ignore storage errors */
  }
}

function shouldStartTour() {
  try {
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return false;
  } catch {
    /* allow tour if storage unavailable */
  }
  return Boolean(window.AGRISETU_FRESH_LOGIN);
}

function startProductTour() {
  if (!window.driver?.js?.driver) {
    console.warn("Driver.js not loaded — tour skipped.");
    return;
  }

  const driverObj = window.driver.js.driver({
    showProgress: true,
    animate: true,
    overlayColor: "rgba(0,0,0,.72)",
    stagePadding: 8,
    stageRadius: 8,
    popoverClass: "agrisetu-tour-popover",
    nextBtnText: "Next →",
    prevBtnText: "← Back",
    doneBtnText: "Finish tour",
    steps: buildTourSteps(),
    onDestroyed: markTourComplete,
  });

  driverObj.drive();
}

function maybeStartProductTour() {
  if (!shouldStartTour()) return;
  setTimeout(startProductTour, 900);
}

window.startProductTour = startProductTour;
window.maybeStartProductTour = maybeStartProductTour;
